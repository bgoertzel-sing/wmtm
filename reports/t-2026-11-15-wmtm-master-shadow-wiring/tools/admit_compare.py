#!/usr/bin/env python3
"""t-2026-11-15-wmtm-master-shadow-wiring: admit-level comparison (counts/ids only).
The wired run's admit.json (written by the worker itself through pc_admit.write_admit_file, with the sources the
built spec's atom_src gives - no post-hoc spec_maps) goes through pc_admit.load_candidates (trivial filter at its
default, live ids = the 20 note ids) in a private mode-700 temp dir removed at exit.  Then drops, refusals by
reason, admitted C/W/U (verdicts by goal id b01.., as judged in t-2026-11-14-wmtm-trivial-filter-coref) and the
count rule vs A_v3 and the old loader M17 runs - compared with the render task's armB full_s2 row.
Usage: python3 reports/<task>/tools/admit_compare.py EV [run_apply|run]"""
import sys, os, json, tempfile, shutil, atexit
from collections import Counter
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, REPO)
from wmtm import pc_admit as P
sys.path.insert(0, os.path.join(REPO, "reports", "t-2026-11-14-wmtm-trivial-filter-coref", "tools"))
import rescore as RS

REF = {"dropped": {"asserted": 0, "bad": 0, "known": 0, "negative": 0, "no_live_source": 0, "per_fact_cap": 0, "trivial": 82},
       "refused_by_reason": {"coref_restatement": 5, "symmetry_restatement": 77}, "admitted": 23, "C": 22, "W": 1, "U": 0,
       "unjudged": 0, "vs_A_v3": "HOLDS"}   # render task tables/counts.json arms.full_s2 (t-2026-11-14-wmtm-render-master-goals)
BASE_EV = "/srv/hive-evidence/t-2026-11-14-wmtm-render-master-goals"
_TMP = []
def tmpdir():
    if not _TMP:
        d = tempfile.mkdtemp(prefix="msw_lc_"); _TMP.append(d); atexit.register(cleanup)
    return _TMP[0]
def cleanup():
    if _TMP: shutil.rmtree(_TMP.pop(), ignore_errors=True)

def main(EV, RUN):
    I = os.path.join(EV, "inputs"); D = os.path.join(EV, RUN)
    notes = [l.strip() for l in open(os.path.join(I, "note_ids.txt")) if l.strip()]
    base, _ = RS.compute(BASE_EV)   # A_v3 / M17 baselines as judged, from the render task's evidence (group-readable)
    vd = {r["goal"]: r["verdict"] for f in ("verdicts_restate.tsv", "verdicts23.tsv", "verdicts_sens_impl.tsv")
          for r in RS.tsv(os.path.join(I, "verdicts", f))}
    aC, aW = [int(x[:-1]) for x in base["inputs"]["A_v3"].split("/")]
    adm = json.load(open(os.path.join(D, "admit.json")))
    qs = json.loads(open(os.path.join(D, "shadow.jsonl")).readlines()[-1])["queries"]
    gid = {RS.norm(q["goal"]): "b%02d" % (i + 1) for i, q in enumerate(qs)}
    sd = os.path.join(tmpdir(), RUN); os.makedirs(sd, mode=0o700)
    json.dump(adm, open(os.path.join(sd, P.ADMIT_FILE), "w"))
    c, info = P.load_candidates({"shadow_dir": sd, "reasoner_max_admit": 1000, "gate_max_per_fact": 0}, None,
                                now=float(adm.get("spec_ts") or adm["ts"]) + 1, live_ids=notes)
    c = c or []
    ag = [gid.get(RS.norm(x.provenance["goal"]), "?") for x in c]
    cv = Counter(vd.get(g, "unjudged") for g in ag)
    out = {"run": RUN, "admit_status": adm.get("status"), "canary_ok": adm.get("canary_ok"), "results": len(adm["results"]),
           "results_with_sources": sum(1 for r in adm["results"] if r.get("sources")),
           "dropped": info["dropped"], "refused_by_reason": dict(sorted(Counter(e["reason"] for e in info.get("trivial_refused") or []).items())),
           "admitted": len(c), "C": cv["correct"], "W": cv["wrong"], "U": cv["unclear"], "unjudged": cv["unjudged"],
           "admitted_wrong_ids": sorted(g for g in ag if vd.get(g) == "wrong"),
           "admitted_unclear_ids": sorted(g for g in ag if vd.get(g) == "unclear"),
           "vs_A_v3": RS.rule_verdict(cv["correct"], cv["wrong"], aC, aW), "A_v3": base["inputs"]["A_v3"],
           "vs_M17_as_judged": {r: RS.rule_verdict(cv["correct"], cv["wrong"], v["as_judged"]["C"], v["as_judged"]["W"]) for r, v in base["m17"].items()}}
    out["equal_to_render_armB_full_s2"] = all(out[k] == v for k, v in REF.items())
    cleanup()
    return out

if __name__ == "__main__":
    o = main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "run_apply")
    print(json.dumps(o, indent=1, sort_keys=True))
    sys.exit(0 if o["equal_to_render_armB_full_s2"] else 1)
