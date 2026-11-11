"""Track G: PeTTaChainer *shadow* run alongside the Python PLN phase.

Off by default.  Enabled per bot by ``"pc_shadow": true`` in ``<state_dir>/_wmtm_flags.json`` (or env
WMTM_PC_SHADOW=1); see wmtm/runtime_config.py for every knob.  The orchestrator calls
maybe_launch(store, cycle, state_dir) after the Python PLN phase; the cycle side only copies the top-K item fields
(K = shadow_k, default 200) into a spec under ``<runtime_dir>/pc_shadow/`` and launches a detached, niced worker
(``python -m wmtm.workers.pc_shadow``) that builds the snapshot (cached semparse atoms only, goals)
and asks PeTTaChainer.  It NEVER waits on the worker, never admits anything into WMTM and never raises.
At most one worker runs at a time (pidfile guard); a busy worker means the cycle is skipped, not queued.
"""
from __future__ import annotations
import glob, os, re, time

from . import runtime_config as rc

WORKER_MODULE = "wmtm.workers.pc_shadow"
WORKER_MAX_AGE = 900          # s; an older worker is presumed hung and killed by the next launch
_NAME = re.compile(r"^(\w+)\(([a-z_][a-z0-9_-]*),([a-z_][a-z0-9_-]*)\)$")
# PLN relation -> MeTTa head.  Python "Implication" facts become (Implies a b): a bare (Implication a b)
# would be read by PeTTaChainer as a *rule*, not a fact.
HEAD = {"Inheritance": "Inheritance", "Implication": "Implies", "Similarity": "Similarity", "Evaluation": "Evaluation"}
TRANSITIVE = ("Inheritance",)   # F3 v2: Implies dropped with imp_trans (no native engine chaining over Implies)


def enabled(cfg=None) -> bool:
    return bool((cfg or rc.resolve())["pc_shadow"])


def atom_to_metta(atom, i):
    m = _NAME.match(atom.name)
    if not m or m.group(1) not in HEAD:
        return None
    s = min(1.0, max(0.0, float(atom.truth.strength))); c = min(0.99, max(0.0, float(atom.truth.confidence)))
    return "(: wm%d (%s %s %s) (STV %.4f %.4f))" % (i, HEAD[m.group(1)], m.group(2), m.group(3), s, c)


MAX_GOALS = 60
_FACTS_MEMO = {}
SP_HEADS = ("Inheritance", "Member", "Implies", "Similarity", "Evaluation")


def _cache_lookup(items, cache_dir=None, context=False, speaker=False):
    """item.id -> validated semparse atom strings (Track H cache), only for items that have a cached parse.
    context=True (Track O, flags key semparse_context): context parses in <cache_dir>/ctx1 win over the base cache."""
    from . import frozen_parse as _fp
    fz = _fp.store_from_env()
    if fz is not None:                    # t-2026-11-10: evaluation reads only the frozen store (strict, no fallback)
        st, pin, psha = fz
        return st.lookup(items, pin, psha, strict=False)
    try:
        from .parse_cache import ParseCache, CTX_VERSION
        c = ParseCache(cache_dir); ent = c.entries()
        if context:
            cd = os.path.join(c.d, CTX_VERSION)
            if os.path.isdir(cd):
                ent.update(ParseCache(cd).entries())
        if speaker:                       # Track Q: speaker-linked parses (spk1) win over base and ctx1
            from .parse_cache import SPK_VERSION
            sd = os.path.join(c.d, SPK_VERSION)
            if os.path.isdir(sd):
                ent.update(ParseCache(sd).entries())
    except Exception:
        return {}
    out = {}
    for it in items:
        try:
            a = c.atoms_for(it.content, ent)
        except Exception:
            a = None
        if a is not None:
            out[it.id] = a
    return out


# F7 design (Track P README 8cf5006, binding for P4): a narrowed Member class such as (Narrow pilot (Mod harbour))
# is named by a deterministic symbol plus a defining rule.  This is the design, not a stopgap.
def narrow_symbol(node) -> str:
    """Deterministic class symbol for a (Narrow base R...) class: <base>__nw_<sha1(form)[:10]>."""
    import hashlib
    from .semparse_adapter import to_str
    base = node[1] if isinstance(node[1], str) else narrow_symbol(node[1])
    return "%s__nw_%s" % (base, hashlib.sha1(to_str(node).encode()).hexdigest()[:10])


def _is_narrow(n) -> bool:
    return (isinstance(n, list) and len(n) >= 3 and n[0] == "Narrow"
            and (isinstance(n[1], str) or _is_narrow(n[1])))


def _name_narrow(node, defs):
    """F7 design: replace every narrowed Member class by its deterministic symbol; defs collects
    symbol -> (base symbol, narrow form) so each symbol gets its defining rule."""
    if isinstance(node, list):
        if len(node) == 3 and node[0] == "Member" and _is_narrow(node[2]):
            return ["Member", _name_narrow(node[1], defs), _narrow_to_sym(node[2], defs)]
        return [_name_narrow(x, defs) for x in node]
    return node


def _narrow_to_sym(n, defs):
    base = n[1] if isinstance(n[1], str) else _narrow_to_sym(n[1], defs)
    sym = narrow_symbol(n)
    defs.setdefault(sym, base)
    return sym


def narrow_defining_rules(defs):
    """F7 design: (Member $x <sym>) implies (Member $x <base>) for every named narrowed class."""
    return ["(: nwdef_%s (Implication (Member $x %s) (Member $x %s)) (CTV (STV 1.0 0.99) (STV 0.0 0.0)))"
            % (sym, sym, base) for sym, base in sorted(defs.items())]


def _forms(atom_strs, defs):
    from .semparse_adapter import split_toplevel
    for _src, node, err in split_toplevel("\n".join(atom_strs or [])):
        if err or not isinstance(node, list):
            continue
        if node and node[0] == "Interpretation" and len(node) == 3:
            node = node[2]
        if not (isinstance(node, list) and len(node) == 4 and node[0] == ":"):
            continue
        yield _name_narrow(node, defs)


def _derived_fact(it, live_ids):
    """F1 §3: (head, a, b, s, c) for a reasoner-admitted conclusion, from its provenance goal and engine STV; None
    if it has no usable provenance or any of its sources is no longer in the active set (sources withdrawn)."""
    pv = getattr(it, "provenance", None) or {}
    srcs = list(getattr(it, "derived_from", None) or [])
    if not srcs or any(s not in live_ids for s in srcs):
        return None
    if pv.get("polarity") == "negative":
        return None   # an "unlikely:" conclusion is not the goal fact
    m = re.match(r"^\((\w+) (\S+) (\S+)\)$", str(pv.get("goal") or ""))
    tv = pv.get("stv")
    if not m or m.group(1) not in SP_HEADS or not (isinstance(tv, (list, tuple)) and len(tv) == 2):
        return None
    try:
        sv, cv = min(1.0, max(0.0, float(tv[0]))), min(0.99, max(0.0, float(tv[1])))
    except (TypeError, ValueError):
        return None
    return (m.group(1), m.group(2), m.group(3), sv, cv)


def semparse_facts(atom_strs, defs=None):
    """Binary facts (head, a, b, s, c) from validated semparse atoms (Interpretation wrappers unwrapped).
    A narrowed Member class becomes its deterministic symbol (F7 design); defs (dict) receives the definitions."""
    defs = {} if defs is None else defs
    out = []
    for node in _forms(atom_strs, defs):
        c, tv = node[2], node[3]
        if (isinstance(c, list) and len(c) == 3 and c[0] in SP_HEADS and all(isinstance(x, str) for x in c[1:])
                and isinstance(tv, list) and len(tv) == 3):
            try:
                f = (c[0], c[1], c[2], float(tv[1]), float(tv[2]))
            except ValueError:
                continue
            if f not in out:
                out.append(f)
    return out


def _flat_member_rule(node) -> bool:
    """True if every Member atom in a rule names a symbol class (after Narrow naming)."""
    if isinstance(node, list):
        if len(node) == 3 and node[0] == "Member" and not isinstance(node[2], str):
            return False
        return all(_flat_member_rule(x) for x in node)
    return True


def semparse_rules(atom_strs, defs=None, nwdef=True):
    """P4: the parser's (: id (Implication P C) tv) rules, as MeTTa strings, for the shadow KB (Equivalence dropped).
    Narrowed classes are replaced by their deterministic symbols (F7 design) and every symbol seen (in rules
    or, via defs, in facts) gets its defining rule appended."""
    from .semparse_adapter import to_str
    defs = {} if defs is None else defs
    out = []
    for node in _forms(atom_strs, defs):
        if (isinstance(node[1], str) and isinstance(node[2], list) and len(node[2]) == 3
                and node[2][0] == "Implication" and _flat_member_rule(node[2])):
            # STOPGAP(upstream: PC-EQ1 Equivalence add rejected) P4 rev3 (review 2 finding 6): Equivalence is not passed through; PeTTaChainer bdae8d7e rejects it
            # (fact_without_free_variables), which would be a silent add failure.
            r = to_str(node)
            if r not in out:
                out.append(r)
    for r in (narrow_defining_rules(defs) if nwdef else []):   # P4 rev5: shadow_nwdef=False leaves them out (upstream R2)
        if r not in out:
            out.append(r)
    return out


_SCOPED_WITNESS = re.compile(r"^sk_[A-Za-z0-9_\-]*__i_[A-Za-z0-9_]+$")
SCOPED_WITNESS_GOALS = True     # P4 rev3: set from cfg shadow_scoped_witness_goals in build_snapshot


def is_skolem(term) -> bool:
    """Parser-invented placeholder entity (sk_* witness).  P4 rev3: a note-scoped witness sk_<x>__i_<note> is a
    real per-note entity, so it is not treated as a placeholder for goals while SCOPED_WITNESS_GOALS is on."""
    if not (isinstance(term, str) and term.startswith("sk_")):
        return False
    return not (SCOPED_WITNESS_GOALS and _SCOPED_WITNESS.match(term))


def goal_has_skolem(goal: str) -> bool:
    return any(is_skolem(t) for t in goal.strip("()").split()[1:])


def build_goals(rel, max_goals=None, skolem_goals=False):
    """2-step Inheritance / Implies chains plus Member x Inheritance joins, not already asserted.

    Goals about parser-invented placeholder entities (sk_*) are dropped unless skolem_goals=True: they are
    per-item witnesses ("some request"), so a conclusion about one is not a belief about anything nameable.
    The facts mentioning them stay in the KB (they can still support other chains)."""
    max_goals = int(max_goals or MAX_GOALS)
    have = {(h, a, b) for (h, a, b) in rel}
    by = {}
    for (h, a, b) in sorted(rel):
        by.setdefault((h, a), []).append(b)
    goals = []
    def add(t):
        g = "(%s %s %s)" % t
        if not skolem_goals and (is_skolem(t[1]) or is_skolem(t[2])):
            return
        if t not in have and t[1] != t[2] and g not in goals:
            goals.append(g)
    for (h, a, b) in sorted(rel):
        if h in TRANSITIVE:
            for c in by.get((h, b), []):
                add((h, a, c))
        if h == "Member":
            for c in by.get(("Inheritance", b), []):
                add(("Member", a, c))
    return goals[:max_goals]


# ── Track N: Design A goal ranking (docs/TRACK_M_GOALS.md) ─────────────────────────────────────────────
# hops = derivation steps (rule applications) behind a goal: a 2-fact chain (a->b->c, or Member x a + a->b) is
# 1 hop, a 3-fact chain is 2 hops, a 4-fact chain 3 hops.  Track M goals were all 1-hop.
GOAL_WEIGHTS = (2.0, 1.0, 1.0, 0.5)      # w_req, w_depth, w_info, w_sti
MAX_POOL = 5000
_TOK = re.compile(r"[a-z0-9]+")
_STOP = frozenset("a an the is are was were be been of to in on at by for from with and or not no it this that "
                  "what which who how why when where do does did can could should would will my your our me i you "
                  "we please about any some".split())


def _toks(text):
    return {t for t in _TOK.findall(str(text).lower()) if len(t) >= 2 and t not in _STOP}


def goal_pool(rel, max_hops=3, skolem_goals=False, max_pool=MAX_POOL):
    """All goals derivable by chains of up to max_hops derivation steps, not already asserted.
    -> {(head, a, c): (hops, [facts of the shortest chain])}.  Chains: Inheritance/Implies transitivity
    (a->b->...->d, same head) and Member x a + 1..max_hops Inheritance steps."""
    have = set(rel)
    by = {}
    for (h, a, b) in sorted(rel):
        by.setdefault((h, a), []).append(b)
    pool = {}

    def add(t, path):
        if not skolem_goals and (is_skolem(t[1]) or is_skolem(t[2])):
            return
        if t in have or t[1] == t[2]:
            return
        hops = len(path) - 1
        if t not in pool or hops < pool[t][0]:
            if t not in pool and len(pool) >= max_pool:
                return
            pool[t] = (hops, list(path))

    def walk(h_goal, h_step, x, node, path, seen):
        if len(path) - 1 >= max_hops:
            return
        for nxt in by.get((h_step, node), []):
            if nxt in seen:
                continue
            p2 = path + [(h_step, node, nxt)]
            add((h_goal, x, nxt), p2)
            walk(h_goal, h_step, x, nxt, p2, seen | {nxt})

    for (h, a, b) in sorted(rel):
        if h in TRANSITIVE:
            walk(h, h, a, b, [(h, a, b)], {a, b})
        elif h == "Member":
            walk("Member", "Inheritance", a, b, [(h, a, b)], {a, b})
    return pool


def _parse_rules(rule_strs):
    """P4 rev3: (id, [premise atoms], consequent) for parser/defining Implication rules whose premises are binary
    atoms over symbols/variables (a single atom or an And of them) and whose consequent is one binary atom.
    Other shapes (Not/Directive/Can consequents, function terms) cannot yield a nameable goal and are skipped."""
    from .semparse_adapter import split_toplevel
    out = []
    for _src, node, err in split_toplevel("\n".join(rule_strs or [])):
        if err or not (isinstance(node, list) and len(node) == 4 and node[0] == ":"):
            continue
        r = node[2]
        if not (isinstance(r, list) and len(r) == 3 and r[0] == "Implication"):
            continue
        prem, con = r[1], r[2]
        prems = prem[1:] if isinstance(prem, list) and prem and prem[0] == "And" else [prem]
        flat = lambda a: isinstance(a, list) and len(a) == 3 and all(isinstance(x, str) for x in a)
        if prems and all(flat(a) for a in prems) and flat(con):
            out.append((node[1], [tuple(a) for a in prems], tuple(con)))
    return out


def _match(prems, facts_by_head, env=None):
    env = env or {}
    if not prems:
        yield env; return
    h, a, b = prems[0]
    for (fa, fb) in facts_by_head.get(h, ()):
        e = dict(env); ok = True
        for pat, val in ((a, fa), (b, fb)):
            if pat.startswith("$"):
                if e.setdefault(pat, val) != val: ok = False
            elif pat != val:
                ok = False
        if ok:
            yield from _match(prems[1:], facts_by_head, e)


def rule_goal_pool(rel, rule_strs, max_hops=3, skolem_goals=False, max_pool=MAX_POOL, pool=None):
    """P4 rev3: goals from the parser's Implication rules (and the Narrow defining rules), forward-chained up to
    max_hops rule applications over the KB facts.  -> {(head, a, c): (hops, [chain])} merged into pool; a chain
    entry is a premise fact (head, a, b) or ("Rule", rule_id, "").  Goal kind is "rule" (vs fact-chain)."""
    pool = {} if pool is None else pool
    rules = _parse_rules(rule_strs)
    known = {t: (0, [t]) for t in rel}
    for _ in range(max(1, int(max_hops))):
        fbh = {}
        for (h, a, b) in known:
            fbh.setdefault(h, []).append((a, b))
        new = {}
        for rid, prems, con in rules:
            for env in _match(list(prems), fbh):
                t = (con[0],) + tuple(env.get(x, x) if x.startswith("$") else x for x in con[1:])
                if any(x.startswith("$") for x in t[1:]) or t in known or t in new:
                    continue
                ps = [tuple(env.get(x, x) if x.startswith("$") else x for x in p) for p in prems]
                hops = 1 + max(known[p][0] for p in ps)
                chain = [c for p in ps for c in known[p][1]] + [("Rule", rid, "")]
                new[t] = (hops, chain)
        if not new:
            break
        known.update(new)
        for t, (hops, chain) in new.items():
            if t in rel or t[1] == t[2] or hops > max_hops:
                continue
            if not skolem_goals and (is_skolem(t[1]) or is_skolem(t[2])):
                continue
            if t not in pool or hops < pool[t][0]:
                if t not in pool and len(pool) >= max_pool:
                    continue
                pool[t] = (hops, chain)
    return pool


def induction_goal_pool(rel, min_shared=3, skolem_goals=False, max_pool=MAX_POOL, pool=None):
    """t-2026-11-11 induction: (Inheritance A B) goals for class pairs that share >= min_shared Member instances
    and are not already related.  The engine answers them by implication-instance-fold over the Member facts
    (confidence grows ~0.001 per instance at the pins).  -> pool entry (1, [shared Member facts of A and B])."""
    pool = {} if pool is None else pool
    mem = {}
    for (h, x, c) in rel:
        if h == "Member":
            mem.setdefault(c, set()).add(x)
    for a in sorted(mem):
        for b in sorted(mem):
            if a == b:
                continue
            t = ("Inheritance", a, b)
            if t in rel or t in pool:
                continue
            if not skolem_goals and (is_skolem(a) or is_skolem(b)):
                continue
            if a.split("__nw_")[0] == b.split("__nw_")[0]:   # X vs X__nw_*: nwdef alias, definitional, not induction
                continue
            shared = sorted(mem[a] & mem[b])
            if len(shared) < max(1, int(min_shared)):
                continue
            if len(pool) >= max_pool:
                return pool
            pool[t] = (1, [f for x in shared for f in (("Member", x, a), ("Member", x, b))])
    return pool


def request_terms(facts_by_item, user_items, rel):
    """(entities, tokens) of the current user request: entities from the parse of source_type=user items plus
    their 1-hop KB neighbours; tokens from the request text (so an unparsed request still anchors by name)."""
    ents, toks = set(), set()
    for it in user_items:
        toks |= _toks(it.content)
        for (_h, x, y) in facts_by_item.get(it.id, []):
            ents |= {x, y}
    nb = set()
    for (_h, x, y) in rel:
        if x in ents: nb.add(y)
        if y in ents: nb.add(x)
    return ents | nb, toks


def _name_toks(term):
    return [t for t in str(term).lower().replace("-", "_").split("_") if t]


def rank_goals(pool, rel, req=(set(), set()), fact_sti=None, max_goals=None, min_hops=1, weights=GOAL_WEIGHTS):
    """Design A: score = w_req*overlap + w_depth*(hops-1) + w_info*info(category) + w_sti*STI(sources).
    -> [(goal, meta)] best first, at most max_goals, hops >= min_hops."""
    import math
    w_req, w_depth, w_info, w_sti = weights
    max_goals = int(max_goals or MAX_GOALS)
    ents, rtoks = req
    fact_sti = fact_sti or {}
    top_sti = max(fact_sti.values() or [0.0]) or 1.0
    # subjects per category: who is (asserted or derivably) a member/subtype of it
    subj, cat_n = set(), {}
    for (h, a, b) in list(rel) + list(pool):
        if h in ("Member", "Inheritance"):
            subj.add(a); cat_n.setdefault(b, set()).add(a)
    n_subj = max(len(subj), 2)
    out = []
    for (h, a, c), (hops, path) in pool.items():
        if hops < min_hops:
            continue
        if h in ("Member", "Inheritance"):
            echo = bool(set(_name_toks(c)) & set(_name_toks(a)))
            info = 0.0 if echo else -math.log(max(len(cat_n.get(c, ())), 1) / n_subj) / math.log(n_subj)
        else:
            echo, info = False, 1.0
        gt = set(_name_toks(a)) | set(_name_toks(c))
        ov = 1.0 if (a in ents or c in ents) else (len(gt & rtoks) / len(gt) if gt else 0.0)
        sti = max((fact_sti.get(f, 0.0) for f in path), default=0.0) / top_sti
        score = w_req * ov + w_depth * (hops - 1) + w_info * info + w_sti * sti
        g = "(%s %s %s)" % (h, a, c)
        out.append((g, {"score": round(score, 4), "hops": hops, "overlap": round(ov, 3), "info": round(info, 3),
                        "echo": echo, "sti": round(sti, 3), "chain": ["(%s %s %s)" % f for f in path]}))
    out.sort(key=lambda gm: (-gm[1]["score"], gm[0]))
    return out[:max_goals]


def _weights(v):
    try:
        w = tuple(float(x) for x in str(v).split(","))
        return w if len(w) == 4 else GOAL_WEIGHTS
    except (TypeError, ValueError):
        return GOAL_WEIGHTS


def build_snapshot(store, cycle=0, k=None, cfg=None):
    """-> dict spec.  Per item: cached semparse atoms (Track H) only.  Track K: no regex fallback - an item that has
    not been parsed yet contributes no facts this cycle (counted in unparsed_items)."""
    cfg = cfg or rc.resolve()
    k = int(k or cfg["shadow_k"])
    max_goals = int(cfg["shadow_max_goals"]); skolem_goals = bool(cfg["shadow_skolem_goals"])
    global SCOPED_WITNESS_GOALS
    SCOPED_WITNESS_GOALS = bool(cfg.get("shadow_scoped_witness_goals", True))
    all_items = store.get_active_set()
    items = all_items[:k]
    # F12 decision 2: a conclusion's sources are looked up in the whole memory store, not the top-k snapshot
    store_ids = getattr(store, "live_ids", None)
    store_ids = set(store_ids) if store_ids is not None else {it.id for it in all_items}
    if cfg.get("speaker_link"):
        cached = _cache_lookup(items, cfg["semparse_dir"], context=bool(cfg.get("semparse_context")), speaker=True)
    elif cfg.get("semparse_context"):
        cached = _cache_lookup(items, cfg["semparse_dir"], context=True)
    else:
        cached = _cache_lookup(items, cfg["semparse_dir"])
    name_rep = None
    if cfg.get("name_resolve"):           # P3 Deviation 6: named witnesses -> deterministic symbols, before the gate
        from .name_resolve import resolve as _nr
        name_rep = {}
        for iid in list(cached):
            cached[iid], name_rep[iid] = _nr(cached[iid])
    norm_rep = None
    if cfg.get("shadow_normalise", True):  # t-2026-11-10: every parser shape -> the reader's form; unrecognised counted
        from . import parse_normalise as _pn
        cached, _nrep = _pn.normalise_cached(cached, nwdef=bool(cfg.get("shadow_nwdef", True)))
        norm_rep = _pn.report_json(_nrep)
    metta, facts, n_sp, n_unparsed, i, n_rules = [], [], 0, 0, 0, 0
    src, fsrc, dsrc = {}, [], {}   # F1 §3: dsrc = wm label -> source item ids of a re-entered conclusion

    from . import parse_gate as _pg   # Track J: per-fact sanity rules before facts enter the KB
    gst = _pg.settings(cfg); gdec, lf = [], {}
    live_ids = store_ids
    n_derived, j = 0, 0
    for it in items:
        if getattr(it, "source_type", "") == "derived":   # F1 §3: a conclusion is never parsed; it enters the KB
            n_derived += 1                                 # with the engine's TV, only while all its sources are live
            fact = _derived_fact(it, live_ids)
            if fact is not None:
                h, x, y, sv, cv = fact
                lab = "wm%d" % j; j += 1
                metta.append("(: %s (%s %s %s) (STV %.4f %.4f))" % (lab, h, x, y, sv, cv))
                src[lab] = it.id; lf[lab] = "(%s %s %s)" % (h, x, y)
                facts.append(fact); fsrc.append([h, x, y, it.id]); dsrc[lab] = list(it.derived_from)
            continue
        if it.id in cached:
            n_sp += 1
            key = (it.id, len(cached[it.id]), hash(tuple(cached[it.id])))
            fs = _FACTS_MEMO.get(key)
            if fs is None:  # parsing cached atoms costs ~20 ms/item; cached entries are immutable, so memoise
                fs = semparse_facts(cached[it.id])
                if len(_FACTS_MEMO) > 4096:
                    _FACTS_MEMO.clear()
                _FACTS_MEMO[key] = fs
            fs, dec = _pg.gate_facts(fs, _pg.quantifiers(cached[it.id]), gst, it.id); gdec.extend(dec)
            facts.extend(fs); fsrc.extend([h, x, y, it.id] for (h, x, y, _s, _c) in fs)
            if cfg["shadow_full_kb"]:
                metta.extend(cached[it.id])
            else:  # only the binary facts the goals are built from: a 700-atom KB makes each query ~7-10 s
                for (h, x, y, sv, cv) in fs:
                    metta.append("(: sp%d (%s %s %s) (STV %.4f %.4f))" % (i, h, x, y, min(1.0, max(0.0, sv)), min(0.99, max(0.0, cv)))); src["sp%d" % i] = it.id; lf["sp%d" % i] = "(%s %s %s)" % (h, x, y); i += 1
                if cfg.get("shadow_rules", True):   # P4: the parser's Implication rules (flat Member classes only)
                    _d = {}; semparse_facts(cached[it.id], _d)   # F7 design: defining rules for fact classes too
                    for r in semparse_rules(cached[it.id], _d, nwdef=bool(cfg.get("shadow_nwdef", True))):
                        if r not in metta:
                            metta.append(r); n_rules += 1
            continue
        n_unparsed += 1   # Track K: no regex fallback; an item without cached semparse atoms adds no facts
    rel = {(h, a, b) for (h, a, b, _, _) in facts}
    goal_meta = None
    if cfg.get("shadow_goal_rank", True):   # Track N: Design A ranked pool (chains up to shadow_max_hops)
        fbi, fsti = {}, {}
        for (h, x, y, iid) in fsrc:
            fbi.setdefault(iid, []).append((h, x, y))
        sti_of = {it.id: float(getattr(getattr(it, "attention", None), "sti", 0.0) or 0.0) for it in items}
        for (h, x, y, iid) in fsrc:
            fsti[(h, x, y)] = max(fsti.get((h, x, y), 0.0), sti_of.get(iid, 0.0))
        users = [it for it in items if getattr(it, "source_type", "") == "user"]
        req = request_terms(fbi, users, rel)
        pool = goal_pool(rel, int(cfg.get("shadow_max_hops") or 3), skolem_goals)
        if cfg.get("shadow_rules", True):   # P4 rev3: parser Implication + defining rules also propose goals
            rule_goal_pool(rel, [a for a in metta if "(Implication" in a], int(cfg.get("shadow_max_hops") or 3),
                           skolem_goals, pool=pool)
        if cfg.get("shadow_induction", False):   # t-2026-11-11: induction goals (shared Member instances)
            induction_goal_pool(rel, int(cfg.get("shadow_induction_min") or 3), skolem_goals, pool=pool)
        ranked = rank_goals(pool, rel, req, fsti, max_goals, int(cfg.get("shadow_min_hops") or 1),
                            _weights(cfg.get("shadow_goal_weights")))
        goals = [g for g, _ in ranked]
        goal_meta = {g: m for g, m in ranked}
        rank_info = {"pool": len(pool), "user_items": len(users), "req_entities": len(req[0]),
                     "req_tokens": len(req[1]),
                     "hops": {str(h): sum(1 for _, m in ranked if m["hops"] == h) for h in (1, 2, 3)}}
    else:
        goals = build_goals(rel, max_goals, skolem_goals); rank_info = None
    return {"cycle": cycle, "ts": time.time(), "k": k, "items": len(items), "atoms": metta, "goals": goals,
            "semparse_items": n_sp, "unparsed_items": n_unparsed, "facts": len(facts), "rules": n_rules,
            "skolem_goals": skolem_goals, "goal_meta": goal_meta, "goal_rank": rank_info,
            "atom_src": src, "fact_src": fsrc, "label_fact": lf, "derived_src": dsrc, "derived_items": n_derived,
            "gate": dict(_pg.summary(gdec), on=gst["on"], decisions=gdec), "name_resolve": name_rep, "normalise": norm_rep}


def _cleanup_specs(out_dir, max_age=3600):
    for f in glob.glob(os.path.join(out_dir, "spec_c*.json")):
        try:
            if time.time() - os.path.getmtime(f) > max_age:
                os.unlink(f)
        except OSError:
            pass


def launch(spec, cfg=None, out_dir=None, module=None):
    """Write spec + worker config, start a detached niced worker, return its pid (or None if busy).  Never waits."""
    cfg = dict(cfg or rc.resolve())
    out_dir = out_dir or cfg["shadow_dir"]; cfg["shadow_dir"] = out_dir
    os.makedirs(out_dir, exist_ok=True)
    pidfile = os.path.join(out_dir, "worker.pid")
    if rc.busy(pidfile, WORKER_MAX_AGE):
        return None
    _cleanup_specs(out_dir)
    import tempfile, json
    fd, path = tempfile.mkstemp(prefix="spec_c%d_" % spec.get("cycle", 0), suffix=".json", dir=out_dir)
    with os.fdopen(fd, "w") as f:
        json.dump(spec, f)
    cpath = os.path.join(out_dir, "worker_config.json")
    rc.write_json_atomic(cpath, cfg)
    return rc.spawn_worker(cfg, module or WORKER_MODULE,
                           ["--spec", path, "--out", os.path.join(out_dir, "shadow.jsonl"), "--config", cpath], pidfile)


LAST_LAUNCH = "last_launch"    # stamp file in shadow_dir; its mtime is the last launch time (rate limit)


def rate_limited(cfg, now=None) -> bool:
    """True if a shadow worker was launched less than shadow_min_interval_s ago (0 = no limit)."""
    iv = float(cfg.get("shadow_min_interval_s") or 0)
    if iv <= 0:
        return False
    try:
        last = os.path.getmtime(os.path.join(cfg["shadow_dir"], LAST_LAUNCH))
    except OSError:
        return False
    now = time.time() if now is None else now
    return 0 <= now - last < iv


def _stamp(cfg):
    try:
        p = os.path.join(cfg["shadow_dir"], LAST_LAUNCH)
        with open(p, "w") as fh:
            fh.write("%.3f\n" % time.time())
    except OSError:
        pass


def maybe_launch_raw(raw, cycle=0, cfg=None, state_dir=None, source="cycle", force=False, live_ids=None):
    """Launch from raw top-K item dicts (raw_item() shape, active-set order).  Shared by the orchestrator hook and
    the automated fast path (which has only the state JSON, no engine).  Gates, cheapest first: flag, single-worker
    busy guard, rate limit (shadow_min_interval_s).  Returns pid or None; swallows every error."""
    try:
        cfg = cfg or rc.resolve(state_dir)
        if not (cfg["pc_shadow"] or force):     # force: reasoner=pettachainer|both needs the worker (Track I)
            return None
        if rc.busy(os.path.join(cfg["shadow_dir"], "worker.pid"), WORKER_MAX_AGE):
            return None  # skip before doing any work
        if rate_limited(cfg):
            return None
        k = int(cfg["shadow_k"])
        raw = list(raw or [])[:k]
        if not raw:
            return None
        spec = {"cycle": cycle, "ts": time.time(), "k": k, "raw_items": raw, "atoms": [], "goals": [],
                "source": source}
        if live_ids is not None:   # F12 decision 2: ids of every item in the memory store
            spec["live_ids"] = sorted(str(i) for i in live_ids)
        pid = launch(spec, cfg)
        if pid:
            _stamp(cfg)
        return pid
    except Exception:
        return None


def maybe_launch(store, cycle=0, state_dir=None, cfg=None, force=False):
    """Orchestrator hook.  Returns pid or None; swallows every error."""
    try:
        cfg = cfg or rc.resolve(state_dir)
        if not (cfg["pc_shadow"] or force):     # force: reasoner=pettachainer needs the worker (Track I)
            return None
        if rc.busy(os.path.join(cfg["shadow_dir"], "worker.pid"), WORKER_MAX_AGE) or rate_limited(cfg):
            return None  # skip before doing any work
        # cycle side only copies the top-K item fields; the worker builds the snapshot (cache read)
        k = int(cfg["shadow_k"])
        act = store.get_active_set()
        return maybe_launch_raw([raw_item(it) for it in act[:k]], cycle, cfg, force=force,
                                live_ids=[it.id for it in act])
    except Exception:
        return None


def raw_item_from_dict(d):
    """raw_item() from a persisted item dict (the state JSON the automated fast path reads)."""
    return {"id": d.get("id"), "content": d.get("content", ""), "sti": (d.get("attention") or {}).get("sti", 0.0),
            "tv_strength": d.get("tv_strength", 0.0), "tv_confidence": d.get("tv_confidence", 0.0),
            "source_type": d.get("source_type", "recalled"),
            "derived_from": list(d.get("derived_from") or []), "provenance": d.get("provenance"),   # F1 §3
            "origin_ts": float(d.get("origin_timestamp") or 0.0) or float(d.get("created_at") or 0.0)}   # Track R: age


def raw_item(it):
    return {"id": it.id, "content": it.content, "sti": it.attention.sti,
            "tv_strength": getattr(it, "tv_strength", 0.0), "tv_confidence": getattr(it, "tv_confidence", 0.0),
            "source_type": getattr(it, "source_type", "recalled"),
            "derived_from": list(getattr(it, "derived_from", None) or []), "provenance": getattr(it, "provenance", None),
            "origin_ts": float(getattr(it, "origin_timestamp", 0.0) or 0.0) or float(getattr(it, "created_at", 0.0) or 0.0)}


class _RawStore:
    """Minimal store over raw item dicts (already in active-set order), for building a snapshot in the worker."""
    def __init__(self, raw, live_ids=None):
        from types import SimpleNamespace as NS
        self.live_ids = set(live_ids) if live_ids is not None else None   # F12 decision 2: whole-store ids
        self._items = [NS(id=r["id"], content=r["content"], attention=NS(sti=r.get("sti", 0.0)),
                          tv_strength=r.get("tv_strength", 0.0), tv_confidence=r.get("tv_confidence", 0.0),
                          source_type=r.get("source_type", "recalled"), derived_from=list(r.get("derived_from") or []),
                          provenance=r.get("provenance")) for r in raw]
    def get_active_set(self):
        return list(self._items)


def snapshot_from_raw(spec, cfg=None):
    """Worker side: turn a raw spec (from maybe_launch) into a full spec."""
    full = build_snapshot(_RawStore(spec["raw_items"], spec.get("live_ids")), spec.get("cycle", 0), spec.get("k"), cfg)
    full["source"] = spec.get("source")
    full["ts"] = spec.get("ts", full["ts"]); full["build_s"] = round(time.time() - full["ts"], 3)
    return full
