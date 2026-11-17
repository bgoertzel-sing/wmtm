#!/usr/bin/env python3
"""t-2026-11-17-wmtm-impl-premise-proving: counts-only recompute (ids and counts only; no note text printed).
Arms EV/{base,off,ip,sg,ipsg}: base = all note-impl flags off; off = shadow_note_impl_goals on (one-step, as live
steps-3-5 'on' option); ip = + shadow_note_impl_premise; sg = + shadow_lowering_stopgaps thing,narrow; ipsg = both.
Judgments: b01..b105 = trivial-filter-coref verdicts (master-shadow-wiring), n.. = note-implication-goals-v2
both/verdicts_nimpl.tsv (14 rows), any other proved goal -> '?' (must be judged by hand; asserted 0 or listed).
Admit: pc_admit.load_candidates in a private mode-700 temp dir removed at exit.  Usage: recompute_ipp.py EV REPO"""
import sys, os, json, csv, tempfile, shutil, atexit
from collections import Counter
EV, REPO = sys.argv[1], sys.argv[2]
sys.path.insert(0, REPO)
from wmtm import pc_admit as P
sys.path.insert(0, os.path.join(REPO, "reports", "t-2026-11-14-wmtm-trivial-filter-coref", "tools"))
import rescore as RS
MSW = "/srv/hive-evidence/t-2026-11-15-wmtm-master-shadow-wiring"
NI = "/srv/hive-evidence/t-2026-11-17-wmtm-note-implication-goals-v2/both/verdicts_nimpl.tsv"
BASE_EV = "/srv/hive-evidence/t-2026-11-14-wmtm-render-master-goals"
RX = "/srv/hive-evidence/t-2026-11-12-wmtm-parser-master-adopt-v2/armB/verdicts/reader_expect.tsv"
TMP = tempfile.mkdtemp(prefix="ipp_"); os.chmod(TMP, 0o700); atexit.register(lambda: shutil.rmtree(TMP, ignore_errors=True))
J = lambda p: json.load(open(p)); JL = lambda p: [json.loads(l) for l in open(p) if l.strip()][-1]
notes = [l.strip() for l in open(os.path.join(EV, "note_ids.txt")) if l.strip()]
vd = {r["goal"]: r["verdict"][0].upper() for f in ("verdicts_restate.tsv", "verdicts23.tsv")
      for r in RS.tsv(os.path.join(MSW, "inputs", "verdicts", f))}
restate = {r["goal"] for r in RS.tsv(os.path.join(MSW, "inputs", "verdicts", "verdicts_restate.tsv"))}
ref = JL(os.path.join(MSW, "run_apply/shadow.jsonl"))
gid = {RS.norm(q["goal"]): "b%02d" % (i + 1) for i, q in enumerate(ref["queries"])}
ni = list(csv.DictReader(open(NI), delimiter="\t"))
for i, r in enumerate(ni):
    gid[RS.norm(r["goal"])] = "n%02d" % (i + 1); vd["n%02d" % (i + 1)] = r["verdict"][0].upper()
def cw(ids): k = Counter(vd.get(i, "?") for i in ids); return k["C"], k["W"], k["U"], k["?"]
def rule(v, r): return "HOLDS" if v[0] >= r[0] and v[1] <= r[1] else "FAILS"
base_rs, _ = RS.compute(BASE_EV); A = tuple(int(x[:-1]) for x in base_rs["inputs"]["A_v3"].split("/"))
reader = list(csv.DictReader(open(RX), delimiter="\t")); assert len(reader) == 75
got = {x["note"] + "." + x["sent"] for x in reader if x["status"] == "got"}
out = {"live_A_CW": "%dC/%dW" % A, "arms": {}}
lines_of = {}
for a in ("base", "off", "ip", "sg", "ipsg", "ipsg_s300"):
    s = JL(os.path.join(EV, a, "shadow.jsonl")); sp = J(os.path.join(EV, a, "spec.json")); gr = sp["goal_rule"]
    nn = 0; ids = []
    for q in s["queries"]:
        k = RS.norm(q["goal"])
        if k not in gid:
            nn += 1; gid[k] = "x%02d" % nn if not str(gr.get(q["goal"], "")).startswith("nimplp:") else "p" + str(len(gid))
        ids.append(gid[k])
    proved = [i for i, q in zip(ids, s["queries"]) if q.get("ok")]
    pgoals = [i for i, q in zip(ids, s["queries"]) if str(gr.get(q["goal"], "")).startswith("nimplp:")]
    adm = J(os.path.join(EV, a, "admit.json")); sd = os.path.join(TMP, a); os.makedirs(sd, mode=0o700)
    json.dump(adm, open(os.path.join(sd, P.ADMIT_FILE), "w"))
    c, info = P.load_candidates({"shadow_dir": sd, "reasoner_max_admit": 1000, "gate_max_per_fact": 0}, None,
                                now=float(adm.get("spec_ts") or adm["ts"]) + 1, live_ids=notes)
    ag = [gid.get(RS.norm(x.provenance["goal"]), "?") for x in (c or [])]
    new_proved = [i for i in proved if i[0] != "b"]
    L = {"all": cw(proved), "non_restatement": cw([i for i in proved if i not in restate]), "admitted": cw(ag)}
    lines_of[a] = L
    out["arms"][a] = {"goals": s["goals_n"], "proved": len(proved), "timeouts": s["timeouts"], "status": s["status"],
                      "canary_ok": bool((s.get("canary") or {}).get("ok")),
                      "premise_goals_built": len(pgoals), "premise_goals_proved": sum(1 for i in pgoals if i in proved),
                      "new_proved_vs_base": len(new_proved), "new_proved_CWU?": cw(new_proved),
                      "proofs_using_stopgap": sum("stopgap_" in str(q.get("proof")) for q in s["queries"]),
                      "admitted": len(ag), "admitted_CWU?": cw(ag), "trivial_refused": len(info.get("trivial_refused") or []),
                      "reader_rows_of_75": len(got)}
for a in out["arms"]:
    out["arms"][a]["count_rule"] = {k: {"C/W/U/unjudged": "%d/%d/%d/%d" % v, "vs_live_A": rule(v, A),
                                        "vs_flags_off(base)": rule(v, lines_of["base"][k]), "vs_off": rule(v, lines_of["off"][k])}
                                    for k, v in lines_of[a].items()}
print(json.dumps(out, indent=1, sort_keys=True, default=str))
