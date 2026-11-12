#!/usr/bin/env python3
"""t-2026-11-12-wmtm-parser-master-adopt-v2: counts-only recompute from the evidence folder (ids, counts, hashes).
Usage (repo root): python3 reports/t-2026-11-12-wmtm-parser-master-adopt-v2/tools/recompute.py /srv/hive-evidence/t-2026-11-12-wmtm-parser-master-adopt-v2
Checks SHA256SUMS, then prints: whole-note parse status per note id, whole-note A/B (legacy vs master) per stage,
sentence-mode call count (and max calls in any rolling hour), arm B runs (goals, proved, by rule, restatement split).
Ends RECOMPUTE_OK."""
import sys, os, json, hashlib, glob
from collections import Counter
EV = sys.argv[1]
def jl(p): return [json.loads(l) for l in open(p) if l.strip()]
bad = 0
sums = os.path.join(EV, "SHA256SUMS")
if os.path.exists(sums):
    for line in open(sums):
        h, f = line.split(None, 1); f = f.strip().lstrip("*")
        if hashlib.sha256(open(os.path.join(EV, f), "rb").read()).hexdigest() != h:
            print("SHA MISMATCH", f); bad += 1
    print("sha256sums checked, mismatches", bad)
last = {}
for r in jl(os.path.join(EV, "wholenote_parse/parse_log.jsonl")) + jl(os.path.join(EV, "wholenote_parse/parse_log_retry151833Z.jsonl")):
    i = r.get("item_id") or ""
    if i.startswith("ep-"): last[i] = r["status"]
print("wholenote parse:", dict(Counter(last.values())), "not ok:", sorted(k for k, v in last.items() if v != "ok"))
for st in ("canary", "pilot", "full"):
    row = []
    for arm in "AB":
        p = os.path.join(EV, "wholenote_ab/%s_%s/shadow.jsonl" % (st, arm))
        if not os.path.exists(p): continue
        d = json.loads(open(p).readlines()[-1])
        row.append("%s %s goals=%s proved=%s canary=%s neg=%s" % (arm, d.get("load_order"), d.get("goals_n"), d.get("pc_proved"),
                   d["canary"].get("ok"), d["neg"].get("ok")))
    print("wholenote A/B", st, " | ".join(row))
cp = os.path.join(EV, "sentence_parse/calls.jsonl")
if os.path.exists(cp):
    c = jl(cp); ts = sorted(x["ts"] for x in c)
    mx = max((sum(1 for t in ts if t0 <= t < t0 + 3600) for t0 in ts), default=0)
    lim = [x for x in c if x.get("error") and any(w in x["error"].lower() for w in ("429", "rate limit", "usage limit", "quota"))]
    print("sentence calls", len(c), "ok", sum(x["ok"] for x in c), "max_in_rolling_hour", mx, "limit_errors", len(lim))
for sc in sorted(glob.glob(os.path.join(EV, "armB/*/score.json"))):
    s = json.load(open(sc))
    print("armB", os.path.basename(os.path.dirname(sc)), {k: s[k] for k in ("status", "canary", "neg", "goals", "proved", "by_rule",
          "shipped_trivial", "restatement", "multi_note")})
print("RECOMPUTE_FAIL" if bad else "RECOMPUTE_OK")
