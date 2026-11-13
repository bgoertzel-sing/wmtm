#!/usr/bin/env python3
"""t-2026-11-13-wmtm-spread-seed-sweep: the probe's table (tools/table4.py of t-2026-11-11-wmtm-spread-seeds-probe, same
definitions) for arms A, E, F50, F25, P10, P25, plus a by-turn-kind split and the no-match turns.

No-match turn: no journal cluster matches the turn's query by keyword (RecallBridge._keyword_matches over every
cluster, resident or not: exactly the condition under which spread_seed_ids("turn") has no keyword seeds and the
fallback fires).  It depends only on the query and the journal, so it is the same in every arm.
Seeds added per turn (F/P arms) = ceil(n * x / 100) of the n residents at recall time (recall_calls n_active).
Usage: table5.py --code <this branch's worktree> --data data --results results"""
import argparse, json, math, os, sys, collections as C
ap = argparse.ArgumentParser()
for k in ("--code", "--data", "--results"): ap.add_argument(k, required=True)
a = ap.parse_args()
sys.path.insert(0, a.code)
from wmtm.recall_bridge import RecallBridge, parse_journal
LAB = json.load(open(os.path.join(a.data, "labels.json")))["labels"]
S = json.load(open(os.path.join(a.results, "summary.json")))
W = S["whole_run"]; arms = S["arms"]; PT = S["per_turn"]
rows = {k: [json.loads(l) for l in open(os.path.join(a.results, k, "turns.jsonl"))] for k in arms}
rb = RecallBridge(parse_journal(open(os.path.join(a.data, "journal.metta")).read().splitlines(True)))
nomatch = {}
for r in rows["E"]:
    qt = rb._tokenize(r["q"])
    nomatch[r["i"]] = not any(rb._keyword_matches(c, qt) for c in rb._clusters)
PCT = {"F50": ("fallback", 50), "F25": ("fallback", 25), "P10": ("add", 10), "P25": ("add", 25)}
def hub_on(cid, t):
    l = LAB.get(cid); return bool(l and l["useful"] and l["role"] == "hub" and l["topic"] == t)
out = {"no_match_turns": [[r["i"], r["kind"]] for r in rows["E"] if nomatch[r["i"]]],
       "no_match_turn_kinds": dict(C.Counter(r["kind"] for r in rows["E"] if nomatch[r["i"]])),
       "match_turn_kinds": dict(C.Counter(r["kind"] for r in rows["E"] if not nomatch[r["i"]])), "arms": {}}
for k in arms:
    w = W[k]
    lost, lost_ev, turns, turns_ev = 0, 0, set(), set()
    if k != "A":
        for ra, rx in zip(rows["A"], rows[k]):
            t = ra["topic"]
            miss = {c for c in ra["shown"] if hub_on(c, t)} - set(rx["shown"])
            ev = {e["id"] for e in rx["evicts"]}
            mev = {c for c in miss if c in rx["store_before"] and c in ev}
            lost += len(miss); lost_ev += len(mev)
            if miss: turns.add(ra["i"])
            if mev: turns_ev.add(ra["i"])
    comp = W.get("%s_graph_only_admit_composition" % k, {})
    go = sum(comp.values())
    full = sum(1 for r in rows[k] if len(r["store_after"]) >= 60)
    added = []
    if k in PCT:
        mode, x = PCT[k]
        for r in rows[k]:
            n = r["recall_calls"][0]["n_active"] if r["recall_calls"] else 0
            fires = mode == "add" or nomatch[r["i"]]
            added.append(0 if not (fires and n) else min(n, max(1, math.ceil(n * x / 100 - 1e-9))))
    out["arms"][k] = {
        "admitted": w["admitted"], "admitted_graph_only": w["admitted_graph_only"],
        "admitted_on_topic_useful": w["admitted_useful"], "precision_admitted_on_topic": w["precision_admitted_on_topic"],
        "evictions": w["evicted"], "useful_evicted": w["evicted_useful_any_topic"], "useful_hubs_evicted": w["evicted_useful_hubs"],
        "first_turn_with_eviction": w["first_turn_store_full"], "max_store": w["max_store"],
        "turns_store_at_capacity": full, "turns_budget_binds": w["turns_top_k_full"],
        "graph_only_off_topic_share": None if not go else round((comp.get("other_topic_useful", 0) + comp.get("other_topic_noise", 0)) / go, 4),
        "graph_only_off_topic": [comp.get("other_topic_useful", 0) + comp.get("other_topic_noise", 0), go],
        "useful_shown_on_topic": w["shown_useful"], "shown_total": w["shown_total"], "precision_shown": w["precision_shown_on_topic"],
        "first_visit_coverage": [w["coverage_useful_shown_first_visit"][x] for x in ("shown", "planted", "hubs", "linked")],
        "revisit_coverage": w["coverage_revisit_total"],
        "hubs_lost_vs_A": lost, "hubs_lost_turns": len(turns), "hubs_lost_evicted_in_turn": lost_ev,
        "hubs_lost_evicted_turns": sorted(turns_ev),
        "seeds_added_total": sum(added) if added else None, "turns_seeds_added": sum(1 for v in added if v) if added else None,
        "seeds_added_per_turn": added or None,
    }
    byk = C.defaultdict(C.Counter)
    for x in PT[k]:
        g = "Q3/R3" if x["kind"] in ("Q3", "R3") else x["kind"]
        for grp in (g, "no-match" if nomatch[x["i"]] else "match"):
            for c in ("admitted", "admitted_go", "adm_useful", "evicted", "evicted_useful_any", "shown", "shown_useful"):
                byk[grp][c] += x[c]
            byk[grp]["turns"] += 1
    out["arms"][k]["by_kind"] = {g: dict(v) for g, v in byk.items()}
json.dump(out, open(os.path.join(a.results, "table5.json"), "w"), indent=1)
L = ["| | " + " | ".join(arms) + " |", "|---|" + "---|" * len(arms)]
def row(name, f): L.append("| %s | " % name + " | ".join(f(k, out["arms"][k]) for k in arms) + " |")
row("admitted (new, recalled)", lambda k, d: str(d["admitted"]))
row("of which graph-only", lambda k, d: str(d["admitted_graph_only"]))
row("on-topic useful admitted", lambda k, d: str(d["admitted_on_topic_useful"]))
row("precision of admitted (on-topic)", lambda k, d: "%.2f" % d["precision_admitted_on_topic"])
row("graph-only admissions from another topic", lambda k, d: "n/a" if d["graph_only_off_topic_share"] is None else "%d of %d (%d%%)" % (d["graph_only_off_topic"][0], d["graph_only_off_topic"][1], round(100 * d["graph_only_off_topic_share"])))
row("evictions (capacity)", lambda k, d: str(d["evictions"]))
row("useful evicted (hubs)", lambda k, d: "%d (%d)" % (d["useful_evicted"], d["useful_hubs_evicted"]))
row("first turn with an eviction", lambda k, d: str(d["first_turn_with_eviction"]))
row("turns with the store at capacity (max store)", lambda k, d: "%d (max %d)" % (d["turns_store_at_capacity"], d["max_store"]))
row("turns the budget (10) binds", lambda k, d: str(d["turns_budget_binds"]))
row("useful shown (on-topic)", lambda k, d: str(d["useful_shown_on_topic"]))
row("items shown / precision of shown", lambda k, d: "%d / %.2f" % (d["shown_total"], d["precision_shown"]))
row("first-visit coverage (hubs + linked)", lambda k, d: "%d/%d (%d+%d)" % tuple(d["first_visit_coverage"]))
row("revisit coverage", lambda k, d: "%d/%d" % tuple(d["revisit_coverage"]))
row("hubs lost vs A (turns)", lambda k, d: "-" if k == "A" else "%d (%d)" % (d["hubs_lost_vs_A"], d["hubs_lost_turns"]))
row("of which evicted in-turn", lambda k, d: "-" if k == "A" else str(d["hubs_lost_evicted_in_turn"]))
row("resident seeds added (turns)", lambda k, d: "-" if d["seeds_added_total"] is None else "%d (%d)" % (d["seeds_added_total"], d["turns_seeds_added"]))
L += ["", "By turn kind, per arm: admitted / graph-only admitted / on-topic useful admitted / evictions / useful evicted / on-topic useful shown", "",
      "| kind (turns) | " + " | ".join(arms) + " |", "|---|" + "---|" * len(arms)]
for g in ("Q1", "Q2", "Q3/R3", "R1", "R2", "match", "no-match"):
    if g not in out["arms"]["E"]["by_kind"]: continue
    n = out["arms"]["E"]["by_kind"][g]["turns"]
    L.append("| %s (%d) | " % (g, n) + " | ".join("%d / %d / %d / %d / %d / %d" % tuple(out["arms"][k]["by_kind"][g].get(c, 0) for c in ("admitted", "admitted_go", "adm_useful", "evicted", "evicted_useful_any", "shown_useful")) for k in arms) + " |")
open(os.path.join(a.results, "table5.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L)); print(json.dumps({k: v for k, v in out.items() if k != "arms"}))
