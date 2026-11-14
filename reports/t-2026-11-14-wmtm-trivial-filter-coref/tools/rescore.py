#!/usr/bin/env python3
"""t-2026-11-14-wmtm-trivial-filter-coref: re-score the parser-master-adopt-v2 B set with the extended trivial filter.

compute(EV) reads only EV/inputs (copies of the v2 evidence, note-derived, kept apart) and returns id/count tables:
per goal: goal id, rule id, filter reason under split (a) narrow (pc_admit.RESTATEMENT_RULES, the shipped default) and
split (b) wide (also all six coref role rules), hand verdict, note count; then per split the admitted C/W/U, the count
rule against A_v3 (live F3 v3) and M17 r1/r2/r3, Mesto s11 (earlier conclusions kept/dropped) and W1.
No parse calls; the filter is wmtm.pc_admit.trivial_reason from the repo this file sits in.
Usage: python3 reports/<task>/tools/rescore.py EV   -> writes EV/tables/*.tsv, EV/tables/counts.json (ids/counts only)."""
import sys, os, json, re, csv, time
from collections import Counter
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, REPO)
from wmtm import pc_admit as P

ROLE = tuple(P.COREF_ROLE_RULES)
SPLITS = {"a_narrow": None, "b_wide": dict(P.RESTATEMENT_RULES, **{r: "coref_restatement" for r in ROLE})}
ARMS = ("full_s2", "sens_s2")
norm = lambda g: g.replace("__i_ep_note_", "__ep_note_").strip()


def rid(r):
    """rule id for tables: the parser's per-sentence implication rules carry a note label; collapse them to one id."""
    return "parser_implication" if re.search(r"_implication(_\d+)?__", r) else r


def lc(arm, adm, mutate):
    """Real admission path (pc_admit.load_candidates, filter flag at its default = on) over this arm's admit.json."""
    if mutate:   # canary: renderable synthetic goal + live source, proof and rules unchanged, so every result reaches the filter
        adm = dict(adm, results=[dict(r, goal="(Member sk_canary c%d)" % i, sources=["n1"]) for i, r in enumerate(adm["results"])])
    sd = os.path.join("/tmp/tfc_lc", arm + ("_canary" if mutate else "_raw")); os.makedirs(sd, exist_ok=True)
    json.dump(adm, open(os.path.join(sd, P.ADMIT_FILE), "w"))
    _, info = P.load_candidates({"shadow_dir": sd, "reasoner_max_admit": 1000, "gate_max_per_fact": 0}, None,
                                now=float(adm.get("spec_ts") or adm["ts"]) + 1,
                                live_ids=["n1"] + sorted({x for r in adm["results"] for x in r.get("sources") or []}))
    return {"dropped": info.get("dropped"), "trivial_refused_n": info.get("trivial_refused_n"),
            "refused_by_reason": dict(sorted(Counter(e["reason"] for e in info.get("trivial_refused") or []).items()))}


def tsv(p):
    return list(csv.DictReader(open(p), delimiter="\t"))


def rule_verdict(C, W, aC, aW):
    return "HOLDS" if C >= aC and W <= aW else "FAILS"


def compute(EV):
    I = os.path.join(EV, "inputs")
    vd = {r["goal"]: r["verdict"] for f in ("verdicts_restate.tsv", "verdicts23.tsv", "verdicts_sens_impl.tsv")
          for r in tsv(os.path.join(I, "verdicts", f))}
    J = json.load(open(os.path.join(I, "f3v3_JUDGMENTS.json")))
    aC, aW = J["A_v3"]["counts"]["correct"], J["A_v3"]["counts"]["wrong"]
    aq = [q for q in json.loads(open(os.path.join(I, "f3v3_v3_A.shadow.jsonl")).readlines()[-1])["queries"] if q.get("ok")]
    a_ref = {sp: sum(bool(P.trivial_reason(q.get("proof"), q.get("rules"), R)) for q in aq) for sp, R in SPLITS.items()}
    a_ref["proved_judged"] = sum(q["goal"] in {r["goal"] for r in J["A_v3"]["rows"]} for q in aq)
    # old loader M17: goals per run, verdicts (B_v3 rows + 5 extra), proofs from each run's admit.json
    mv = {norm(r["goal"]): r["verdict"].lower() for r in J["B_v3"]["rows"]}
    mv.update({norm(r["goal"]): r["verdict"].lower() for r in tsv(os.path.join(I, "verdicts", "verdicts_m17_extra.tsv"))})
    runs = {}
    for l in open(os.path.join(I, "old_loader_goals.txt")):
        p = l.split(None, 2)
        if len(p) == 3 and p[0].startswith("M17"):
            runs.setdefault(p[0], []).append(norm(p[2]))
    out = {"inputs": {"A_v3": "%dC/%dW" % (aC, aW), "A_v3_proved": len(aq), "A_v3_refused": a_ref},
           "goals": {}, "splits": {}, "m17": {}}
    m17 = {}
    for r, gs in sorted(runs.items()):
        adm = json.load(open(os.path.join(I, "old_loader", r, "admit.json")))["results"]
        pf = {norm(x["goal"]): x for x in adm}
        cj = Counter(mv.get(g, "unjudged") for g in gs)
        row = {"n": len(gs), "missing_proof": sum(g not in pf for g in gs), "as_judged": {"C": cj["correct"], "W": cj["wrong"],
               "U": cj["unclear"], "unjudged": cj["unjudged"]},
               "refused_by_reason_narrow": dict(Counter(P.trivial_reason(pf[g]["proof"], pf[g].get("rules")) or "-" for g in gs if g in pf))}
        for sp, R in SPLITS.items():
            keep = [g for g in gs if not (g in pf and P.trivial_reason(pf[g]["proof"], pf[g].get("rules"), R))]
            c = Counter(mv.get(g, "unjudged") for g in keep)
            row[sp] = {"admitted": len(keep), "refused": len(gs) - len(keep), "C": c["correct"], "W": c["wrong"],
                       "U": c["unclear"], "unjudged": c["unjudged"]}
        m17[r] = row
    out["m17"] = m17
    earlier = {}
    for k in ("A_v3", "B_v3"):
        for r in J[k]["rows"]:
            earlier.setdefault(norm(r["goal"]), {})[k] = r["verdict"].lower()
    for r, gs in runs.items():
        for g in gs:
            earlier.setdefault(g, {})[r] = mv.get(g, "unjudged")
    rows = {}
    for arm in ARMS:
        A = os.path.join(I, "armB", arm)
        d = json.loads(open(os.path.join(A, "shadow.jsonl")).readlines()[-1]); s = json.load(open(os.path.join(A, "spec.json")))
        gr = s.get("goal_rule", {})
        lab2note = {}
        for k, x in s.get("master_ops", []):
            m = re.match(r"\(: (\S+) ", x)
            n = re.search(r"__ep_note_(\d{8}T\d{6}Z)", x)
            if k == "atom" and m and n:
                lab2note[m.group(1)] = n.group(1)
        R = []
        for i, q in enumerate(d["queries"]):
            p = q.get("proof") or ""
            notes = sorted({lab2note[t] for t in re.findall(r"[A-Za-z0-9_]+", p) if t in lab2note})
            gid = "b%02d" % (i + 1)
            R.append({"goal_id": gid, "rule": rid(gr.get(q["goal"], "?")), "ok": bool(q.get("ok")),
                      "a_narrow": P.trivial_reason(p, {}) or "", "b_wide": P.trivial_reason(p, {}, SPLITS["b_wide"]) or "",
                      "verdict": vd.get(gid, "unjudged"), "notes": len(notes), "goal": norm(q["goal"])})
        adm = json.load(open(os.path.join(A, "admit.json")))
        same = [x["proof"] for x in adm["results"]] == [q.get("proof") for q in d["queries"] if q.get("ok")]
        rows[arm] = R
        out["goals"][arm] = {"n": len(R), "proved": sum(r["ok"] for r in R), "admit_results": len(adm["results"]),
                             "admit_proofs_equal_shadow": same,
                             "load_candidates_raw": lc(arm, adm, False), "load_candidates_canary": lc(arm, adm, True),
                             "by_rule": dict(sorted(Counter(r["rule"] for r in R).items()))}
    for sp in SPLITS:
        so = {}
        for arm in ARMS:
            R = rows[arm]
            adm = [r for r in R if r["ok"] and not r[sp]]
            ref = [r for r in R if r["ok"] and r[sp]]
            c = Counter(r["verdict"] for r in adm); C, W, U = c["correct"], c["wrong"], c["unclear"]
            kept = sorted(r["goal_id"] for r in adm if r["goal"] in earlier)
            kept_before = sorted(r["goal_id"] for r in R if r["ok"] and r["goal"] in earlier)
            so[arm] = {"admitted": len(adm), "refused": len(ref), "C": C, "W": W, "U": U, "unjudged": c["unjudged"],
                       "refused_by_reason": dict(sorted(Counter(r[sp] for r in ref).items())),
                       "refused_by_rule": dict(sorted(Counter(r["rule"] for r in ref).items())),
                       "refused_CWU": dict(sorted(Counter(r["verdict"] for r in ref).items())),
                       "admitted_by_rule": dict(sorted(Counter(r["rule"] for r in adm).items())),
                       "admitted_wrong_ids": sorted(r["goal_id"] for r in adm if r["verdict"] == "wrong"),
                       "admitted_unclear_ids": sorted(r["goal_id"] for r in adm if r["verdict"] == "unclear"),
                       "refused_wrong_ids": sorted(r["goal_id"] for r in ref if r["verdict"] == "wrong"),
                       "vs_A_v3": rule_verdict(C, W, aC, aW),
                       "vs_M17": {r: rule_verdict(C, W, m17[r]["as_judged"]["C"], m17[r]["as_judged"]["W"]) for r in sorted(m17)},
                       "vs_M17_filtered": {r: rule_verdict(C, W, m17[r][sp]["C"], m17[r][sp]["W"]) for r in sorted(m17)},
                       "mesto_earlier": len(earlier), "mesto_kept": len(kept), "mesto_kept_ids": kept,
                       "mesto_dropped": len(earlier) - len(kept),
                       "mesto_newly_dropped_by_filter": sorted(set(kept_before) - set(kept)),
                       "w1_multi_note_admitted": sum(r["notes"] > 1 for r in adm),
                       "w1_wrong_multi_note_admitted": sum(r["notes"] > 1 and r["verdict"] == "wrong" for r in adm)}
        out["splits"][sp] = so
    return out, rows


def write(EV, out, rows):
    T = os.path.join(EV, "tables"); os.makedirs(T, exist_ok=True)
    for arm, R in rows.items():
        with open(os.path.join(T, "goals_%s.tsv" % arm), "w") as f:
            f.write("goal_id\trule\tproved\tsplit_a_narrow\tsplit_b_wide\tverdict\tnotes\n")
            for r in R:
                f.write("%s\t%s\t%s\t%s\t%s\t%s\t%d\n" % (r["goal_id"], r["rule"], r["ok"], r["a_narrow"] or "-",
                                                         r["b_wide"] or "-", r["verdict"], r["notes"]))
    json.dump(out, open(os.path.join(T, "counts.json"), "w"), indent=1, sort_keys=True)


if __name__ == "__main__":
    EV = sys.argv[1]
    out, rows = compute(EV)
    write(EV, out, rows)
    print(json.dumps(out["splits"], indent=1, sort_keys=True))
