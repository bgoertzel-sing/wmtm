#!/usr/bin/env python3
"""Mechanical W1-W3 check for arm B (P4 rev4), same rules as P3 recompute/w123.py (PREREG lines 15-17):
W1 = proof mixes premises from >1 note and uses an sk_* fact; W2 = goal is negated or in neg_goals;
W3 = a premise was gate-rejected or comes from a note outside the 20-note sample.
Inputs: rev3/bdae8d7e/shadow_B.jsonl + rev4/w123/w123_extract.json (no note text).
Usage: python3 -S rev4/w123/w123_B.py [report_root]. Writes rev4/w123/B_W123.json; exit 0 iff it matches the saved copy (or creates it)."""
import json, os, re, sys
R = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
ext = json.load(open(os.path.join(R, "rev4/w123/w123_extract.json")))
d = json.loads(open(os.path.join(R, "rev3/bdae8d7e/shadow_B.jsonl")).read().strip().splitlines()[-1])
P = ext["premises"]; sample = set(ext["sample"]); out = []
for q in d["queries"]:
    if not q["ok"]: continue
    prem = sorted(set(re.findall(r"\bsp\d+\b", q["proof"])), key=lambda x: int(x[2:]))
    srcs = sorted({P[p]["src"] for p in prem}); facts = [P[p]["fact"] for p in prem]
    w1 = len(srcs) > 1 and any("sk_" in f for f in facts)
    w2 = q["goal"] in ext["neg_goals"] or q["goal"].startswith("(Not")
    w3 = [p for p in prem if P[p]["gate_rejected"] or P[p]["src"] not in sample]
    out.append({"goal": q["goal"], "stv": q["stv"], "premises": prem, "sources": srcs, "W1": w1, "W2": w2, "W3": w3})
path = os.path.join(R, "rev4/w123/B_W123.json")
same = True
if os.path.exists(path): same = json.load(open(path)) == out
else: json.dump(out, open(path, "w"), indent=1)
print(json.dumps({"n_goals": len(out), "neg_atoms": ext["neg_atom_count"], "gate_rejected": ext["gate_rejected_count"],
  "W1": sum(o["W1"] for o in out), "W2": sum(o["W2"] for o in out), "W3": sum(bool(o["W3"]) for o in out),
  "wrong_W123": sum(bool(o["W1"] or o["W2"] or o["W3"]) for o in out), "matches_saved": same}))
sys.exit(0 if same else 1)
