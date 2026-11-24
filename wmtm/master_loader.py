"""master-adopt-v2: load sentence-mode parses the way semantic-parsing-hitl 24e37182 templates/README.md says
(upstream PeTTaChainer master recipe).  Order, which matters on that engine:
  (1) once per KB: declare tmpl.lower.predicates("pettachainer-master") positive-only;
  (2) the "(: ..." lines of generated/seeded_rules.pettachainer-master.metta;
  (3) per note, per sentence (tmpl.blocks.block_records): lower(rec, "pettachainer-master", symbols=names),
      declare low["predicates"] BEFORE that sentence's statements, then load statements + definitions.
Our name table (``names_for``): a named individual (Name sym "Label") with one bearer in its note gets slug(label),
shared across notes; every other sk_ symbol gets a per-note suffix so two notes' witnesses stay apart.  A definition
(kind__/by_) two notes share keeps its own name and is loaded once (a restatement, not new evidence).
Pure planning: ``plan`` returns the ordered ops [("pred", name) | ("atom", text)]; ``apply`` runs them on a chainer.
Upstream code is imported, never edited."""
from __future__ import annotations
import os, re, sys

from .name_resolve import slug


def _tmpl(tdir):
    tdir = os.path.expanduser(tdir)
    if tdir not in sys.path:
        sys.path.insert(0, tdir)
    from tmpl import lower as L, blocks as B, catalog as CAT   # noqa: E402 (upstream, MIT)
    return L, B, CAT


def seeded_rules(tdir):
    with open(os.path.join(os.path.expanduser(tdir), "generated", "seeded_rules.pettachainer-master.metta"),
              encoding="utf-8") as fh:
        return [ln.strip() for ln in fh if ln.strip().startswith("(:")]


EXTRA_RULES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules", "extra_rules.pettachainer-master.metta")


def extra_rules(path=None):
    """t-2026-11-17-wmtm-extra-rules-v2: the "(: ..." lines of wmtm/rules/extra_rules.pettachainer-master.metta,
    loaded after the seeded master rules when shadow_extra_rules is on (default off)."""
    with open(path or EXTRA_RULES, encoding="utf-8") as fh:
        return [ln.strip() for ln in fh if ln.strip().startswith("(:")]


def _syms(term):
    if isinstance(term, list):
        for x in term:
            yield from _syms(x)
    elif isinstance(term, str):
        yield term


def names_for(note_id, records):
    """-> symbols table for one note's records (all sentences together)."""
    labels = {}
    for r in records:
        t = r["term"]
        if isinstance(t, list) and len(t) == 3 and t[0] == "Name" and isinstance(t[1], str):
            labels.setdefault(t[1], str(t[2]))
    by = {}
    for sym, lab in labels.items():
        by.setdefault(slug(lab), []).append(sym)
    suffix = "__" + re.sub(r"[^A-Za-z0-9]", "_", note_id)
    out = {}
    for base, syms in by.items():
        if len(syms) == 1:
            out[syms[0]] = base
    for r in records:
        for s in _syms(r["term"]):
            if s.startswith("sk_") and s not in out:
                out[s] = s + suffix
    return out


def _note_label(stmt, suffix):
    """Review 1 F3: the recipe's per-sentence labels (s1_x1_member, ...) repeat across notes, so a proof label
    could not say which note it came from.  Give each statement label the note suffix (symbols already have it)."""
    m = re.match(r"\(: (\S+) ", stmt)
    return stmt if not m else "(: " + m.group(1) + suffix + stmt[m.end() - 1:]


def _label_fact(stmt):
    """'(: L (H a b) (STV ..))' -> (L, '(H a b)'); (None, None) if stmt is not a labelled statement.
    t-2026-11-14-wmtm-render-master-goals: plan() records label -> note id (meta atom_src) and label -> fact
    (meta label_fact) so the spec carries the same maps as the legacy path and sources_for/proof_facts find them."""
    m = re.match(r"\(: (\S+) ", stmt or "")
    if not m:
        return None, None
    from .semparse_adapter import split_toplevel, to_str
    try:
        r = list(split_toplevel(stmt))
        n = r[0][1] if r and not r[0][2] else None
    except Exception:
        n = None
    if not (isinstance(n, list) and len(n) >= 3):
        return m.group(1), None
    return m.group(1), to_str(n[2])


def plan(tdir, notes, kb_once=True, rules=True, catalog=None, note_labels=True, extra=False, label_replace=False,
         reference_times=None):
    """notes: [(note_id, prior)] with prior = tmpl.blocks.walk(...)[0] for that note.
    -> (ops, meta).  meta: counts and, per note, sentences ok/malformed, predicates, statements, definitions."""
    L, B, CAT = _tmpl(tdir)
    catalog = catalog or CAT.load()
    ops, seen_pred, seen_atom = [], set(), set()
    meta = {"kb_predicates": 0, "rules": 0, "notes": {}, "shared_definitions": 0, "atom_src": {}, "label_fact": {}}
    def pred(n):
        if n not in seen_pred:
            seen_pred.add(n); ops.append(("pred", n)); return True
        return False
    def atom(a):
        if a not in seen_atom:
            seen_atom.add(a); ops.append(("atom", a)); return True
        return False
    lab_at = {}   # t-2026-11-17-wmtm-steps-3-5 step 4: statement label -> index in ops (label_replace only)
    if label_replace:
        meta["label_replaced"] = 0
    if kb_once:
        for n in L.predicates(L.MASTER):
            meta["kb_predicates"] += pred(n)
    if rules:
        for r in seeded_rules(tdir):
            meta["rules"] += atom(r)
    if extra:   # t-2026-11-17-wmtm-extra-rules-v2: after the seeded rules, before notes; meta key only when on
        meta["extra_rules"] = 0
        for r in extra_rules():
            meta["extra_rules"] += atom(r)
    for nid, prior in notes:
        lab_at.clear()   # step 4: a label repeats only within one note's sentence records; never replace across notes
        rt = (reference_times or {}).get(nid)   # t-2026-11-17-wmtm-steps-3-5 step 5: the note's date anchors @now
        recs = B.block_records(prior, catalog, rt) if rt else B.block_records(prior, catalog)
        allrec = [x for rec in recs for x in rec.get("records") or []]
        names = names_for(nid, allrec)
        suffix = "__" + re.sub(r"[^A-Za-z0-9]", "_", nid)
        m = {"sentences": len(recs), "malformed": sum(r["status"] != "ok" for r in recs), "predicates": 0,
             "statements": 0, "definitions": 0, "definitions_shared": 0, "names": sum(not v.startswith("sk_") for v in names.values())}
        for rec in recs:
            if rec["status"] != "ok" or rec.get("kind") == "question":
                continue
            low = L.lower({"records": rec["records"], "types": rec["types"], "functions": rec["functions"]},
                          L.MASTER, symbols=names)
            for n in low["predicates"]:                 # BEFORE this sentence's statements
                m["predicates"] += pred(n)
            for s in low["statements"]:
                st = _note_label(s, suffix) if note_labels else s
                lab, fact = _label_fact(st)
                if label_replace and lab and lab in lab_at and ops[lab_at[lab]] != ("atom", st):
                    # sph Man Hin 2026-11-17 (3): a re-issued statement under a repeated label (revision-needed)
                    # replaces the earlier one: drop the earlier op, load the later at this point (after its predicates)
                    old = ops[lab_at[lab]][1]
                    ops[lab_at[lab]] = None; seen_atom.discard(old)
                    meta["atom_src"].pop(lab, None); meta["label_fact"].pop(lab, None)
                    meta["label_replaced"] += 1
                added = atom(st)
                m["statements"] += added
                if label_replace and lab and added:
                    lab_at[lab] = len(ops) - 1
                if lab and note_labels:   # render-master-goals: label -> source note, like the legacy atom_src
                    meta["atom_src"].setdefault(lab, nid); meta["label_fact"].setdefault(lab, fact)
            for d in low["definitions"]:
                if atom(d): m["definitions"] += 1
                else: m["definitions_shared"] += 1
        meta["shared_definitions"] += m["definitions_shared"]
        meta["notes"][nid] = m
    if label_replace:
        ops[:] = [o for o in ops if o is not None]
    meta["ops"] = len(ops)
    return ops, meta


def spec_maps(ops, note_ids):
    """-> {"atom_src": {label: note id}, "label_fact": {label: fact}} from planned ops, for specs written before plan()
    recorded them (e.g. the stored master-adopt-v2 B specs).  A statement label ends in __<sanitised note id>; it maps to
    the one note id in note_ids with that sanitised form.  Seeded rule / pole labels carry no note suffix: no source."""
    by_suffix = {"__" + re.sub(r"[^A-Za-z0-9]", "_", n): n for n in note_ids}
    src, lf = {}, {}
    for kind, x in ops or []:
        if kind != "atom":
            continue
        lab, fact = _label_fact(x)
        if not lab:
            continue
        for suf, nid in by_suffix.items():
            if lab.endswith(suf):
                src.setdefault(lab, nid)
                if fact:
                    lf.setdefault(lab, fact)
                break
    return {"atom_src": src, "label_fact": lf}


def apply(h, ops):
    """Run planned ops on a PeTTaChainer; -> (pred_fail, add_fail)."""
    pf = af = 0
    for kind, x in ops:
        try:
            h.set_positive_only_predicate(x) if kind == "pred" else h.add_atom(x)
        except Exception:
            if kind == "pred": pf += 1
            else: af += 1
    return pf, af


def _node(s):
    from .semparse_adapter import split_toplevel
    try:
        r = list(split_toplevel(s))
    except Exception:
        return None
    return r[0][1] if r and not r[0][2] else None


def _unify(p, f, env):
    if isinstance(p, str) and p.startswith("$"):
        if p in env:
            return env if env[p] == f else None
        e = dict(env); e[p] = f
        return e
    if isinstance(p, list):
        if not isinstance(f, list) or len(p) != len(f):
            return None
        for x, y in zip(p, f):
            env = _unify(x, y, env)
            if env is None:
                return None
        return env
    return env if p == f else None


def _subst(t, env):
    if isinstance(t, list):
        return [_subst(x, env) for x in t]
    return env.get(t, t) if isinstance(t, str) else t


def _ground(t):
    if isinstance(t, list):
        return all(_ground(x) for x in t)
    return not (isinstance(t, str) and t.startswith("$"))


_NOTE_SFX = re.compile(r"__ep_note_\d{8}T\d{6}Z")


def _one_note(env):
    """True when the bound symbols carry at most one distinct note suffix (named individuals carry none)."""
    seen = set()
    for v in env.values():
        for t in _syms(v):
            seen.update(_NOTE_SFX.findall(t))
    return len(seen) <= 1


def rule_goals(ops, rule_atoms, max_envs=200, scoped=()):
    """t-2026-11-15-wmtm-master-shadow-wiring: the goal builder of the master-adopt-v2 mkspec.py, moved here.
    Goals = ground conclusions of the seeded master rules whose premises match loaded statements (forward
    instantiation, one step), deduped, minus conclusions already stated.  -> ({goal: rule id}, {rule id: count}).
    t-2026-11-17-wmtm-extra-rules-v2: scoped = rule ids (the extra rules) whose goals are kept only when their
    bindings come from one note; seeded rules are never affected."""
    from .semparse_adapter import to_str
    rule_set = set(rule_atoms)
    rules, facts = {}, []
    for k, a in ops:
        if k != "atom":
            continue
        n = _node(a)
        if not (isinstance(n, list) and len(n) == 4):
            continue
        if a in rule_set and isinstance(n[2], list) and n[2][0] in ("Implication", "BiImplication"):
            rules[n[1]] = n[2]
        elif isinstance(n[2], list):
            facts.append(n[2])
    by_head = {}
    for f in facts:
        by_head.setdefault(f[0] if f and isinstance(f[0], str) else None, []).append(f)

    def matches(prem, env):
        ps = prem[1:] if isinstance(prem, list) and prem and prem[0] == "And" else [prem]
        envs = [env]
        for p in ps:
            nxt = []
            for e in envs:
                for f in by_head.get(p[0] if isinstance(p, list) else None, []):
                    r = _unify(p, f, e)
                    if r is not None:
                        nxt.append(r)
            envs = nxt[:max_envs]
        return envs

    stated = {to_str(f) for f in facts}
    goals, per_rule = {}, {}
    for rid, r in rules.items():
        pairs = [(r[1], r[2])] + ([(r[2], r[1])] if r[0] == "BiImplication" else [])
        for prem, concl in pairs:
            for e in matches(prem, {}):
                if rid in scoped and not _one_note(e):
                    continue
                c = _subst(concl, e)
                if not _ground(c):
                    continue
                g = to_str(c)
                if g in stated or g in goals:
                    continue
                goals[g] = rid
                per_rule[rid] = per_rule.get(rid, 0) + 1
    return goals, per_rule


CHAIN_INH_MEMBER = "chain_inh_member"     # (Member x A) + (Inheritance A B) -> (Member x B)
CHAIN_INH_TRANS = "chain_inh_trans"       # (Inheritance A B) + (Inheritance B C) -> (Inheritance A C)


_NOTE_TS = re.compile(r"\d{8}T\d{6}Z")


def _notes_of(t):
    return frozenset(_NOTE_TS.search(n).group(0) for s_ in _syms(t) for n in _NOTE_SFX.findall(s_))


def _meet(h, th):
    """Note scope of a combination: None = free (shared premise); else the notes every premise so far belongs to."""
    if h is None:
        return th
    if th is None:
        return h
    return h & th


def chain_goals(ops, rule_atoms, k=2, scoped=(), max_per_note=30, budget_s=10.0, max_envs=200, note_src=None, trace=None, no_coref=False):
    """t-2026-11-24-wmtm-r02-chaining (flag shadow_chain_k, default 0 = off): multi-step forward goal generation.
    Step 1 is rule_goals (unchanged).  Steps 2..k treat every ground conclusion of the step before as a usable
    premise and apply the same rules again, plus two class-link rules: (Member x A),(Inheritance A B) -> (Member x B)
    and (Inheritance A B),(Inheritance B C) -> (Inheritance A C).  A new goal must use at least one conclusion of the
    step just before (semi-naive), so a cycle stops once nothing new appears.
    Note scope ("home" of a fact): the note suffix in its symbols if any; else the notes that state it (note_src =
    plan()'s label -> note id, so a fact without a suffix but stated in one note still belongs to that note); a fact
    stated in no note and carrying no suffix (definitions, kind__ class links, rules' background facts) is free.  A fact
    stated in several notes may join any of them (that is the shared premise).  A combination's home is the
    intersection over all premises used; empty = refused and counted (cross_note_refused).  A derived fact keeps that
    home.  So a chain never links two notes unless a premise is shared.
    Caps: at most max_per_note new chained goals per note (free goals count under note ""), wall budget_s for
    steps 2..k together; whatever hits a cap is counted, never silently dropped.
    -> ({goal: "chain<d>:" + rule id}, stats) (no atom text)."""
    import time as _t
    from .semparse_adapter import to_str
    t0 = _t.monotonic()
    rule_set = set(rule_atoms)
    src = {}
    for lab, nid in (note_src or {}).items():
        m = _NOTE_TS.search(str(nid))
        if m:
            src[lab] = m.group(0)
    rules, facts = {}, []
    for kk, a in ops:
        if kk != "atom":
            continue
        n = _node(a)
        if not (isinstance(n, list) and len(n) == 4):
            continue
        if a in rule_set and isinstance(n[2], list) and n[2][0] in ("Implication", "BiImplication"):
            rules[n[1]] = n[2]
        elif isinstance(n[2], list):
            facts.append((n[2], n[1]))
    rules[CHAIN_INH_MEMBER] = ["Implication", ["And", ["Member", "$cx", "$cA"], ["Inheritance", "$cA", "$cB"]],
                               ["Member", "$cx", "$cB"]]
    rules[CHAIN_INH_TRANS] = ["Implication", ["And", ["Inheritance", "$cA", "$cB"], ["Inheritance", "$cB", "$cC"]],
                              ["Inheritance", "$cA", "$cC"]]
    pairs = []
    for rid, r in rules.items():
        pairs.append((rid, r[1], r[2]))
        if r[0] == "BiImplication":
            pairs.append((rid, r[2], r[1]))
    known = {}                  # str -> (term, home or None, depth)
    for f, lab in facts:
        sf = _notes_of(f)
        h = sf if sf else (frozenset([src[lab]]) if lab in src else None)
        g = to_str(f)
        if g in known:
            oh = known[g][1]
            h = None if (oh is None or h is None) else (oh | h)   # stated in several notes: shared by them
        known[g] = (f, h, 0)
    st = {"k": k, "max_per_note": max_per_note, "budget_s": budget_s, "rules": len(rules), "steps": 0,
          "per_step": {}, "cross_note_refused": 0, "capped": 0, "budget_hit": False, "envs_cut": 0,
          "inh_member": 0, "inh_trans": 0, "goals": 0, "per_note_max": 0, "no_coref": bool(no_coref), "coref_gated": 0,
          "facts_free": sum(1 for v in known.values() if v[1] is None),
          "facts_src_only": sum(1 for f, lab in facts if not _notes_of(f) and lab in src)}
    FREE = object()

    def step(depth):
        by_head = {}
        for g, (t, h, d) in known.items():
            by_head.setdefault(t[0] if t and isinstance(t[0], str) else None, []).append((t, h, d))
        out = {}
        for rid, prem, concl in pairs:
            ps = prem[1:] if isinstance(prem, list) and prem and prem[0] == "And" else [prem]
            if no_coref and depth >= 2 and any(isinstance(p, list) and p and p[0] == "Coref" for p in ps):
                st["coref_gated"] += 1     # gate: a chained step never reads a coreference link
                continue
            envs = [({}, FREE, -1, ())]      # env, home so far (FREE = no scoped premise yet), max depth used, premises
            for p in ps:
                nxt = []
                for e, h, md, pr in envs:
                    for t, th, d in by_head.get(p[0] if isinstance(p, list) else None, []):
                        r = _unify(p, t, e)
                        if r is not None:
                            nxt.append((r, _meet(None if h is FREE else h, th) if not (h is FREE and th is None) else FREE,
                                        max(md, d), pr + (t,) if trace is not None else pr))
                if len(nxt) > max_envs:
                    st["envs_cut"] += len(nxt) - max_envs
                envs = nxt[:max_envs]
            for e, h, md, pr in envs:
                if md != depth - 1:                  # semi-naive: must use a conclusion of the step before
                    continue
                h = None if h is FREE else h
                if h is not None and not h:
                    st["cross_note_refused"] += 1
                    continue
                if rid in scoped and not _one_note(e):
                    continue
                c = _subst(concl, e)
                if not _ground(c):
                    continue
                g = to_str(c)
                if g in known or g in out:
                    continue
                out[g] = (c, h, depth, rid)
                if trace is not None:
                    trace[g] = (rid, [to_str(x) for x in pr])
        return out

    def keep(g, h, d, rid, goals, per_note):
        note = min(h) if h else ""
        if per_note.get(note, 0) >= max_per_note:
            st["capped"] += 1
            return
        per_note[note] = per_note.get(note, 0) + 1
        goals[g] = "chain%d:%s" % (d, rid)
        st["inh_member"] += rid == CHAIN_INH_MEMBER
        st["inh_trans"] += rid == CHAIN_INH_TRANS

    first = step(1)
    for g, (c, h, d, rid) in first.items():
        known[g] = (c, h, 1)
    goals, per_note = {}, {}
    for depth in range(2, int(k) + 1):
        if _t.monotonic() - t0 > budget_s:
            st["budget_hit"] = True
            break
        new = step(depth)
        st["steps"] = depth
        st["per_step"][str(depth)] = len(new)
        if not new:
            break
        for g, (c, h, d, rid) in new.items():
            known[g] = (c, h, d)
            keep(g, h, d, rid, goals, per_note)
    # class-link conclusions of step 1 are new to the one-step builder too: keep them (depth 1)
    for g, (c, h, d, rid) in first.items():
        if rid in (CHAIN_INH_MEMBER, CHAIN_INH_TRANS) and g not in goals:
            keep(g, h, 1, rid, goals, per_note)
    st["goals"] = len(goals)
    st["per_note_max"] = max(per_note.values()) if per_note else 0
    st["elapsed_s"] = round(_t.monotonic() - t0, 3)
    return goals, st


def note_impl_goals(ops, rule_atoms, note_labels, max_envs=200):
    """t-2026-11-17-wmtm-steps-3-5, carried over from t-2026-11-17-wmtm-note-implication-goals-v2 (flag shadow_note_impl_goals, default off): goals from Implication
    atoms a note states (label in note_labels, i.e. atom_src; never a seeded/extra rule).  For each such atom, the
    conclusion becomes a goal when its premise matches loaded statements (all conjuncts; variables bound by matching,
    one step), minus conclusions already stated.  The atom itself stays in the KB with its STV as loaded.
    -> ({goal: "nimpl:" + label}, stats) where stats counts shapes and outcomes (no atom text)."""
    from .semparse_adapter import to_str
    rule_set, labels = set(rule_atoms), set(note_labels)
    nimpl, facts = {}, []
    for k, a in ops:
        if k != "atom" or a in rule_set:
            continue
        n = _node(a)
        if not (isinstance(n, list) and len(n) == 4 and isinstance(n[2], list)):
            continue
        if n[2][0] in ("Implication", "BiImplication") and n[1] in labels:
            nimpl[n[1]] = n[2]
        else:
            facts.append(n[2])
    by_head = {}
    for f in facts:
        by_head.setdefault(f[0] if f and isinstance(f[0], str) else None, []).append(f)
    stated = {to_str(f) for f in facts}
    st = {"note_impl": len(nimpl), "ground": 0, "with_vars": 0, "bi": 0, "and_premise": 0, "premise_in_kb": 0,
          "premise_missing": 0, "concl_not_ground": 0, "cross_note": 0, "concl_stated": 0, "dup_goal": 0, "goals": 0,
          "impl_with_goal": 0, "premise_shape": {}, "concl_shape": {}}

    def shape(t):
        return t[0] if isinstance(t, list) and t and isinstance(t[0], str) else "other"

    def matches(prem):
        ps = prem[1:] if isinstance(prem, list) and prem and prem[0] == "And" else [prem]
        envs = [{}]
        for p in ps:
            nxt = []
            for e in envs:
                for f in by_head.get(p[0] if isinstance(p, list) and p else None, []):
                    r = _unify(p, f, e)
                    if r is not None:
                        nxt.append(r)
            envs = nxt[:max_envs]
        return envs

    goals = {}
    for lab, r in nimpl.items():
        st["ground" if _ground(r) else "with_vars"] += 1
        st["bi"] += r[0] == "BiImplication"
        pairs = [(r[1], r[2])] + ([(r[2], r[1])] if r[0] == "BiImplication" else [])
        got = 0
        for prem, concl in pairs:
            st["and_premise"] += isinstance(prem, list) and bool(prem) and prem[0] == "And"
            st["premise_shape"][shape(prem)] = st["premise_shape"].get(shape(prem), 0) + 1
            st["concl_shape"][shape(concl)] = st["concl_shape"].get(shape(concl), 0) + 1
            envs = matches(prem)
            if not envs:
                st["premise_missing"] += 1
                continue
            st["premise_in_kb"] += 1
            own = set(_NOTE_SFX.findall(lab))
            for e in envs:
                c = _subst(concl, e)
                if not _ground(c):
                    st["concl_not_ground"] += 1
                    continue
                # v2: keep a binding only when every bound note suffix is the implication's own note
                seen = {x for v in e.values() for t in _syms(v) for x in _NOTE_SFX.findall(t)}
                if seen - own:
                    st["cross_note"] += 1
                    continue
                g = to_str(c)
                if g in stated:
                    st["concl_stated"] += 1
                    continue
                if g in goals:
                    st["dup_goal"] += 1
                    continue
                goals[g] = "nimpl:" + lab
                got += 1
        st["goals"] += got
        st["impl_with_goal"] += got > 0
    return goals, st


_ENTITY_ROLES = ("Member", "Agent", "Patient", "Theme", "Bearer", "Name")


def note_impl_premise_goals(ops, rule_atoms, note_labels, max_cands=8):
    """t-2026-11-17-wmtm-impl-premise-proving step 1 (flag shadow_note_impl_premise, default off).  For a note-stated
    Implication/BiImplication whose premise does NOT match its OWN note's statements literally (v2: facts
    from other notes never count, so a premise stated only in another note does not block the goal), still ask the conclusion,
    instantiated for candidate entities of the SAME note, and leave the premise to PeTTaChainer.
    Candidates: entity arguments (first arg of Member/Name, second of Agent/Patient/Theme/Bearer) of statements whose
    label carries the implication's own note suffix (never another note's; named individuals only when stated in this
    note).  Cap: per implication at most max_cands candidates, ranked by how many of the premise's constant symbols
    (classes, predicates) the entity's own-note statements mention, ties by first appearance; entities with score 0
    are not candidates.  Only conclusions whose unbound variables are exactly one ($x-like) are built; more counted.
    -> ({goal: "nimplp:" + label}, stats) (no atom text)."""
    from .semparse_adapter import to_str
    rule_set, labels = set(rule_atoms), set(note_labels)
    nimpl, facts, own_facts = {}, [], {}
    for k, a in ops:
        if k != "atom" or a in rule_set:
            continue
        n = _node(a)
        if not (isinstance(n, list) and len(n) == 4 and isinstance(n[2], list)):
            continue
        if n[2][0] in ("Implication", "BiImplication") and n[1] in labels:
            nimpl[n[1]] = n[2]
            continue
        facts.append(n[2])
        for sfx in set(_NOTE_SFX.findall(n[1])):
            own_facts.setdefault(sfx, []).append(n[2])
    stated = {to_str(f) for f in facts}
    st = {"note_impl": len(nimpl), "premise_literal": 0, "premise_not_literal": 0, "no_note": 0, "multi_var_concl": 0,
          "no_var_concl": 0, "candidates": 0, "capped": 0, "concl_stated": 0, "goals": 0, "impl_with_goal": 0}

    def literal(prem, own_by_head):
        """True when the premise matches facts of the implication's OWN note literally (v2: never another note's)."""
        ps = prem[1:] if isinstance(prem, list) and prem and prem[0] == "And" else [prem]
        envs = [{}]
        for p in ps:
            envs = [r for e in envs for f in own_by_head.get(p[0] if isinstance(p, list) and p else None, [])
                    for r in [_unify(p, f, e)] if r is not None][:200]
            if not envs:
                return False
        return True

    def ents(fs):
        out = []
        for f in fs:
            if not (isinstance(f, list) and len(f) >= 3 and f[0] in _ENTITY_ROLES):
                continue
            x = f[1] if f[0] in ("Member", "Name") else f[2]
            if isinstance(x, str) and not x.startswith("$") and x not in out:
                out.append(x)
        return out

    goals = {}
    for lab, r in nimpl.items():
        sfx = set(_NOTE_SFX.findall(lab))
        if len(sfx) != 1:
            st["no_note"] += 1
            continue
        fs = own_facts.get(next(iter(sfx)), [])
        own_by_head = {}
        for f in fs:
            own_by_head.setdefault(f[0] if f and isinstance(f[0], str) else None, []).append(f)
        pairs = [(r[1], r[2])] + ([(r[2], r[1])] if r[0] == "BiImplication" else [])
        got = 0
        for prem, concl in pairs:
            if literal(prem, own_by_head):
                st["premise_literal"] += 1     # the one-step builder (note_impl_goals) covers it
                continue
            st["premise_not_literal"] += 1
            cv = sorted({t for t in _syms(concl) if t.startswith("$")})
            if not cv:
                st["no_var_concl"] += 1
                continue
            if len(cv) > 1:
                st["multi_var_concl"] += 1
                continue
            consts = {t for t in _syms(prem) if not t.startswith("$")} - {"And", "Member", "Agent", "Patient",
                                                                            "Theme", "Bearer", "Inheritance", "thing"}
            scored = []
            for i, e in enumerate(ents(fs)):
                mine = [f for f in fs if e in _syms(f)]
                sc = len(consts & {t for f in mine for t in _syms(f)})
                if sc:
                    scored.append((-sc, i, e))
            scored.sort()
            st["capped"] += max(0, len(scored) - max_cands)
            for _, _, e in scored[:max_cands]:
                st["candidates"] += 1
                g = to_str(_subst(concl, {cv[0]: e}))
                if g in stated:
                    st["concl_stated"] += 1
                    continue
                if g not in goals:
                    goals[g] = "nimplp:" + lab
                    got += 1
        st["goals"] += got
        st["impl_with_goal"] += got > 0
    return goals, st


def notes_from_parsed(tdir, parsed_path, note_ids):
    """-> ([(note_id, prior)], {"complete": n, "incomplete": [note ids], "absent": [note ids]}) from a cached
    sentence-mode parsed.jsonl (rows carry id/dataset/doc/sent next to the reply).  Reads the cache only: no parse
    calls.  A note is planned only when every sentence has a good reply made under the right context (blocks.walk)."""
    import json as _json
    L, B, CAT = _tmpl(tdir)
    want = list(dict.fromkeys(note_ids))
    rows, seen = [], set()
    if parsed_path and os.path.exists(parsed_path):
        with open(parsed_path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                r = _json.loads(line)
                if r.get("id") in seen:
                    continue
                seen.add(r["id"])
                rows.append({k: v for k, v in r.items() if k != "reply"})
    rep = B.read_replies(parsed_path) if parsed_path else {}
    blocks = {}
    for b in B.blocks_of(rows):
        blocks.setdefault(b[0].get("doc") or b[0]["id"], b)
    notes, info = [], {"complete": 0, "incomplete": [], "absent": []}
    wset = set(want)
    info["absent"] = [nid for nid in want if nid not in blocks]
    # cache (block) order, not store order: the load order must not depend on how the store lists its items
    for nid, b in blocks.items():
        if nid not in wset:
            continue
        prior, nxt = B.walk(b, rep)
        if nxt is None:
            notes.append((nid, prior)); info["complete"] += 1
        else:
            info["incomplete"].append(nid)
    return notes, info
