"""t-2026-11-10-wmtm-graph-recall: recall-step time and recall-budget check, before/after.

Run with the code under test on PYTHONPATH (the base tree or the task branch):

    PYTHONPATH=<tree> python bench_recall_step.py <label> <out.json>

Part A (s12.3 simulation): the same setup as tests/test_design_s12_gapcheck._simulate (100 cycles, capacity 20,
seed 123, 8 useful + 52 background notes, each task names 3 useful + 4 background), but the recall step is the real
RecallBridge.recall over a synthetic 60-cluster journal (EvidenceFor and PromotesFrom links among the notes) instead
of a fixed recall list.  Each recall() call is timed (perf_counter); its candidates go into orch.cycle the way
api.py admits them (STI = max(score*10, 1)).
Part B (scale): 7,900 synthetic clusters (the size of the live journal named in recall_bridge's Track P comment),
1-2 EvidenceFor links and on average 0.2 PromotesFrom links per cluster, 40 active items, 30 queries, top_k 15.

Synthetic data only: no journal, no note text, no parse calls.
"""
import json
import random
import statistics
import sys
import time

from wmtm.orchestrator import WMTMOrchestrator
from wmtm.recall_bridge import RecallBridge, parse_journal
from wmtm.store import WMTMStore


def _journal(clusters):
    out = []
    for cid, about, note, extra in clusters:
        out += [f";;; BEGIN MemoryCluster {cid}", f"(MemoryCluster {cid})", f"(About {cid} {about})",
                f'(EventNote ev-{cid} "{note}")', *extra, f";;; END MemoryCluster {cid}"]
    return out


def _graph_only(rb, query, cid):
    return not (rb._tokenize(query) & rb._tokenize(rb._by_id[cid].text))


def part_a(top_k=15):
    rnd = random.Random(123)
    useful = [f"u{i}" for i in range(8)]
    background = [f"b{i}" for i in range(52)]
    keys = useful + background
    lr = random.Random(7)
    clusters = []
    for i, k in enumerate(keys):
        extra = [f"(EvidenceFor {k} {lr.choice([x for x in keys if x != k])})"]
        if i % 5 == 0:
            extra.append(f"(PromotesFrom {k} {lr.choice([x for x in keys if x != k])})")
        clusters.append((k, k, f"note {k}", extra))
    rb = RecallBridge(parse_journal(_journal(clusters)))
    orch = WMTMOrchestrator(WMTMStore(capacity=20))
    times, ncand, ngraph, occ = [], [], [], []
    for _c in range(100):
        task = rnd.sample(useful, 3) + rnd.sample(background, 4)
        query = " ".join(task)
        t0 = time.perf_counter()
        cands = rb.recall(query, orch.store, top_k=top_k)
        times.append(time.perf_counter() - t0)
        ncand.append(len(cands))
        ngraph.append(sum(1 for c in cands if _graph_only(rb, query, c.cluster_id)))
        got = [(c.cluster_id, c.content, max(c.score * 10, 1.0)) for c in cands]
        for i in orch.store.get_active_set():
            if i.id in useful:
                orch.utility.record_use(i.id, orch._cycle)
        orch.cycle(recall_fn=lambda g=got: g)
        occ.append(len(orch.store))
    return {"cycles": 100, "top_k": top_k, "clusters": len(rb._clusters),
            "recall_s_mean": statistics.mean(times), "recall_s_median": statistics.median(times),
            "recall_s_max": max(times), "recall_s_total": sum(times),
            "candidates_max": max(ncand), "candidates_mean": statistics.mean(ncand),
            "graph_only_candidates_mean": statistics.mean(ngraph), "graph_only_candidates_max": max(ngraph),
            "occupancy_max": max(occ), "useful_resident_end": sum(1 for u in useful if u in orch.store)}


def part_b(n=7900, active=40, queries=30, top_k=15):
    r = random.Random(11)
    vocab = [f"w{i}" for i in range(3000)]
    ids = [f"c{i}" for i in range(n)]
    cl = []
    for cid in ids:
        extra = [f"(EvidenceFor {cid} {r.choice(ids)})" for _ in range(r.choice((1, 1, 2, 2)))]
        if r.random() < 0.2:
            extra.append(f"(PromotesFrom {cid} {r.choice(ids)})")
        cl.append((cid, r.choice(vocab), " ".join(r.sample(vocab, 6)), extra))
    rb = RecallBridge(parse_journal(_journal(cl)))
    st = WMTMStore(capacity=200)
    for cid in r.sample(ids, active):
        st.admit(cid, "x", initial_sti=2.0)
    qs = [" ".join(r.sample(vocab, 4)) for _ in range(queries)]
    rb.recall(qs[0], st, top_k=top_k)                   # warm the IDF cache (built once per bridge)
    times, ncand, ngraph = [], [], []
    for q in qs:
        t0 = time.perf_counter()
        cands = rb.recall(q, st, top_k=top_k)
        times.append(time.perf_counter() - t0)
        ncand.append(len(cands))
        ngraph.append(sum(1 for c in cands if _graph_only(rb, q, c.cluster_id)))
    return {"clusters": len(rb._clusters), "active": active, "queries": queries, "top_k": top_k,
            "recall_s_mean": statistics.mean(times), "recall_s_median": statistics.median(times),
            "recall_s_max": max(times), "candidates_max": max(ncand), "candidates_mean": statistics.mean(ncand),
            "graph_only_candidates_mean": statistics.mean(ngraph)}


if __name__ == "__main__":
    label, out = sys.argv[1], sys.argv[2]
    res = {"label": label, "part_a_s12_3": part_a(), "part_b_scale": part_b()}
    with open(out, "w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps(res, indent=1))
