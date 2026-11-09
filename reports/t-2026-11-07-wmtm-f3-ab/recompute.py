#!/usr/bin/env python3
"""Stdlib-only recheck of t-2026-11-07-wmtm-f3-ab verdicts. Usage: python3 -S recompute.py <bundle root>.
Reads each run's shadow.jsonl (in the bundle) + recompute/extract.json (premise -> source note, fact; gate rejects; no note text)
+ recompute/W4.json (hand W4 table). Applies PREREG W1-W3 mechanically, then W4. Prints counts and the gate verdict.
Also prints a W1-off sensitivity count. Exit 0 iff the counts match JUDGMENTS.json and gate 1 holds."""
import json, os, re, sys
R = sys.argv[1]
ext = json.load(open(os.path.join(R, "recompute/extract.json"))); W4 = json.load(open(os.path.join(R, "recompute/W4.json")))
saved = json.load(open(os.path.join(R, "JUDGMENTS.json")))
BMAP = {"v2/full_A": "v2/full_A", "v2/full_B": "v2/full_B", "v2k/A": "v2k/A", "v2k/B": "v2k/B"}
def shadow_path(p):
    p = p.replace("/shadow.jsonl", "")
    return os.path.join(R, p, "shadow.jsonl")
res = {}; ok = True
for k, e in sorted(ext.items()):
    d = json.loads(open(shadow_path(e["shadow"])).readline()); P = e["premises"]; rej = set(e["gate_rejected"])
    c = {"correct": 0, "wrong": 0, "unclear": 0, "unjudged": 0}; c_nw1 = dict(c)
    for q in d["queries"]:
        if not q.get("ok") or (q.get("stv") or [0])[0] < 0.5: continue
        pr = q["proof"]; prem = sorted(set(re.findall(r"\bsp\d+\b", pr)))
        rid = {m[1] for m in re.findall(r"\b(i_ep_note_(\d{8}T\d{6}Z)__x\d+_\w+?)\b", pr)}
        srcs = {P[p]["src"] for p in prem} | {"ep-note-" + n for n in rid}
        w1 = len(srcs) > 1 and any("sk_" in P[p]["fact"] for p in prem)
        w2 = q["goal"].startswith("(Not"); w3 = any(P[p]["fact"] in rej or P[p]["src"] == "?" for p in prem)
        v4 = W4.get(q["goal"], ["UNJUDGED"])[0].lower()
        c["wrong" if (w1 or w2 or w3) else v4] += 1
        c_nw1["wrong" if (w2 or w3) else v4] += 1
    s = saved[k]["counts"]; same = all(c[x] == s[x] for x in c); ok &= same
    res[k] = (c, c_nw1); print(k, c, "W1-off:", c_nw1, "matches" if same else "MISMATCH")
for tag, i in (("W1 on", 0), ("W1 off", 1)):
    A = [v[i] for k, v in res.items() if k[0] == "A"]; B = [v[i] for k, v in res.items() if k[0] == "B"]
    g1 = min(b["correct"] for b in B) >= max(a["correct"] for a in A) and max(b["wrong"] for b in B) <= min(a["wrong"] for a in A)
    print(tag, "gate1 count rule (worst case over runs):", "HOLDS" if g1 else "FAILS")
    if i == 0: ok &= g1
print("RECOMPUTE_OK" if ok else "RECOMPUTE_FAIL"); sys.exit(0 if ok else 1)
