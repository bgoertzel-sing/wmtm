#!/usr/bin/env python3
"""Judge pc_shadow runs with F3 v3 rules (W1 incl. DEVIATION_1 nwdef join, W2, W3, then W4 hand table).
Usage: judge.py <extract.json> <W4.json>. Prints per-run counts, lists unjudged goals, and gate-1 worst case."""
import json, re, sys
ext = json.load(open(sys.argv[1])); W4 = json.load(open(sys.argv[2])); res = {}; unj = set()
for k, e in sorted(ext.items()):
    d = json.loads(open(e["shadow"]).read().strip().splitlines()[-1]); P = e["premises"]; rej = set(e["gate_rejected"])
    c = {"CORRECT": 0, "WRONG": 0, "UNCLEAR": 0, "UNJUDGED": 0, "W1": 0, "W2": 0, "W3": 0}
    for q in d["queries"]:
        if not q.get("ok") or (q.get("stv") or [0])[0] < 0.5: continue
        pr = q["proof"]; prem = sorted(set(re.findall(r"\bsp\d+\b", pr)))
        srcs = {P.get(p, {"src": "?"})["src"] for p in prem}
        for s_ in set(re.findall(r"\bnwdef_(\w+?__nw_[0-9a-f]+)\b", pr)): srcs |= set(e["nw_symbol_notes"].get(s_, []))
        sk = any("sk_" in P.get(p, {"fact": ""})["fact"] for p in prem) or "sk_" in q["goal"]
        w1 = len(srcs) > 1 and sk; w2 = q["goal"].startswith("(Not")
        w3 = any(P.get(p, {"fact": ""})["fact"] in rej or P.get(p, {"src": "?"})["src"] == "?" for p in prem)
        c["W1"] += w1; c["W2"] += w2; c["W3"] += w3
        v4 = W4.get(q["goal"], "UNJUDGED")
        if v4 == "MECH_W1" and not w1: v4 = "UNJUDGED"
        if not (w1 or w2 or w3) and v4 == "UNJUDGED": unj.add(q["goal"])
        c["WRONG" if (w1 or w2 or w3) else v4] += 1
    res[k] = c; print(k, c)
A = [c for k, c in res.items() if k.startswith("A")]; B = [c for k, c in res.items() if k.startswith("B")]
if A and B:
    g1 = min(b["CORRECT"] for b in B) >= max(a["CORRECT"] for a in A) and max(b["WRONG"] for b in B) <= min(a["WRONG"] for a in A)
    print("gate1 count rule (worst case):", "HOLDS" if g1 else "FAILS")
print("UNJUDGED goals needing W4 hand verdicts:", len(unj)); [print("  ", g) for g in sorted(unj)]
