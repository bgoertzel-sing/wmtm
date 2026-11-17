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


def plan(tdir, notes, kb_once=True, rules=True, catalog=None, note_labels=True, extra=False):
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
        recs = B.block_records(prior, catalog)
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
                m["statements"] += atom(st)
                lab, fact = _label_fact(st)
                if lab and note_labels:   # render-master-goals: label -> source note, like the legacy atom_src
                    meta["atom_src"].setdefault(lab, nid); meta["label_fact"].setdefault(lab, fact)
            for d in low["definitions"]:
                if atom(d): m["definitions"] += 1
                else: m["definitions_shared"] += 1
        meta["shared_definitions"] += m["definitions_shared"]
        meta["notes"][nid] = m
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
