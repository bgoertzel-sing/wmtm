#!/usr/bin/env python3
"""Per-turn recall admit table from turn_loop recall_*.json (ids/scores/STIs only, no note text).
Usage: admit_table.py <run dir> ...  -> JSON {arm: {"turns": [...], "totals": {...}}}"""
import json, os, sys, glob, statistics as S
out = {}
for d in sys.argv[1:]:
    arm = os.path.basename(d.rstrip("/")); rows = []
    for f in sorted(glob.glob(os.path.join(d, "out", "recall_*.json"))):
        i, kind = os.path.basename(f)[7:-5].split("_")
        r = json.load(open(f)); new = r["new"]; adm = [x for x in new if x["admitted"]]
        g = [x for x in adm if x["graph_only"]]
        cands = [c for call in r["calls"] for c in call["cands"]]
        rows.append({"i": int(i), "kind": kind, "calls": len(r["calls"]), "cands": len(cands),
                     "cands_graph_only": sum(c["graph_only"] for c in cands), "admitted": len(adm),
                     "admitted_graph_only": len(g),
                     "sti_planned_kw": [x["sti_planned"] for x in adm if not x["graph_only"]],
                     "sti_planned_graph": [x["sti_planned"] for x in g],
                     "sti_end_graph": [x["sti_end"] for x in g],
                     "score_graph": [x["score"] for x in g]})
    U = [x for x in rows if x["kind"] == "user"]
    gs = [v for x in U for v in x["sti_planned_graph"]]
    out[arm] = {"turns": rows, "totals": {
        "user_turns": len(U), "admitted": sum(x["admitted"] for x in U),
        "admitted_graph_only": sum(x["admitted_graph_only"] for x in U),
        "turns_with_graph_only": sum(1 for x in U if x["admitted_graph_only"]),
        "graph_sti_planned_min_med_max": [min(gs), S.median(gs), max(gs)] if gs else None}}
print(json.dumps(out, indent=1))
