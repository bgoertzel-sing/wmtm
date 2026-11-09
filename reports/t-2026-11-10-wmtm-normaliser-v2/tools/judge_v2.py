#!/usr/bin/env python3
"""Judge pc_shadow runs: F3 v3 rules (W1 incl. DEVIATION_1 nwdef join, W2, W3, W4 hand table) plus the v2 W1 rule
(andy, Work msg 355): an identical class-level fact (no sk_ witness) asserted in two or more notes is corroboration,
not conflation, so it does not by itself add a second source note.  Everything else in W1 is unchanged.
Usage: judge_v2.py <extract.json> <W4.json>.  Prints old and new counts per run and the goals whose verdict changes.
No note text is read or written (premise facts are parser symbols)."""
import json, re, sys

def sources(prem, P, by_fact, nw_notes, pr, new_rule):
    srcs = set()
    dup = []                      # class-level facts asserted identically in >= 2 notes
    for p in prem:
        e = P.get(p, {"src": "?", "fact": ""})
        f = e["fact"]
        notes = by_fact.get(f, {e["src"]})
        if new_rule and "sk_" not in f and len(notes) > 1:
            dup.append(notes)
        else:
            srcs.add(e["src"])
    for s_ in set(re.findall(r"\bnwdef_(\w+?__nw_[0-9a-f]+)\b", pr)):   # DEVIATION_1 join, unchanged
        srcs |= set(nw_notes.get(s_, []))
    for notes in dup:             # corroborated fact: attribute it to a note already in the chain if it is asserted there
        if not (notes & srcs):
            srcs.add(sorted(notes)[0])
    return srcs

def judge(e, W4, new_rule):
    d = json.loads(open(e["shadow"]).read().strip().splitlines()[-1]); P = e["premises"]; rej = set(e["gate_rejected"])
    by_fact = {}
    for v in P.values():
        by_fact.setdefault(v["fact"], set()).add(v["src"])
    c = {"CORRECT": 0, "WRONG": 0, "UNCLEAR": 0, "UNJUDGED": 0, "W1": 0, "W2": 0, "W3": 0}; verdict = {}
    for q in d["queries"]:
        if not q.get("ok") or (q.get("stv") or [0])[0] < 0.5: continue
        pr = q["proof"]; prem = sorted(set(re.findall(r"\bsp\d+\b", pr)))
        srcs = sources(prem, P, by_fact, e["nw_symbol_notes"], pr, new_rule)
        sk = any("sk_" in P.get(p, {"fact": ""})["fact"] for p in prem) or "sk_" in q["goal"]
        w1 = len(srcs) > 1 and sk; w2 = q["goal"].startswith("(Not")
        w3 = any(P.get(p, {"fact": ""})["fact"] in rej or P.get(p, {"src": "?"})["src"] == "?" for p in prem)
        c["W1"] += w1; c["W2"] += w2; c["W3"] += w3
        v4 = W4.get(q["goal"], "UNJUDGED")
        if v4 == "MECH_W1" and not w1: v4 = "UNJUDGED"
        v = "WRONG" if (w1 or w2 or w3) else v4
        c[v] += 1; verdict[q["goal"]] = (v, "W1" if w1 else ("W2" if w2 else ("W3" if w3 else "W4")))
    return c, verdict

if __name__ == "__main__":
    ext = json.load(open(sys.argv[1])); W4 = json.load(open(sys.argv[2])); out = {}
    for k, e in sorted(ext.items()):
        c0, v0 = judge(e, W4, False); c1, v1 = judge(e, W4, True)
        changed = {g: {"f3v3": v0[g], "v2": v1[g]} for g in v1 if v0.get(g) != v1[g]}
        out[k] = {"f3v3_rule": c0, "v2_rule": c1, "changed": changed,
                  "unjudged": sorted(g for g, (v, _) in v1.items() if v == "UNJUDGED")}
        print(k, "F3v3", c0, "\n   v2  ", c1, "\n   changed", changed)
    A = [o["v2_rule"] for k, o in out.items() if k.startswith("A")]; B = [o["v2_rule"] for k, o in out.items() if k.startswith("B")]
    if A and B:
        g1 = min(b["CORRECT"] for b in B) >= max(a["CORRECT"] for a in A) and max(b["WRONG"] for b in B) <= min(a["WRONG"] for a in A)
        print("gate1 count rule (v2 W1, worst case):", "HOLDS" if g1 else "FAILS")
    if len(sys.argv) > 3: json.dump(out, open(sys.argv[3], "w"), indent=1, sort_keys=True)
