#!/usr/bin/env python3
"""t-2026-11-11-wmtm-recall-budget-10: the graph-only probe's analysis (graph-only-probe/tools/analyse.py), generalised
from two arms (A, B) to any number of arms, with the same metrics and label rules.
Usage: analyse3.py --data data --arm A=results/A/turns.jsonl --arm B=... --arm C=... --out results
Labels: an item is USEFUL at turn t when it is planted useful AND its topic is the turn's topic; everything else counts
as NOISE at that turn.  Changes from analyse.py (and only these):
  * "turns with the recall cut full" counts turns where recall() returned as many candidates as its top_k (15 for A
    and B, as before; 10 for C, where the cut is the recall budget);
  * the B-only blocks (displacement vs A, evicted kinds, graph-only admit composition, floor-cut kinds) are computed
    for every arm other than A;
  * new: per-turn new recalled admissions max, and planted-useful items reached (admitted or shown) per arm."""
import argparse, json, os, collections as C
ap = argparse.ArgumentParser()
ap.add_argument("--data", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--arm", action="append", required=True)
a = ap.parse_args()
LAB = json.load(open(os.path.join(a.data, "labels.json")))["labels"]
def load(p): return [json.loads(l) for l in open(p)]
ARMS = {}
for spec in a.arm:
    k, p = spec.split("=", 1); ARMS[k] = load(p)
names = list(ARMS)
for k in names[1:]:
    assert [r["q"] for r in ARMS[names[0]]] == [r["q"] for r in ARMS[k]], "turn scripts differ"
    assert ARMS[names[0]][0]["meta"]["journal_sha256"] == ARMS[k][0]["meta"]["journal_sha256"], "journals differ"
    assert ARMS[names[0]][0]["meta"]["turns_sha256"] == ARMS[k][0]["meta"]["turns_sha256"], "turns differ"
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
        top_k = r["recall_calls"][0]["top_k"] if r["recall_calls"] else None
        evs = r["evicts"]
        ev_by_go = [e for e in evs if src.get(e["by"], {}).get("source") == "graph-only"]
        out.append({
            "i": r["i"], "topic": t, "kind": r["kind"], "top_k": top_k,
            "scored_pos": len(pos), "scored_kw": sum(s["source"] == "keyword" for s in pos),
            "scored_go": sum(s["source"] == "graph-only" for s in pos),
            "cut_floor": sum(s.get("cut") == "floor" for s in r["scored"]),
            "cut_topk": sum(s.get("cut") == "top_k" for s in r["scored"]),
            "cut_topk_useful": sum(s.get("cut") == "top_k" and useful_at(s["id"], t) for s in r["scored"]),
            "cut_topk_kw": sum(s.get("cut") == "top_k" and s["source"] == "keyword" for s in r["scored"]),
            "cut_topk_kw_useful": sum(s.get("cut") == "top_k" and s["source"] == "keyword" and useful_at(s["id"], t) for s in r["scored"]),
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
    planted = C.defaultdict(set)
    for cid, l in LAB.items():
        if l["useful"] and l["topic"] is not None: planted[l["topic"]].add(cid)
    seen = C.defaultdict(set); seen_rev = C.defaultdict(set); adm_on = C.defaultdict(set)
    for r in rows:
        for c in r["shown"]:
            if useful_at(c, r["topic"]):
                (seen_rev if r["kind"].startswith("R") else seen)[r["topic"]].add(c)
        for x in r["admits"]:
            if x["source_type"] == "recalled" and useful_at(x["id"], r["topic"]):
                adm_on[r["topic"]].add(x["id"])
    rev_topics = sorted({r["topic"] for r in rows if r["kind"].startswith("R")})
    rev = []
    for r in rows:
        if r["kind"].startswith("R"):
            t = r["topic"]
            rev.append({"i": r["i"], "topic": t, "kind": r["kind"],
                        "resident_useful": sum(useful_at(c, t) for c in r["store_after"]),
                        "shown_useful": sum(useful_at(c, t) for c in r["shown"]), "shown": len(r["shown"])})
    sti_go = [v for x in pt for v in x["sti_go"]]; sti_kw = [v for x in pt for v in x["sti_kw"]]
    hubs = {cid for cid, l in LAB.items() if l["useful"] and l["role"] == "hub"}
    first = set().union(*seen.values()) if seen else set()
    return {
        "turns": len(pt), "admitted": s("admitted"), "admitted_graph_only": s("admitted_go"), "admitted_keyword": s("admitted_kw"),
        "admitted_useful": s("adm_useful"), "admitted_noise": s("adm_noise"),
        "max_new_recalled_in_one_turn": max(x["admitted"] for x in pt),
        "precision_admitted_on_topic": frac(s("adm_useful"), s("admitted")),
        "precision_admitted_any_useful": frac(s("adm_any_useful"), s("admitted")),
        "precision_graph_only_admitted_on_topic": frac(s("adm_go_useful"), s("admitted_go")),
        "shown_total": s("shown"), "shown_useful": s("shown_useful"), "shown_noise": s("shown_noise"),
        "precision_shown_on_topic": frac(s("shown_useful"), s("shown")),
        "coverage_useful_shown_first_visit": {"shown": sum(len(v) for v in seen.values()), "planted": sum(len(v) for v in planted.values()),
                                              "hubs": len(first & hubs), "linked": len(first - hubs),
                                              "frac": frac(sum(len(v) for v in seen.values()), sum(len(v) for v in planted.values()))},
        "useful_admitted_during_topic_turns": sum(len(v) for v in adm_on.values()),
        "coverage_by_topic_first_visit": {t: [len(seen[t]), len(planted[t])] for t in sorted(planted)},
        "coverage_revisit": {t: [len(seen_rev[t]), len(planted[t])] for t in rev_topics},
        "coverage_revisit_total": [sum(len(seen_rev[t]) for t in rev_topics), sum(len(planted[t]) for t in rev_topics)],
        "revisit_turns": rev,
        "evicted": s("evicted"), "evicted_by_graph_only_admit": s("evicted_by_go"), "evicted_useful_any_topic": s("evicted_useful_any"),
        "evicted_useful_hubs": sum(1 for x in pt for k, v in x["evicted_kinds"].items() if k == "hub-U" for _ in range(v)),
        "max_store": max(x["store"] for x in pt),
        "first_turn_store_full": next((x["i"] for x in pt if x["evicted"] > 0), None),
        "cut_by_floor": s("cut_floor"), "cut_by_top_k": s("cut_topk"), "cut_by_top_k_on_topic_useful": s("cut_topk_useful"),
        "cut_by_top_k_keyword": s("cut_topk_kw"), "cut_by_top_k_keyword_on_topic_useful": s("cut_topk_kw_useful"),
        "top_k_values": sorted({x["top_k"] for x in pt if x["top_k"] is not None}),
        "turns_top_k_full": sum(x["top_k"] is not None and x["returned"] >= x["top_k"] for x in pt),
        "sti_on_admit": {"graph_only": [min(sti_go, default=None), max(sti_go, default=None), round(sum(sti_go) / len(sti_go), 3) if sti_go else None],
                         "keyword": [min(sti_kw, default=None), max(sti_kw, default=None), round(sum(sti_kw) / len(sti_kw), 3) if sti_kw else None]},
        "min_keyword_score_vs_max_graph_only": [min([x["kw_min"] for x in pt if x["kw_min"] is not None], default=None),
                                               max([x["go_max"] for x in pt if x["go_max"] is not None], default=None)],
        "violations": max(x["violations"] for x in pt), "errors": sum(1 for x in pt if x["err"]),
    }
W = {k: whole(k) for k in ARMS}
base = names[0]
for arm in names[1:]:
    disp = []
    for ra, rb in zip(ARMS[base], ARMS[arm]):
        t = ra["topic"]
        ua = {c for c in ra["shown"] if useful_at(c, t)}; ub = {c for c in rb["shown"] if useful_at(c, t)}
        disp.append({"i": ra["i"], "kind": ra["kind"], "topic": t, "A_only_useful": sorted(ua - ub), "X_only_useful": sorted(ub - ua),
                     "A_only_useful_kinds": [kind(c) for c in sorted(ua - ub)]})
    W["context_displacement_%s_vs_%s" % (arm, base)] = {
        "turns_lost_a_useful_A_showed": sum(1 for d in disp if d["A_only_useful"]),
        "turn_kinds_lost": dict(C.Counter(d["kind"] for d in disp if d["A_only_useful"])),
        "useful_lost": sum(len(d["A_only_useful"]) for d in disp),
        "useful_lost_kinds": dict(C.Counter(k for d in disp for k in d["A_only_useful_kinds"])),
        "useful_gained": sum(len(d["X_only_useful"]) for d in disp), "by_turn": [d for d in disp if d["A_only_useful"] or d["X_only_useful"]]}
    evk = C.Counter(); ev_needed = []
    for r in ARMS[arm]:
        for e in r["evicts"]:
            evk[kind(e["id"])] += 1
            l = lab(e["id"])
            if l and l["useful"]:
                later = [x["i"] for x in ARMS[arm] if x["i"] > r["i"] and x["topic"] == l["topic"]]
                ev_needed.append({"turn": r["i"], "id": e["id"], "kind": kind(e["id"]), "topic": l["topic"], "sti": e["sti"],
                                  "evicted_by": kind(e["by"]) if e["by"] else None, "topic_turns_after": later})
    W["%s_evicted_kinds" % arm] = dict(evk); W["%s_evicted_useful" % arm] = ev_needed
    comp = C.Counter(); go_scores = C.Counter()
    for r in ARMS[arm]:
        src = {s["id"]: s for s in r["scored"]}
        for x in r["admits"]:
            s = src.get(x["id"])
            if not (x["new"] and s and s["source"] == "graph-only"): continue
            l = lab(x["id"])
            if l["topic"] != r["topic"]: comp["other_topic_%s" % ("useful" if l["useful"] else "noise")] += 1
            else: comp["on_topic_%s" % ("useful" if l["useful"] else "noise")] += 1
            go_scores["%.2f" % s["score"]] += 1
    W["%s_graph_only_admit_composition" % arm] = dict(comp)
    W["%s_graph_only_admit_score_hist" % arm] = dict(sorted(go_scores.items(), key=lambda kv: float(kv[0])))
    fl = C.Counter()
    for r in ARMS[arm]:
        for s in r["scored"]:
            if s.get("cut") == "floor":
                l = lab(s["id"]); fl[kind(s["id"]) + ("" if not l or l["topic"] == r["topic"] else "-offtopic")] += 1
    W["%s_floor_cut_kinds" % arm] = dict(fl)
byk = {}
for arm in names:
    agg = C.defaultdict(lambda: C.Counter())
    for x in PT[arm]:
        k = "Q3/R3" if x["kind"] in ("Q3", "R3") else x["kind"]
        for c in ("admitted", "admitted_go", "adm_useful", "adm_noise", "shown", "shown_useful", "shown_noise"):
            agg[k][c] += x[c]
        agg[k]["turns"] += 1
    byk[arm] = {k: dict(v) for k, v in agg.items()}
W["by_turn_kind"] = byk
os.makedirs(a.out, exist_ok=True)
json.dump({"arms": names, "per_turn": PT, "whole_run": W}, open(os.path.join(a.out, "summary.json"), "w"), indent=1)
cols = ["admitted", "admitted_go", "adm_useful", "adm_noise", "returned", "scored_go", "cut_floor", "cut_topk", "shown", "shown_useful", "shown_noise", "store", "evicted", "evicted_useful_any"]
lab3 = " / ".join(names)
md = ["| turn | topic/kind | " + " | ".join("%s (%s)" % (c, lab3) for c in cols) + " |", "|" + "---|" * (len(cols) + 2)]
for rows in zip(*(PT[k] for k in names)):
    x = rows[0]
    md.append("| %d | %d %s | " % (x["i"], x["topic"], x["kind"]) + " | ".join(" / ".join(str(y[c]) for y in rows) for c in cols) + " |")
open(os.path.join(a.out, "turn_table.md"), "w").write("\n".join(md) + "\n")
print(json.dumps({arm: {kk: vv for kk, vv in W[arm].items() if kk not in ("revisit_turns",)} for arm in names}, indent=0))
for arm in names[1:]:
    print(json.dumps({k: W[k] for k in ("%s_evicted_kinds" % arm, "%s_graph_only_admit_composition" % arm, "%s_floor_cut_kinds" % arm)}))
    print(json.dumps({"disp_%s" % arm: {k: v for k, v in W["context_displacement_%s_vs_%s" % (arm, base)].items() if k != "by_turn"}}))
print(json.dumps({"by_turn_kind": byk}))
