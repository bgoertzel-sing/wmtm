#!/usr/bin/env python3
"""Recompute every count in REPORT.md from evidence/ only (stdlib + judge_v2 from the normaliser-v2 report).
Usage: python3 reports/t-2026-11-10-wmtm-narrow-preload/tools/recompute.py   (run from the repo root)"""
import json, os, sys, hashlib
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); E = os.path.join(H, "evidence")
sys.path.insert(0, os.path.join(os.path.dirname(H), "t-2026-11-10-wmtm-normaliser-v2", "tools"))
import judge_v2 as J
ext = json.load(open(os.path.join(E, "extract_ids_only.json"))); W4 = json.load(open(os.path.join(E, "W4_f3v3.json")))
S = json.load(open(os.path.join(E, "SUMMARY.json"))); ok = True
for k, e in sorted(ext.items()):
    e = dict(e); e["shadow"] = os.path.join(E, "runs", e["shadow"])
    if hashlib.sha256(open(e["shadow"], "rb").read()).hexdigest() != e["record_sha256"]: print("SHA MISMATCH", k); ok = False
    c, _ = J.judge(e, W4, True)
    rec = json.loads(open(e["shadow"]).read().strip().splitlines()[-1])
    print(k, "goals", rec.get("goals_n"), "proved", rec.get("pc_proved"), "C/W/U/unjudged", c["CORRECT"], c["WRONG"], c["UNCLEAR"], c["UNJUDGED"], "W1", c["W1"])
    if k in S["judge"] and S["judge"][k]["v2_rule"] != c: print("JUDGE MISMATCH", k); ok = False
A = J.judge(dict(ext["A_A_v3"], shadow=os.path.join(E, "runs", "A_A_v3/shadow.jsonl")), W4, True)[0]
for r in ("r1", "r2", "r3", "f44"):
    k = "B_%s_after" % r if r != "f44" else "B_f44_before"
    b = S["judge"][k]["v2_rule"]
    rule = b["CORRECT"] >= A["CORRECT"] and b["WRONG"] <= A["WRONG"]
    g = S["goals"].get(r, [])
    _, v = J.judge(dict(ext[k], shadow=os.path.join(E, "runs", ext[k]["shadow"])), W4, True)
    echo = {x["goal"] for x in g if x["trivial_echo"]}
    cor = [q for q, (vv, _) in v.items() if vv == "CORRECT"]
    print(r, "count rule", "HOLDS" if rule else "FAILS", "| correct", len(cor), "trivial", sum(q in echo for q in cor),
          "non-trivial", sum(q not in echo for q in cor), "| goals echoing their own Narrow restriction", len(echo), "of", len(g))
    rc = S["recovery"].get(r)
    if rc: print("   recovered", rc["statements_recovered"], "still refused", rc["still_refused"], "nwdef", rc["nwdef_loaded"], "in", rc["petta_rejects_in"])
print("RECOMPUTE_OK" if ok else "RECOMPUTE_FAIL")
