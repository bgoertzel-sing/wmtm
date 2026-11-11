#!/usr/bin/env python3
"""t-2026-11-11-wmtm-graph-only-probe: join the planted labels to the A and B turn logs and compare.
Usage: analyse.py --data data --a results/A/turns.jsonl --b results/B/turns.jsonl --out results
Labels: an item is USEFUL at turn t when it is planted useful AND its topic is the turn's topic; everything else
(planted noise, distractors, background, useful items of another topic, request items) counts as NOISE at that turn.
The 'planted-useful (any topic)' variant is reported too."""
import argparse, json, os, collections as C
ap = argparse.ArgumentParser()
for k in ("--data", "--a", "--b", "--out"): ap.add_argument(k, required=True)
a = ap.parse_args()
LAB = json.load(open(os.path.join(a.data, "labels.json")))["labels"]
def load(p): return [json.loads(l) for l in open(p)]
ARMS = {"A": load(a.a), "B": load(a.b)}
assert [r["q"] for r in ARMS["A"]] == [r["q"] for r in ARMS["B"]], "turn scripts differ"
def lab(cid): return LAB.get(cid)
def useful_at(cid, topic):
    l = lab(cid); return bool(l and l["useful"] and l["topic"] == topic)
def any_useful(cid):
    l = lab(cid); return bool(l and l["useful"])
def kind(cid):
    l = lab(cid)
    if not l: return "request" if cid.startswith("user-") else "other"
    return "%s%s-%s" % (l["role"], "" if l["depth"] in (None, 0) else "-d%d" % l["depth"], "U" if l["useful"] else "N")

def per_turn(rows):
    out = []
    for r in rows:
        t = r["topic"]; src = {s["id"]: s for s in r["scored"]}
        new = [x for x in r["admits"] if x["new"] and x["source_type"] == "recalled"]
        go = [x for x in new if src.get(x["id"], {}).get("source") == "graph-only"]
        kw = [x for x in new if src.get(x["id"], {}).get("source") == "keyword"]
        pos = [s for s in r["scored"] if s["score"] > 0]
        ret = r["recall_calls"][0]["returned"] if r["recall_calls"] else []
        evs = r["evicts"]
        ev_by_go = [e for e in evs if src.get(e["by"], {}).get("source") == "graph-only"]
        out.append({
            "i": r["i"], "topic": t, "kind": r["kind"],
            "scored_pos": len(pos), "scored_kw": sum(s["source"] == "keyword" for s in pos),
            "scored_go": sum(s["source"] == "graph-only" for s in pos),
            "cut_floor": sum(s.get("cut") == "floor" for s in r["scored"]),
            "cut_topk": sum(s.get("cut") == "top_k" for s in r["scored"]),
            "cut_topk_useful": sum(s.get("cut") == "top_k" and useful_at(s["id"], t) for s in r["scored"]),
            "cut_topk_kw": sum(s.get("cut") == "top_k" and s["source"] == "keyword" for s in r["scored"]),
            "returned": len(ret), "admitted": len(new), "admitted_go": len(go), "admitted_kw": len(kw),
            "adm_useful": sum(useful_at(x["id"], t) for x in new), "adm_noise": sum(not useful_at(x["id"], t) for x in new),
            "adm_go_useful": sum(useful_at(x["id"], t) for x in go),
            "adm_any_useful": sum(any_useful(x["id"]) for x in new),
            "sti_go": [x["initial_sti"] for x in go], "sti_kw": [x["initial_sti"] for x in kw],
            "shown": len(r["shown"]), "shown_useful": sum(useful_at(c, t) for c in r["shown"]),
            "shown_noise": sum(not useful_at(c, t) for c in r["shown"]),
            "store": len(r["store_after"]), "evicted": len(evs), "evicted_by_go": len(ev_by_go),
            "evicted_useful_any": sum(any_useful(e["id"]) for e in evs),
            "evicted_kinds": dict(C.Counter(kind(e["id"]) for e in evs)),
            "kw_min": min([s["score"] for s in pos if s["source"] == "keyword"], default=None),
            "go_max": max([s["score"] for s in pos if s["source"] == "graph-only"], default=None),
            "violations": len(r.get("violations", [])), "err": r["err"],
        })
    return out
PT = {k: per_turn(v) for k, v in ARMS.items()}

def frac(n, d): return None if d == 0 else round(n / d, 4)
def whole(arm):
    rows, pt = ARMS[arm], PT[arm]
    s = lambda k: sum(x[k] for x in pt)
    # coverage: planted useful items of topic t shown in the main context block during any turn of topic t
    planted = C.defaultdict(set)
    for cid, l in LAB.items():
        if l["useful"] and l["topic"] is not None: planted[l["topic"]].add(cid)
    seen = C.defaultdict(set); seen_rev = C.defaultdict(set)
    for r in rows:
        for c in r["shown"]:
            if useful_at(c, r["topic"]):
                (seen_rev if r["kind"].startswith("R") else seen)[r["topic"]].add(c)
    rev_topics = sorted({r["topic"] for r in rows if r["kind"].startswith("R")})
    # revisit: on-topic useful items resident in the store / shown at the revisit turns
    rev = []
    for r in rows:
        if r["kind"].startswith("R"):
            t = r["topic"]
            rev.append({"i": r["i"], "topic": t, "kind": r["kind"],
                        "resident_useful": sum(useful_at(c, t) for c in r["store_after"]),
                        "shown_useful": sum(useful_at(c, t) for c in r["shown"]), "shown": len(r["shown"])})
    sti_go = [v for x in pt for v in x["sti_go"]]; sti_kw = [v for x in pt for v in x["sti_kw"]]
    return {
        "turns": len(pt), "admitted": s("admitted"), "admitted_graph_only": s("admitted_go"), "admitted_keyword": s("admitted_kw"),
        "admitted_useful": s("adm_useful"), "admitted_noise": s("adm_noise"),
        "precision_admitted_on_topic": frac(s("adm_useful"), s("admitted")),
        "precision_admitted_any_useful": frac(s("adm_any_useful"), s("admitted")),
        "precision_graph_only_admitted_on_topic": frac(s("adm_go_useful"), s("admitted_go")),
        "shown_total": s("shown"), "shown_useful": s("shown_useful"), "shown_noise": s("shown_noise"),
        "precision_shown_on_topic": frac(s("shown_useful"), s("shown")),
        "coverage_useful_shown_first_visit": {"shown": sum(len(v) for v in seen.values()), "planted": sum(len(v) for v in planted.values()),
                                              "frac": frac(sum(len(v) for v in seen.values()), sum(len(v) for v in planted.values()))},
        "coverage_by_topic_first_visit": {t: [len(seen[t]), len(planted[t])] for t in sorted(planted)},
        "coverage_revisit": {t: [len(seen_rev[t]), len(planted[t])] for t in rev_topics},
        "revisit_turns": rev,
        "evicted": s("evicted"), "evicted_by_graph_only_admit": s("evicted_by_go"), "evicted_useful_any_topic": s("evicted_useful_any"),
        "cut_by_floor": s("cut_floor"), "cut_by_top_k": s("cut_topk"), "cut_by_top_k_on_topic_useful": s("cut_topk_useful"),
        "cut_by_top_k_keyword": s("cut_topk_kw"),
        "turns_top_k_full": sum(x["returned"] >= 15 for x in pt),
        "sti_on_admit": {"graph_only": [min(sti_go, default=None), max(sti_go, default=None), round(sum(sti_go) / len(sti_go), 3) if sti_go else None],
                         "keyword": [min(sti_kw, default=None), max(sti_kw, default=None), round(sum(sti_kw) / len(sti_kw), 3) if sti_kw else None]},
        "min_keyword_score_vs_max_graph_only": [min([x["kw_min"] for x in pt if x["kw_min"] is not None], default=None),
                                               max([x["go_max"] for x in pt if x["go_max"] is not None], default=None)],
        "violations": max(x["violations"] for x in pt), "errors": sum(1 for x in pt if x["err"]),
    }
W = {k: whole(k) for k in ARMS}
# what B's graph-only admission displaced, relative to A, at the context level: on-topic useful items A showed at a
# turn that B did not show at that turn (and the reverse)
disp = []
for ra, rb in zip(ARMS["A"], ARMS["B"]):
    t = ra["topic"]
    ua = {c for c in ra["shown"] if useful_at(c, t)}; ub = {c for c in rb["shown"] if useful_at(c, t)}
    disp.append({"i": ra["i"], "kind": ra["kind"], "topic": t, "A_only_useful": sorted(ua - ub), "B_only_useful": sorted(ub - ua),
                 "A_only_useful_kinds": [kind(c) for c in sorted(ua - ub)]})
W["context_displacement_B_vs_A"] = {"turns_B_lost_a_useful_A_showed": sum(1 for d in disp if d["A_only_useful"]),
                                    "useful_lost": sum(len(d["A_only_useful"]) for d in disp),
                                    "useful_gained": sum(len(d["B_only_useful"]) for d in disp), "by_turn": [d for d in disp if d["A_only_useful"] or d["B_only_useful"]]}
# B evictions: kinds evicted, and what the evicted planted-useful items were needed for later
evk = C.Counter(); ev_needed = []
needed_later = C.defaultdict(list)
rowsB = ARMS["B"]
for r in rowsB:
    for e in r["evicts"]:
        evk[kind(e["id"])] += 1
        l = lab(e["id"])
        if l and l["useful"]:
            later = [x["i"] for x in rowsB if x["i"] > r["i"] and x["topic"] == l["topic"]]
            ev_needed.append({"turn": r["i"], "id": e["id"], "kind": kind(e["id"]), "topic": l["topic"], "sti": e["sti"],
                              "evicted_by": kind(e["by"]) if e["by"] else None, "topic_turns_after": later})
W["B_evicted_kinds"] = dict(evk); W["B_evicted_useful"] = ev_needed
# by turn kind (Q1 two keywords, Q2 one keyword, Q3/R3 keyword-free follow-up, R2 revisit)
byk = {}
for arm in ("A", "B"):
    agg = C.defaultdict(lambda: C.Counter())
    for x in PT[arm]:
        k = "Q3/R3" if x["kind"] in ("Q3", "R3") else x["kind"]
        for c in ("admitted", "admitted_go", "adm_useful", "adm_noise", "shown", "shown_useful", "shown_noise"):
            agg[k][c] += x[c]
        agg[k]["turns"] += 1
    byk[arm] = {k: dict(v) for k, v in agg.items()}
W["by_turn_kind"] = byk
# composition of B's graph-only admissions: on-topic useful / on-topic planted noise / another topic's item
comp = C.Counter(); go_scores = C.Counter()
for r in ARMS["B"]:
    src = {s["id"]: s for s in r["scored"]}
    for x in r["admits"]:
        s = src.get(x["id"])
        if not (x["new"] and s and s["source"] == "graph-only"): continue
        l = lab(x["id"])
        if l["topic"] != r["topic"]: comp["other_topic_%s" % ("useful" if l["useful"] else "noise")] += 1
        else: comp["on_topic_%s" % ("useful" if l["useful"] else "noise")] += 1
        go_scores["%.2f" % s["score"]] += 1
W["B_graph_only_admit_composition"] = dict(comp)
W["B_graph_only_admit_score_hist"] = dict(sorted(go_scores.items(), key=lambda kv: float(kv[0])))
fl = C.Counter()
for r in ARMS["B"]:
    for s in r["scored"]:
        if s.get("cut") == "floor":
            l = lab(s["id"]); fl[kind(s["id"]) + ("" if not l or l["topic"] == r["topic"] else "-offtopic")] += 1
W["B_floor_cut_kinds"] = dict(fl)
os.makedirs(a.out, exist_ok=True)
json.dump({"per_turn": PT, "whole_run": W}, open(os.path.join(a.out, "summary.json"), "w"), indent=1)
cols = ["admitted", "admitted_go", "adm_useful", "adm_noise", "returned", "scored_go", "cut_floor", "cut_topk", "shown", "shown_useful", "shown_noise", "store", "evicted", "evicted_useful_any"]
md = ["| turn | topic/kind | " + " | ".join("A %s / B" % c for c in cols) + " |", "|" + "---|" * (len(cols) + 2)]
for x, y in zip(PT["A"], PT["B"]):
    md.append("| %d | %d %s | " % (x["i"], x["topic"], x["kind"]) + " | ".join("%s / %s" % (x[c], y[c]) for c in cols) + " |")
open(os.path.join(a.out, "turn_table.md"), "w").write("\n".join(md) + "\n")
print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk not in ("revisit_turns", "coverage_by_topic_first_visit")} for k, v in W.items() if k in ("A", "B")} if False else
                 {arm: {kk: vv for kk, vv in W[arm].items() if kk not in ("revisit_turns",)} for arm in ("A", "B")}, indent=0))
print(json.dumps({k: W[k] for k in ("B_evicted_kinds", "by_turn_kind", "B_graph_only_admit_composition", "B_graph_only_admit_score_hist", "B_floor_cut_kinds")}))
print(json.dumps({"disp": {k: v for k, v in W["context_displacement_B_vs_A"].items() if k != "by_turn"}}))
