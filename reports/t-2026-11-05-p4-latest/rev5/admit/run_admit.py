"""P4 rev5 (review 4 finding 1): wmtm's own admission filter (pc_admit.load_candidates) on the nwdef A/B runs.
Columns: pre_rev5 = filter as at f58f9a5 (_RULE only); rev5 = filter with _PARSER_RULE (direct parser-implication proofs).
Runs: full (rev4, nwdef in), nonwdef (rev4, nwdef removed by hand), nonwdef_flag (rev5, shadow_nwdef=False through the real code path).
Usage: python3 run_admit.py (wmtm repo found at ../../../..)"""
import json, os, re, shutil, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(here, "../../../..")))
from wmtm import pc_admit, runtime_config as rc
NEVER = re.compile(r"(?!x)x")
out = {}
for v in ("full", "nonwdef", "nonwdef_flag"):
    d = tempfile.mkdtemp()
    shutil.copy(os.path.join(here, "admit_%s.json" % v), os.path.join(d, "admit.json"))
    doc = json.load(open(os.path.join(d, "admit.json")))
    live = sorted({s for r in doc["results"] for s in r["sources"]})
    cfg = dict(rc.resolve()); cfg["shadow_dir"] = d; cfg["reasoner_max_age_s"] = 1e12
    row = {"results": len(doc["results"])}
    for tag, pr in (("pre_rev5", NEVER), ("rev5", pc_admit._PARSER_RULE)):
        old = pc_admit._PARSER_RULE; pc_admit._PARSER_RULE = pr
        c, info = pc_admit.load_candidates(cfg, None, live_ids=live)
        pc_admit._PARSER_RULE = old
        row[tag] = {"candidates": info.get("candidates"), "dropped": info.get("dropped"),
                    "admitted_goals": [x.provenance["goal"] for x in (c or [])],
                    "admitted_conf": [round(x.confidence, 4) for x in (c or [])]}
    out[v] = row
    shutil.rmtree(d)
json.dump(out, open(os.path.join(here, "ADMIT_AB.json"), "w"), indent=1)
for v in out: print(v, "pre_rev5", out[v]["pre_rev5"]["candidates"], "rev5", out[v]["rev5"]["candidates"], out[v]["rev5"]["admitted_conf"])
