"""rev3: replay the real reader (pc_admit.load_candidates, default config: trivial filter on, cap 5) over each committed run."""
import json, os, sys, glob
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from wmtm import pc_admit as pa
from wmtm import runtime_config as rc
base = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "evidence", "runs_rev2")
print("\t".join(["run", "results", "trivial_refused", "asserted", "admitted_n", "admitted_goals", "trivial_filter", "cap"]))
for d in sorted(glob.glob(base + "/*")):
    doc = json.load(open(d + "/admit.json"))
    cfg = dict(rc.resolve(environ={}))
    cfg["shadow_dir"] = d; cfg["reasoner_max_age_s"] = 10 ** 12
    live = sorted({s for r in doc["results"] for s in (r.get("sources") or [])})
    cands, info = pa.load_candidates(cfg, None, now=float(doc.get("spec_ts") or doc.get("ts")), live_ids=live)
    goals = [c.provenance["goal"] for c in (cands or [])]
    print("\t".join([os.path.basename(d), str(info.get("results")), str(info.get("trivial_refused_n")),
                     str((info.get("dropped") or {}).get("asserted")), str(len(goals)), ";".join(goals),
                     str(info.get("trivial_filter")), str(cfg.get("reasoner_max_admit") or 5)]))
