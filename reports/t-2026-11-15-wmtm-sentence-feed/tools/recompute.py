#!/usr/bin/env python3
"""Counts-only recompute for t-2026-11-15-wmtm-sentence-feed.  Reads only evidence JSON (this task's and the
shadow-wiring task's run_apply reference) and prints PASS / FAIL.  No note text is read or printed.
Usage: python3 recompute.py [EVIDENCE_DIR]"""
import json, os, sys
E = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = "/srv/hive-evidence/t-2026-11-15-wmtm-master-shadow-wiring/run_apply/shadow.jsonl"
C = json.load(open(os.path.join(E, "replay", "counts.json")))
def last(p): return json.loads(open(p).readlines()[-1])
def st(x):
    if isinstance(x, dict): return {k: st(v) for k, v in x.items() if k not in ("s", "prequery_s", "warm_s", "total_s", "ts", "start_ts")}
    if isinstance(x, list): return [st(v) for v in x]
    return x
r = last(REF)
out, ok = {}, True
for arm in ("offline_order", "feed_order"):
    s = last(os.path.join(E, "replay", arm, "shadow.jsonl"))
    a = json.load(open(os.path.join(E, "replay", arm, "admit.json")))
    key = lambda q: json.dumps(st(q), sort_keys=True)
    o = {"pc_proved": s["pc_proved"], "goals_n": s["goals_n"], "add_fail": s["add_fail"], "pred_fail": s["pred_fail"],
         "timeouts": s["timeouts"], "status": s["status"], "admit_results": len(a["results"]),
         "queries_equal_ref": st(s["queries"]) == st(r["queries"]),
         "queries_same_set_as_ref": sorted(map(key, s["queries"])) == sorted(map(key, r["queries"])),
         "canary_equal_ref": st(s["canary"]) == st(r["canary"]), "neg_equal_ref": st(s["neg"]) == st(r["neg"])}
    c = C[arm]
    agree = (o["pc_proved"] == c["shadow"]["pc_proved"] == 105 and o["goals_n"] == 105 and o["add_fail"] == 0
             and o["pred_fail"] == 0 and o["queries_same_set_as_ref"] and o["canary_equal_ref"] and o["neg_equal_ref"]
             and o["queries_equal_ref"] == c["shadow"]["queries_equal_ref_excl_timing"]
             and (c["admit"]["admitted"], c["admit"]["C"], c["admit"]["W"]) == (23, 22, 1) and c["admit"]["vs_A_v3"] == "HOLDS"
             and c["rows"]["byte_identical_to_cached_good_row"] == c["rows"]["rebuilt"] == 124
             and c["replay"]["ledger_rows"] == c["replay"]["calls"] == 124 and c["replay"]["ledger_roles"] == ["live"]
             and c["replay"]["provider"] == {"requests": 124, "served": 124}
             and c["replay"]["master_path_never_saw_a_partial_note"])
    o["agrees_with_counts_json"] = agree
    ok &= agree
    out[arm] = o
ok &= C["offline_order"]["spec"]["master_ops_equal_ref"] and C["offline_order"]["spec"]["goals_equal_ref"]
ok &= C["split"]["equal_to_sel_jsonl"] and C["untouched"]["equal"]
print(json.dumps(out, indent=1, sort_keys=True))
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
