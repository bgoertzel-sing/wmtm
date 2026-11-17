"""note_impl_goals as on hive/t-2026-11-17-wmtm-note-implication-goals-v2 (1dd5f47, wmtm/master_loader.py), copied verbatim
because that flag is not on PR 43 (a70dc86).  Only change: the relative import "from .semparse_adapter import to_str"
is made absolute.  The helpers it uses (_node, _unify, _subst, _ground, _syms, _NOTE_SFX) are the a70dc86 ones,
identical to 1dd5f47's.  The original function text has sha256 f33908fd0d71f471ace07831e98b022e53054a07af9e3c69f058aba73d28bb27
(git show 1dd5f47:wmtm/master_loader.py, from 'def note_impl_goals' up to 'def notes_from_parsed')."""
from wmtm.master_loader import _node, _unify, _subst, _ground, _syms, _NOTE_SFX  # noqa: F401


def note_impl_goals(ops, rule_atoms, note_labels, max_envs=200):
    """t-2026-11-17-wmtm-note-implication-goals (flag shadow_note_impl_goals, default off): goals from Implication
    atoms a note states (label in note_labels, i.e. atom_src; never a seeded/extra rule).  For each such atom, the
    conclusion becomes a goal when its premise matches loaded statements (all conjuncts; variables bound by matching,
    one step), minus conclusions already stated.  The atom itself stays in the KB with its STV as loaded.
    -> ({goal: "nimpl:" + label}, stats) where stats counts shapes and outcomes (no atom text)."""
    from wmtm.semparse_adapter import to_str
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
