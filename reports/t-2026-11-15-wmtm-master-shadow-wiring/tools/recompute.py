#!/usr/bin/env python3
"""Counts-only recompute for t-2026-11-15-wmtm-master-shadow-wiring. Reads run/*.json(l) only."""
import json, os, sys
E = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = sys.argv[1] if len(sys.argv) > 1 else "run_apply"   # run = inline loop (580d394), run_apply = master_loader.apply (988579f)
s = json.load(open(f"{E}/{RUN}/shadow.jsonl")); r = json.load(open(f"{E}/run/ref_render_armB_full_s2.shadow.jsonl"))
sp = json.load(open(f"{E}/run/spec.json"))
def st(x):
    if isinstance(x, dict): return {k: st(v) for k, v in x.items() if k != "s"}
    if isinstance(x, list): return [st(v) for v in x]
    return x
out = {
 "run": RUN,
 "spec_master_ops": len(sp["master_ops"]), "spec_goals": len(sp["goals"]),
 "status": s["status"], "load_order": s["load_order"], "goals_n": s["goals_n"],
 "pc_proved": s["pc_proved"], "ok_queries": sum(q["ok"] for q in s["queries"]),
 "add_fail": s["add_fail"], "pred_fail": s["pred_fail"], "timeouts": s["timeouts"],
 "skipped_budget": s["skipped_budget"], "unparsed_items": s.get("unparsed_items"),
 "ref_pc_proved": r["pc_proved"], "ref_goals_n": r["goals_n"],
 "queries_equal_excl_timing": st(s["queries"]) == st(r["queries"]),
 "canary_equal_excl_timing": st(s["canary"]) == st(r["canary"]),
 "neg_equal_excl_timing": st(s["neg"]) == st(r["neg"]),
}
print(json.dumps(out, indent=1))
ok = (out["status"] == "ok" and out["pc_proved"] == out["ref_pc_proved"] == 105 and out["add_fail"] == 0
      and out["pred_fail"] == 0 and out["queries_equal_excl_timing"] and out["canary_equal_excl_timing"] and out["neg_equal_excl_timing"])
print("PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
