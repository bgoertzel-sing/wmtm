#!/usr/bin/env python3
"""ATOMS.md: per case, the sentences, the lowered note atoms (exactly as loaded; master_loader.plan at PR 43), the
narrowed-class definitions they use, and the note implications' shapes.  Usage: atoms_md.py ARM_DIR > ATOMS.md"""
import json, os, sys
b = json.load(open(os.path.join(sys.argv[1], "build.json")))
spec = json.load(open(os.path.join(sys.argv[1], "spec.json")))
defs = [a for k, a in spec["master_ops"] if k == "atom" and (a.startswith("(: kind__") or a.startswith("(: by_"))]
print("# Lowered atoms (invented notes; master_loader.plan, sph 24e37182 lower.py master target, PR 43 a70dc86)\n")
print("Note suffix in labels/skolems: __ep_note_20991117T0000NNZ = case NN.  Statement order as loaded.\n")
for c in b["cases"]:
    print("## %s\n\nText: %s\n\n```" % (c["case"], c["text"]))
    for a in c["atoms"]:
        print(a)
    print("```\n")
    for i in c["note_implications"]:
        print("- note implication `%s`: %s, variables %s, skolem constants inside %s, note-impl goals %s, %s" % (
            i["label"], i["kind"], i["variables"] or "none", i["skolem_symbols_inside"] or "none", list(i["goals"]) or "none",
            {k: v for k, v in i["stats"].items() if v and k in ("premise_in_kb", "premise_missing", "concl_not_ground", "cross_note", "concl_stated")}))
    if not c["note_implications"]:
        print("- no Implication atom in this note")
    print()
print("## Narrowed-class definitions loaded (shared, no note suffix)\n\n```")
for a in defs:
    if "thing__" in a:
        print(a)
print("```")
