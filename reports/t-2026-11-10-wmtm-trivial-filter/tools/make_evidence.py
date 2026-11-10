#!/usr/bin/env python3
"""t-2026-11-10-wmtm-trivial-filter: build evidence/SUMMARY.json from the frozen B rerun (~/scratch/trivf/runs) and
the narrow-preload evidence.  Ids, parser symbols, counts and hashes only.  Run from the repo root."""
import json, os, sys, shutil, hashlib, collections
sys.path.insert(0, "."); sys.path.insert(0, "reports/t-2026-11-10-wmtm-normaliser-v2/tools")
import judge_v2 as J
from wmtm import pc_admit as P
H = "reports/t-2026-11-10-wmtm-narrow-preload/evidence"; E = "reports/t-2026-11-10-wmtm-trivial-filter/evidence"
RUNS = os.environ.get("TRIVF_RUNS", os.path.expanduser("~/scratch/trivf/runs"))
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
ext = json.load(open(H + "/extract_ids_only.json")); W4 = json.load(open(H + "/W4_f3v3.json"))
NP = json.load(open(H + "/SUMMARY.json"))
A, Av = J.judge(dict(ext["A_A_v3"], shadow=H + "/runs/A_A_v3/shadow.jsonl"), W4, True)
out = {"A": {"counts": A, "verdicts": {q: v[0] for q, v in Av.items()}}, "parses": {}}
for r in ("r1", "r2", "r3"):
    k = "B_%s_after" % r
    os.makedirs(E + "/runs/" + r, exist_ok=True)
    for f in ("admit.json", "shadow.jsonl"):
        if os.path.exists(os.path.join(RUNS, r + "_after", f)):
            shutil.copy(os.path.join(RUNS, r + "_after", f), E + "/runs/%s/%s" % (r, f))
    d = json.load(open(E + "/runs/%s/admit.json" % r))
    _, v = J.judge(dict(ext[k], shadow=H + "/runs/%s/shadow.jsonl" % k), W4, True)
    label = {x["goal"]: x["trivial_echo"] for x in NP["goals"][r]}
    rows = []
    for x in d["results"]:
        why = P.trivial_reason(x["proof"], x.get("rules"))
        rows.append({"goal": x["goal"], "verdict": v.get(x["goal"], ("UNJUDGED",))[0], "trivial_by_label": label.get(x["goal"]),
                     "refused": bool(why), "reason": why})
    bef = collections.Counter(z["verdict"] for z in rows)
    aft = collections.Counter(z["verdict"] for z in rows if not z["refused"])
    def split(rs):
        return {"trivial": sum(1 for z in rs if z["trivial_by_label"]), "non_trivial": sum(1 for z in rs if not z["trivial_by_label"])}
    out["parses"][r] = {
        "admit_sha256": sha(E + "/runs/%s/admit.json" % r),
        "before": {"n": len(rows), "verdicts": dict(bef), "split": split(rows)},
        "after": {"n": sum(1 for z in rows if not z["refused"]), "verdicts": dict(aft), "split": split([z for z in rows if not z["refused"]])},
        "refused": len([z for z in rows if z["refused"]]),
        "refused_reasons": dict(collections.Counter(z["reason"] for z in rows if z["refused"])),
        "refused_non_trivial": sum(1 for z in rows if z["refused"] and not z["trivial_by_label"]),
        "label_disagree": sum(1 for z in rows if z["refused"] != bool(z["trivial_by_label"])),
        "count_rule": {"before": bef.get("CORRECT", 0) >= A["CORRECT"] and bef.get("WRONG", 0) <= A["WRONG"],
                       "after": aft.get("CORRECT", 0) >= A["CORRECT"] and aft.get("WRONG", 0) <= A["WRONG"]},
        "rows": rows}
# non-trivial controls: A (f3-ab-v3) proofs and the s49 snapshot (49 non-trivial conclusions on a real KB)
ctl = {}
for k in ("A_A_v3", "A_A_v3r1"):
    rec = json.loads(open(H + "/runs/%s/shadow.jsonl" % k).read().strip().splitlines()[-1])
    qs = [q for q in rec.get("queries", []) if q.get("ok")]
    ctl[k] = {"proved": len(qs), "refused": sum(1 for q in qs if P.trivial_reason(q["proof"], None))}
for n in ("run_snap", "run_live"):
    d = "/tmp/s49/" + n
    if os.path.exists(d + "/admit.json"):
        s = json.load(open(d + "/spec.json")); a = json.load(open(d + "/admit.json"))
        ctl["s49_" + n] = {"results": len(a["results"]), "admit_sha256": sha(d + "/admit.json"),
                           "refused": sum(1 for x in a["results"] if P.trivial_reason(x["proof"], P.proof_rules(x["proof"], s["atoms"])))}
out["controls"] = ctl
json.dump(out, open(E + "/SUMMARY.json", "w"), indent=1, sort_keys=True)
for r, p in out["parses"].items():
    print(r, "before", p["before"], "after", p["after"], "refused", p["refused"], p["refused_reasons"],
          "refused_non_trivial", p["refused_non_trivial"], "disagree", p["label_disagree"], "rule", p["count_rule"])
print("controls", ctl)
