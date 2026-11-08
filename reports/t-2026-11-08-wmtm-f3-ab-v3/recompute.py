#!/usr/bin/env python3
"""Stdlib-only recheck of t-2026-11-08-wmtm-f3-ab-v3. Usage: python3 -S recompute.py [report dir].
Reads the 12 committed shadow records (runs/), extract.json (premise id -> source note id + parsed fact, gate rejects; no note text)
and W4.json (hand verdicts). Re-derives W1-W3 mechanically (P4 rules; W1 also follows shared nwdef_ narrow-class symbols across notes), then W4; checks item C (no factored/merge revision over
asserted facts counted as a conclusion) and gate 1 worst-case over runs. Exit 0 iff gate 1 holds and every goal is judged."""
import json, os, re, sys
R = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
ext = json.load(open(os.path.join(R, "extract.json"))); W4 = json.load(open(os.path.join(R, "W4.json")))
res = {}; ok = True
for k, e in sorted(ext.items()):
    d = json.loads(open(os.path.join(R, e["shadow"])).read().strip().splitlines()[-1]); P = e["premises"]; rej = set(e["gate_rejected"])
    c = {"CORRECT": 0, "WRONG": 0, "UNCLEAR": 0, "UNJUDGED": 0, "W1": 0, "W2": 0, "W3": 0, "revision_only": 0}
    for q in d["queries"]:
        if not q.get("ok") or (q.get("stv") or [0])[0] < 0.5: continue
        pr = q["proof"]
        if re.match(r"\(: \((factored-revision|merge/revision) ", pr) and "(by " not in pr.split("prior")[0].replace("(by nwdef", ""):
            c["revision_only"] += 1
        prem = sorted(set(re.findall(r"\bsp\d+\b", pr)))
        srcs = {P.get(p, {"src": "?"})["src"] for p in prem}
        nws = set(re.findall(r"\bnwdef_(\w+?__nw_[0-9a-f]+)\b", pr))          # shared narrow-class symbols join notes too
        for s_ in nws: srcs |= set(e.get("nw_symbol_notes", {}).get(s_, []))
        sk = any("sk_" in P.get(p, {"fact": ""})["fact"] for p in prem) or "sk_" in q["goal"]
        w1 = len(srcs) > 1 and sk
        w2 = q["goal"].startswith("(Not"); w3 = any(P.get(p, {"fact": ""})["fact"] in rej or P.get(p, {"src": "?"})["src"] == "?" for p in prem)
        c["W1"] += w1; c["W2"] += w2; c["W3"] += w3
        v4 = W4.get(q["goal"], "UNJUDGED")
        if v4 == "MECH_W1" and not w1: v4 = "UNJUDGED"          # hand table says W1: must be re-derived mechanically
        c["WRONG" if (w1 or w2 or w3) else v4] += 1
    ok &= c["UNJUDGED"] == 0; res[k] = c; print(k, c)
A = [c for k, c in res.items() if k[0] == "A"]; B = [c for k, c in res.items() if k[0] == "B"]
g1 = min(b["CORRECT"] for b in B) >= max(a["CORRECT"] for a in A) and max(b["WRONG"] for b in B) <= min(a["WRONG"] for a in A)
print("gate1 count rule (worst case over runs):", "HOLDS" if g1 else "FAILS"); ok &= g1
print("RECOMPUTE_OK" if ok else "RECOMPUTE_FAIL"); sys.exit(0 if ok else 1)
