#!/usr/bin/env python3
"""t-2026-11-11-wmtm-spread-seeds-probe: the order's table for arms A, C, D, E from results/summary.json (analyse3.py)
and the arms' turns.jsonl, plus hubs lost on keyword turns.

Hubs lost (every probe turn is a keyword query): an on-topic planted-useful hub that arm A (keyword only) showed on
that turn and arm X did not show.  "evicted in-turn" = of those, the hub was resident at the start of the turn in X
and was evicted during the turn by X's admissions (the churn reaching a resident hub).
Usage: table4.py --data data --results results"""
import argparse, json, os, collections as C
ap = argparse.ArgumentParser(); ap.add_argument("--data", required=True); ap.add_argument("--results", required=True)
a = ap.parse_args()
LAB = json.load(open(os.path.join(a.data, "labels.json")))["labels"]
S = json.load(open(os.path.join(a.results, "summary.json")))
W = S["whole_run"]; arms = S["arms"]
rows = {k: [json.loads(l) for l in open(os.path.join(a.results, k, "turns.jsonl"))] for k in arms}
def hub_on(cid, t):
    l = LAB.get(cid); return bool(l and l["useful"] and l["role"] == "hub" and l["topic"] == t)
out = {}
for k in arms:
    w = W[k]
    lost, lost_ev, turns, turns_ev, kinds = 0, 0, set(), set(), C.Counter()
    if k != "A":
        for ra, rx in zip(rows["A"], rows[k]):
            t = ra["topic"]
            miss = {c for c in ra["shown"] if hub_on(c, t)} - set(rx["shown"])
            ev = {e["id"] for e in rx["evicts"]}
            mev = {c for c in miss if c in rx["store_before"] and c in ev}
            lost += len(miss); lost_ev += len(mev)
            if miss: turns.add(ra["i"]); kinds[ra["kind"]] += 1
            if mev: turns_ev.add(ra["i"])
    comp = W.get("%s_graph_only_admit_composition" % k, {})
    go = sum(comp.values())
    out[k] = {
        "admitted": w["admitted"], "admitted_graph_only": w["admitted_graph_only"], "admitted_keyword": w["admitted_keyword"],
        "admitted_on_topic_useful": w["admitted_useful"], "precision_admitted_on_topic": w["precision_admitted_on_topic"],
        "evictions": w["evicted"], "evicted_by_graph_only_admit": w["evicted_by_graph_only_admit"],
        "useful_evicted": w["evicted_useful_any_topic"], "useful_hubs_evicted": w["evicted_useful_hubs"],
        "first_turn_with_eviction": w["first_turn_store_full"], "max_store": w["max_store"],
        "turns_recall_cut_full": w["turns_top_k_full"], "max_new_in_one_turn": w["max_new_recalled_in_one_turn"],
        "useful_shown_on_topic": w["shown_useful"], "shown_total": w["shown_total"], "precision_shown": w["precision_shown_on_topic"],
        "first_visit_coverage": [w["coverage_useful_shown_first_visit"][x] for x in ("shown", "planted", "hubs", "linked")],
        "revisit_coverage": w["coverage_revisit_total"],
        "graph_only_off_topic_share": None if not go else round((comp.get("other_topic_useful", 0) + comp.get("other_topic_noise", 0)) / go, 4),
        "graph_only_composition": comp,
        "hubs_lost_vs_A": lost, "hubs_lost_turns": len(turns), "hubs_lost_turn_kinds": dict(kinds),
        "hubs_lost_evicted_in_turn": lost_ev, "hubs_lost_evicted_turns": sorted(turns_ev),
        "disp_vs_A": {kk: vv for kk, vv in W.get("context_displacement_%s_vs_A" % k, {}).items() if kk != "by_turn"},
    }
json.dump(out, open(os.path.join(a.results, "table4.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
