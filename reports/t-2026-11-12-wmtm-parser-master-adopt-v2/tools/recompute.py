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

# review 1: hand verdicts, count rule vs A_v3, Mesto s11 drop list
VD = os.path.join(EV, "armB/verdicts")
def tsv(f):
    L = open(os.path.join(VD, f)).read().splitlines()
    h = L[0].split("\t"); return [dict(zip(h, l.split("\t"))) for l in L[1:] if l.strip()]
if os.path.isdir(VD) and os.path.exists(os.path.join(VD, "verdicts_restate.tsv")):
    v = {r["goal"]: r["verdict"] for r in tsv("verdicts_restate.tsv")}
    nt = {r["goal"]: r["verdict"] for r in tsv("verdicts23.tsv")}
    v.update(nt); vs = dict(v); vs.update({r["goal"]: r["verdict"] for r in tsv("verdicts_sens_impl.tsv")})
    J = json.load(open(os.path.join(EV, "baselines/f3v3/JUDGMENTS.json")))
    aC, aW = J["A_v3"]["counts"]["correct"], J["A_v3"]["counts"]["wrong"]
    for name, d, run in (("full_s2 all", v, "full_s2"), ("full_s2 non-restatement", nt, None), ("sens_s2 all", vs, "sens_s2")):
        if run:
            n = json.load(open(os.path.join(EV, "armB/%s/score.json" % run)))["goals"]
            if n != len(d): print("VERDICT COUNT MISMATCH", name, n, len(d)); bad += 1
        c = Counter(d.values()); C, W, U = c["correct"], c["wrong"], c["unclear"]
        print("verdicts", name, "n=%d C=%d W=%d U=%d" % (len(d), C, W, U), "count rule vs A_v3 %dC/%dW:" % (aC, aW),
              "HOLDS" if C >= aC and W <= aW else "FAILS")
    m = tsv("missing_ranked.tsv")
    print("mesto s11 dropped", len(m), dict(Counter(r["kind"] for r in m)))

# review 2: count rule vs old loader M17 (B_v3 + extra verdicts), A_v3/B line-up, suffix duplicates
if os.path.isdir(VD) and os.path.exists(os.path.join(VD, "verdicts_m17_extra.tsv")):
    import re
    norm = lambda g: g.replace("__i_ep_note_", "__ep_note_").strip()
    mv = {norm(r["goal"]): r["verdict"].lower() for r in J["B_v3"]["rows"]}
    mv.update({norm(r["goal"]): r["verdict"].lower() for r in tsv("verdicts_m17_extra.tsv")})
    runs = {}
    for l in open(os.path.join(EV, "baselines/old_loader/old_loader_goals.txt")):
        p = l.split(None, 2)
        if len(p) == 3: runs.setdefault(p[0], []).append(norm(p[2]))
    bsets = (("full_s2 all", Counter(v.values())), ("full_s2 non-restatement", Counter(nt.values())), ("sens_s2 all", Counter(vs.values())))
    for r, gs in sorted(runs.items()):
        c = Counter(mv.get(g, "unjudged") for g in gs)
        if c["unjudged"]: print("M17 UNJUDGED", r, c["unjudged"]); bad += 1
        print("M17", r, "n=%d C=%d W=%d" % (len(gs), c["correct"], c["wrong"]))
        for name, b in bsets:
            print("  count rule", name, "vs", r, "HOLDS" if b["correct"] >= c["correct"] and b["wrong"] <= c["wrong"] else "FAILS")
    lu = tsv("lineup_A_v3_vs_B.tsv")
    print("lineup A_v3 goals", len(lu), dict(Counter(r["status_in_B"].split(" (")[0] for r in lu)))
    for run in ("full_s2", "sens_s2"):
        q = json.loads(open(os.path.join(EV, "armB/%s/shadow.jsonl" % run)).readline())["queries"]
        notes = set()
        for x in q: notes |= set(re.findall(r"2026\d{4}T\d{6}Z", (x.get("proof") or "") + x["goal"]))
        print("lineup B", run, "notes touched by goals/proofs", len(notes))
    L = [l for l in open(os.path.join(VD, "suffix_dupes.tsv")).read().splitlines()[1:] if l.strip() and not l.startswith("#")]
    n = [int(l.split("\t")[0]) for l in L]
    print("suffix dupes: shapes", len(n), "labels", sum(n), "extra copies", sum(n) - len(n))
# review 3: alternative restatement split (all coref role rules counted as coref-link restatements)
if os.path.isdir(VD) and os.path.exists(os.path.join(VD, "verdicts23.tsv")):
    ROLE = {"coref_bearer", "coref_agent", "coref_patient", "coref_theme", "coref_member", "coref_possession"}
    sc = json.load(open(os.path.join(EV, "armB/full_s2/score.json")))
    alt = Counter(v[r["goal_id"]] for r in sc["rows"] if r["restatement"] is None and r["rule"] not in ROLE)
    print("alt non-restatement (all coref roles = restatement) n=%d C=%d W=%d" % (sum(alt.values()), alt["correct"], alt["wrong"]),
          "vs A_v3:", "HOLDS" if alt["correct"] >= aC and alt["wrong"] <= aW else "FAILS")
    for r, gs in sorted(runs.items()):
        c = Counter(mv.get(g, "unjudged") for g in gs)
        print("  alt vs", r, "HOLDS" if alt["correct"] >= c["correct"] and alt["wrong"] <= c["wrong"] else "FAILS")
    print("M17 extra hand verdicts", len(tsv("verdicts_m17_extra.tsv")))
# review 3: committed sums must equal the evidence folder sums
cs = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "SHA256SUMS")
if os.path.exists(cs) and os.path.exists(sums):
    same = open(cs, "rb").read() == open(sums, "rb").read()
    print("committed SHA256SUMS equals evidence SHA256SUMS:", same)
    if not same: bad += 1
print("RECOMPUTE_FAIL" if bad else "RECOMPUTE_OK")
