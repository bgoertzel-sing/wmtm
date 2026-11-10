#!/usr/bin/env python3
"""Recompute every count in REPORT.md from evidence/ only.  Run from the repo root.
Needs the narrow-preload evidence (judge inputs) and judge_v2 from the normaliser-v2 report, both on this branch."""
import json, os, sys, hashlib, collections, tempfile, shutil
sys.path.insert(0, "."); sys.path.insert(0, "reports/t-2026-11-10-wmtm-normaliser-v2/tools")
import judge_v2 as J
from wmtm import pc_admit as P
H = "reports/t-2026-11-10-wmtm-narrow-preload/evidence"; E = "reports/t-2026-11-10-wmtm-trivial-filter/evidence"
S = json.load(open(E + "/SUMMARY.json")); ok = True
ext = json.load(open(H + "/extract_ids_only.json")); W4 = json.load(open(H + "/W4_f3v3.json"))
A, _ = J.judge(dict(ext["A_A_v3"], shadow=H + "/runs/A_A_v3/shadow.jsonl"), W4, True)
print("A", A["CORRECT"], "C", A["WRONG"], "W")
for r in ("r1", "r2", "r3"):
    p = E + "/runs/%s/admit.json" % r
    if hashlib.sha256(open(p, "rb").read()).hexdigest() != S["parses"][r]["admit_sha256"]: print("SHA MISMATCH", r); ok = False
    d = json.load(open(p)); _, v = J.judge(dict(ext["B_%s_after" % r], shadow=H + "/runs/B_%s_after/shadow.jsonl" % r), W4, True)
    ref = {x["goal"]: P.trivial_reason(x["proof"], x.get("rules")) for x in d["results"]}
    bef = collections.Counter(v.get(g, ("UNJUDGED",))[0] for g in ref)
    aft = collections.Counter(v.get(g, ("UNJUDGED",))[0] for g, w in ref.items() if not w)
    got = {}
    for on in (False, True):   # through the real admission path, flag off vs on
        t = tempfile.mkdtemp(); shutil.copy(p, t + "/admit.json")
        c, i = P.load_candidates({"shadow_dir": t, "reasoner_max_admit": 100, "gate_max_per_fact": 0, "admit_trivial_filter": on},
                                 None, now=float(d.get("spec_ts") or d["ts"]) + 1,
                                 live_ids=sorted({s for x in d["results"] for s in x.get("sources") or []}))
        got[on] = (len(c or []), i.get("trivial_refused_n")); shutil.rmtree(t)
    nref = sum(1 for w in ref.values() if w)
    rule = lambda k: k.get("CORRECT", 0) >= A["CORRECT"] and k.get("WRONG", 0) <= A["WRONG"]
    print(r, "goals", len(ref), "before C/W/U/unj", bef["CORRECT"], bef["WRONG"], bef["UNCLEAR"], bef["UNJUDGED"],
          "rule", "HOLDS" if rule(bef) else "FAILS", "| refused", nref, dict(collections.Counter(w for w in ref.values() if w)),
          "| after", len(ref) - nref, "C/W", aft["CORRECT"], aft["WRONG"], "rule", "HOLDS" if rule(aft) else "FAILS",
          "| load_candidates off/on admitted", got[False][0], got[True][0], "refused_n", got[True][1])
    if nref != S["parses"][r]["refused"] or S["parses"][r]["refused_non_trivial"] != 0: print("COUNT MISMATCH", r); ok = False
C = json.load(open(E + "/controls_s49.json"))
for k, rows in sorted(C.items()):
    n = sum(1 for x in rows if P.trivial_reason(x["proof"], x["rules"])); print(k, "results", len(rows), "refused", n)
    ok = ok and n == 0
for k in ("A_A_v3", "A_A_v3r1"):
    rec = json.loads(open(H + "/runs/%s/shadow.jsonl" % k).read().strip().splitlines()[-1])
    qs = [q for q in rec.get("queries", []) if q.get("ok")]
    n = sum(1 for q in qs if P.trivial_reason(q["proof"], None)); print(k, "proved", len(qs), "refused", n); ok = ok and n == 0
print("RECOMPUTE_OK" if ok else "RECOMPUTE_FAIL")
