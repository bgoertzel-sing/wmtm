#!/usr/bin/env python3
"""t-2026-11-14-wmtm-trivial-filter-coref: counts-only recompute (ids, rule ids, counts, hashes; no note text).
Usage (repo root of the branch): python3 reports/t-2026-11-14-wmtm-trivial-filter-coref/tools/recompute.py EV
1. checks EV/SHA256SUMS;  2. re-runs the filter (wmtm.pc_admit from this repo) over EV/inputs and checks the result
equals the stored tables (EV/tables/goals_*.tsv, counts.json);  3. recounts the report tables from goals_*.tsv and
the stored M17 counts and prints them.  Ends RECOMPUTE_OK or RECOMPUTE_FAIL."""
import sys, os, json, hashlib, csv
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rescore
EV = sys.argv[1]; bad = 0
for line in open(os.path.join(EV, "SHA256SUMS")):
    h, f = line.split(None, 1); f = f.strip().lstrip("*")
    if hashlib.sha256(open(os.path.join(EV, f), "rb").read()).hexdigest() != h:
        print("SHA MISMATCH", f); bad += 1
print("sha256sums checked:", sum(1 for _ in open(os.path.join(EV, "SHA256SUMS"))), "files, mismatches", bad)
out, rows = rescore.compute(EV)
stored = json.load(open(os.path.join(EV, "tables", "counts.json")))
same = json.loads(json.dumps(out, sort_keys=True)) == stored
print("re-run filter equals stored counts.json:", same); bad += not same
T = {}
for arm in rescore.ARMS:
    T[arm] = list(csv.DictReader(open(os.path.join(EV, "tables", "goals_%s.tsv" % arm)), delimiter="\t"))
    live = [(r["goal_id"], r["rule"], r["a_narrow"] or "-", r["b_wide"] or "-", r["verdict"]) for r in rows[arm]]
    st = [(r["goal_id"], r["rule"], r["split_a_narrow"], r["split_b_wide"], r["verdict"]) for r in T[arm]]
    print("re-run filter equals stored goals_%s.tsv:" % arm, live == st); bad += live != st
    g = out["goals"][arm]
    nar = sum(1 for r in rows[arm] if r["a_narrow"])
    cn = g["load_candidates_canary"]
    print(arm, "goals", g["n"], "proved", g["proved"], "admit proofs equal shadow", g["admit_proofs_equal_shadow"],
          "| load_candidates raw dropped", g["load_candidates_raw"]["dropped"], "refused", g["load_candidates_raw"]["trivial_refused_n"],
          "| canary refused", cn["trivial_refused_n"], cn["refused_by_reason"], "direct", nar)
    if cn["trivial_refused_n"] != nar or not g["admit_proofs_equal_shadow"]:
        print("CANARY MISMATCH", arm); bad += 1
a = stored["inputs"]
print("A_v3", a["A_v3"], "proved", a["A_v3_proved"], "refused", a["A_v3_refused"])
for r, x in sorted(stored["m17"].items()):
    j = x["as_judged"]
    print("M17", r, "n=%d as judged %dC/%dW" % (x["n"], j["C"], j["W"]), "| shipped-filter reasons", x["refused_by_reason_narrow"],
          "|", " | ".join("%s: refused %d, left %dC/%dW" % (sp, x[sp]["refused"], x[sp]["C"], x[sp]["W"]) for sp in rescore.SPLITS))
print("split | arm | admitted C/W/U | refused | vs A_v3 | vs M17 r1/r2/r3 as judged | vs M17 filtered | Mesto kept/dropped (new drops) | W1")
for sp in rescore.SPLITS:
    for arm in rescore.ARMS:
        R = [r for r in T[arm] if r["proved"] == "True"]
        adm = [r for r in R if r["split_" + sp] == "-"]
        c = Counter(r["verdict"] for r in adm)
        C, W, U = c["correct"], c["wrong"], c["unclear"]
        vA = rescore.rule_verdict(C, W, *map(int, stored["inputs"]["A_v3"].replace("C", "").replace("W", "").split("/")))
        vM = "/".join(rescore.rule_verdict(C, W, x["as_judged"]["C"], x["as_judged"]["W"]) for _, x in sorted(stored["m17"].items()))
        vF = "/".join(rescore.rule_verdict(C, W, x[sp]["C"], x[sp]["W"]) for _, x in sorted(stored["m17"].items()))
        so = stored["splits"][sp][arm]
        w1 = sum(int(r["notes"]) > 1 for r in adm)
        ok = (C, W, U, vA, w1) == (so["C"], so["W"], so["U"], so["vs_A_v3"], so["w1_multi_note_admitted"]) and \
            vM == "/".join(v for _, v in sorted(so["vs_M17"].items())) and vF == "/".join(v for _, v in sorted(so["vs_M17_filtered"].items()))
        bad += not ok
        print(sp, arm, "%d/%d/%d" % (C, W, U), len(R) - len(adm), vA, vM, vF,
              "%d/%d (%d)" % (so["mesto_kept"], so["mesto_dropped"], len(so["mesto_newly_dropped_by_filter"])), w1,
              "" if ok else "TABLE MISMATCH")
cs = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "SHA256SUMS")
if os.path.exists(cs):
    same = open(cs, "rb").read() == open(os.path.join(EV, "SHA256SUMS"), "rb").read()
    print("committed SHA256SUMS equals evidence SHA256SUMS:", same); bad += not same
print("RECOMPUTE_FAIL" if bad else "RECOMPUTE_OK")
