#!/usr/bin/env python3
"""t-2026-11-17-wmtm-variable-implication-test: lower the invented notes the way the master path does and build goals.

Path (all production code on this branch, PR 43 a70dc86, plus the 1dd5f47 note_impl_goals port):
  parsed.jsonl (sentence mode, 24e37182) -> pc_shadow.build_snapshot(shadow_load_order=master_ops)
     = master_loader.notes_from_parsed -> master_loader.plan (tmpl.lower, master target) -> rule_goals
  + note_impl_goals(ops, seeded+extra rules, atom_src)   (the shadow_note_impl_goals logic of 1dd5f47)
  + probe goals (order step 3/acceptance: the conclusion each case is about, asked whether or not a goal was built;
    built only by substituting a symbol the PARSER produced into the parser's own implication atom, never written by hand).
Writes OUT/spec.json (the worker's spec: goals = rule goals + note-impl goals + probes) and OUT/build.json.
DIAG=1 (diagnostic arm, NOT the master path): two mechanical loader-side additions, to tell whose fix each gap is:
  thing:  (: diag_thing__C (Inheritance C thing) (STV 1.0 0.99)) for every class C of a ground Member fact in the notes
  narrow: (: diag_narrow__S (Implication (And (Member $x N) (Member $x a)) (Member $x S)) (STV 1.0 0.99)) for every
          narrowed class S whose definitions are kind__S (Inheritance S N) and by_k__S (NarrowBy S (Is a)).
Usage: run_cases.py NOTES_JSON PARSED SPH_TEMPLATES REPO OUT EXTRA(0|1) DROP(- | comma list) [DIAG(0|1)]"""
import json, os, sys
notes_json, parsed, tdir, repo, out, extra, drop = sys.argv[1:8]
diag = len(sys.argv) > 8 and sys.argv[8] == "1"
sys.path.insert(0, repo); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wmtm import pc_shadow as PS, runtime_config as rc, master_loader as ML   # noqa: E402
from wmtm.semparse_adapter import to_str                                     # noqa: E402
from nimpl_port import note_impl_goals                                       # noqa: E402

cases = json.load(open(notes_json))["cases"]
ids = [c["doc"] for c in cases]
class It:
    def __init__(s, i): s.id = i; s.source_type = "note"
class St:
    def __init__(s, ids): s.ids = ids
    def get_active_set(s): return [It(i) for i in s.ids]
cfg = rc.resolve()
cfg.update(shadow_load_order="master_ops", shadow_sph_templates=tdir, shadow_master_parsed=parsed, shadow_max_goals=0,
           shadow_extra_rules=bool(int(extra)))
xdrop = () if drop == "-" else tuple(x for x in drop.split(",") if x)
sp = PS.build_snapshot(St(ids), k=len(ids), cfg=cfg)
ops, src = sp["master_ops"], sp["atom_src"]
xr = [r for r in ML.extra_rules() if ML._node(r)[1] not in set(xdrop)] if int(extra) else []
if int(extra) and xdrop:      # PR 43 has no drop flag: rebuild without the dropped rules (same as 1dd5f47 extra_drop)
    drop_atoms = set(ML.extra_rules()) - set(xr)
    ops = [o for o in ops if not (o[0] == "atom" and o[1] in drop_atoms)]
rules = ML.seeded_rules(tdir) + xr
diag_atoms = []
if diag:
    cls, kinds, isby = set(), {}, {}
    for k, a in ops:
        n = ML._node(a) if k == "atom" else None
        if not (isinstance(n, list) and len(n) == 4 and isinstance(n[2], list)):
            continue
        f = n[2]
        if "__ep_note_" in n[1] and f[0] == "Member" and len(f) == 3 and isinstance(f[2], str) and ML._ground(f):
            cls.add(f[2])
        if n[1].startswith("kind__") and f[0] == "Inheritance":
            kinds[f[1]] = f[2]
        if n[1].startswith("by_") and f[0] == "NarrowBy" and isinstance(f[2], list) and f[2][0] == "Is":
            isby.setdefault(f[1], []).append(f[2][1])
    for c in sorted(cls - {"thing"}):
        diag_atoms.append("(: diag_thing__%s (Inheritance %s thing) (STV 1.0 0.99))" % (c, c))
    for sym, noun in sorted(kinds.items()):
        if sym in isby:
            prem = " ".join(["(Member $x %s)" % noun] + ["(Member $x %s)" % a for a in isby[sym]])
            diag_atoms.append("(: diag_narrow__%s (Implication (And %s) (Member $x %s)) (STV 1.0 0.99))" % (sym, prem, sym))
    ops = list(ops) + [("atom", a) for a in diag_atoms]
rule_goals, per_rule = ML.rule_goals(ops, rules, scoped={ML._node(r)[1] for r in xr})
ng, nst = note_impl_goals(ops, rules, src)

def node(a):
    return ML._node(a)

def has_var(t):
    return not ML._ground(t)

def syms(t):
    return set(ML._syms(t)) if t is not None else set()

facts = []
for k, a in ops:
    if k == "atom" and a not in set(rules):
        n = node(a)
        if isinstance(n, list) and len(n) == 4 and isinstance(n[2], list) and n[2][0] not in ("Implication", "BiImplication"):
            facts.append((n[1], n[2]))
stated = {to_str(f) for _, f in facts}
subjects = sorted({f[1] for _, f in facts if f and f[0] == "Member" and len(f) == 3 and isinstance(f[1], str)})

report, probes = [], {}
for c in cases:
    suf = "__" + "".join(ch if ch.isalnum() else "_" for ch in c["doc"])
    mine = [a for k, a in ops if k == "atom" and suf in a]
    labs = [l for l, d in src.items() if d == c["doc"]]
    impls = []
    for l in labs:
        n = next((node(a) for a in mine if node(a) and node(a)[1] == l), None)
        if not (n and isinstance(n[2], list) and n[2][0] in ("Implication", "BiImplication")):
            continue
        r = n[2]
        g1, s1 = note_impl_goals(ops, rules, {l: c["doc"]})
        vars_ = sorted({x for x in syms(r) if x.startswith("$")})
        sk = sorted({x for x in syms(r) if x.startswith("sk_")})
        impls.append({"label": l, "atom": next(a for a in mine if node(a) and node(a)[1] == l), "kind": r[0],
                      "variables": vars_, "skolem_symbols_inside": sk, "premise_head": r[1][0] if isinstance(r[1], list) else r[1],
                      "goals": g1, "stats": {k: v for k, v in s1.items() if k not in ("premise_shape", "concl_shape")}})
    asked = []
    nodes = [node(a) for a in mine]
    for q in c.get("asks") or []:
        kind, val = q["subject"].split(":", 1)
        subj = None
        for n in nodes:
            if not (n and isinstance(n[2], list)):
                continue
            f = n[2]
            if kind == "member" and f[0] == "Member" and len(f) == 3 and f[2] == val and isinstance(f[1], str):
                subj = f[1]; break
            if kind == "name" and f[0] == "Name" and f[1] == val:
                subj = val; break
            if kind == "prefix":
                hit = [x for x in syms(f) if isinstance(x, str) and x.startswith(val)]
                if hit:
                    subj = hit[0]; break
        g = "(Member %s %s)" % (subj, q["class"]) if subj else None
        if g:
            probes.setdefault(g, "ask:%s" % c["case"])
        asked.append(dict(q, goal=g, stated=bool(g and g in stated), note_impl_goal=bool(g and g in ng),
                          rule_goal=bool(g and g in rule_goals)))
    report.append({"case": c["case"], "asked": asked, "doc": c["doc"], "text": c["text"], "expect": c["expect"], "atoms": mine,
                   "note_implications": impls,
                   "meta": sp.get("master_notes"), "plan_note": (sp.get("master_meta") or {}).get("notes", {}).get(c["doc"])})

goals = dict(rule_goals)
for g, why in ng.items():
    goals.setdefault(g, why)
for g, why in probes.items():
    goals.setdefault(g, why)
spec = dict(sp, master_ops=ops, goals=list(goals), goal_rule=goals)
json.dump(spec, open(os.path.join(out, "spec.json"), "w"))
json.dump({"cases": report, "rule_goals": rule_goals, "note_impl_goals": ng, "note_impl_stats": nst, "probes": probes,
           "subjects": subjects, "diag_atoms": diag_atoms, "master_notes": sp.get("master_notes"), "extra": int(extra), "drop": list(xdrop),
           "n_ops": len(ops), "n_goals": len(goals)}, open(os.path.join(out, "build.json"), "w"), indent=1)
print(json.dumps({"goals": len(goals), "rule_goals": len(rule_goals), "nimpl": len(ng), "probes": len(probes),
                  "master_notes": sp.get("master_notes"), "nimpl_stats": {k: v for k, v in nst.items() if not isinstance(v, dict)}}))
