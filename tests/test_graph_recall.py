"""t-2026-11-10-wmtm-graph-recall: recall follows the memory graph (design s3.3 'key insight', s8.1b, s13.5).

GAP-1: a cluster linked to an active item is recalled even when it shares no keyword with the query; an unlinked
one is not.  GAP-2: spreading activation follows PromotesFrom (both directions) at depth 1 only.  Kept: superseded
clusters are never recalled, the recall budget (top_k), the existing weights.  Synthetic clusters only.
"""
import random

import pytest

from wmtm.recall_bridge import RecallBridge, parse_journal
from wmtm.store import WMTMStore


def _journal(clusters, tail=()):
    """clusters: [(id, about, note, extra_lines)] -> journal lines in the petta-memory format."""
    out = []
    for cid, about, note, extra in clusters:
        out.append(f";;; BEGIN MemoryCluster {cid}")
        out.append(f"(MemoryCluster {cid})")
        out.append(f"(About {cid} {about})")
        out.append(f'(EventNote ev-{cid} "{note}")')
        out.extend(extra)
        out.append(f";;; END MemoryCluster {cid}")
    out.extend(tail)
    return out


def _store(*active):
    st = WMTMStore(capacity=200)
    for cid in active:
        st.admit(cid, f"resident {cid}", initial_sti=5.0)
    return st


def _ids(rb, query, st, top_k=10):
    return [c.cluster_id for c in rb.recall(query, st, top_k=top_k)]


def _disjoint(rb, query, cid):
    """No keyword path at all: no shared token and no substring hit (layers 1-2 of _score_cluster)."""
    q = rb._tokenize(query)
    raw = rb._by_id[cid].text.lower()
    return not (q & rb._tokenize(rb._by_id[cid].text)) and not any(len(t) >= 4 and t in raw for t in q)


# ----------------------------------------------------------------------------------------------- GAP-1

@pytest.mark.parametrize("edge", ["(EvidenceFor c-b c-a)", "(EvidenceFor c-a c-b)"])
def test_linked_cluster_without_keyword_overlap_is_recalled(edge):
    """An EvidenceFor link to an active item, in either direction, is enough: no keyword is shared."""
    extra_a, extra_b = ([], [edge]) if edge.startswith("(EvidenceFor c-b") else ([edge], [])
    rb = RecallBridge(parse_journal(_journal([
        ("c-a", "zebra", "zebra herd seen at the river", extra_a),
        ("c-b", "quantum", "photon counts doubled overnight", extra_b),
    ])))
    st = _store("c-a")
    assert _disjoint(rb, "zebra herd", "c-b")
    assert "c-b" in _ids(rb, "zebra herd", st)


def test_unlinked_cluster_without_keyword_overlap_is_not_recalled():
    """Negative control: same clusters, no link -> not recalled.  Recall did not widen keyword matching."""
    rb = RecallBridge(parse_journal(_journal([
        ("c-a", "zebra", "zebra herd seen at the river", []),
        ("c-b", "quantum", "photon counts doubled overnight", []),
        ("c-c", "lattice", "lattice spacing measured", ["(EvidenceFor c-c c-a)"]),
    ])))
    st = _store("c-a")
    ids = _ids(rb, "zebra herd", st)
    assert "c-b" not in ids
    assert "c-c" in ids                      # the linked control in the same journal is recalled


def test_graph_only_recall_needs_an_active_item():
    """With nothing active the linked cluster has no keyword and no spread: not recalled."""
    rb = RecallBridge(parse_journal(_journal([
        ("c-a", "zebra", "zebra herd seen at the river", []),
        ("c-b", "quantum", "photon counts doubled overnight", ["(EvidenceFor c-b c-a)"]),
    ])))
    assert _ids(rb, "zebra herd", _store()) == ["c-a"]


def test_keyword_match_outranks_graph_only_neighbour():
    """Graph-only candidates come after keyword matches (they fill the budget, they don't displace)."""
    rb = RecallBridge(parse_journal(_journal([
        ("c-a", "zebra", "zebra herd seen at the river", []),
        ("c-b", "quantum", "photon counts doubled overnight", ["(EvidenceFor c-b c-a)"]),
        ("c-k", "zebra", "zebra crossing repainted", []),
    ])))
    st = _store("c-a")
    assert _ids(rb, "zebra herd", st, top_k=1) == ["c-k"]
    assert _ids(rb, "zebra herd", st, top_k=2) == ["c-k", "c-b"]


def test_resident_relevance_stimulus_keeps_keyword_gate():
    """_score_cluster's default (used by context.relevance_stimulus for residents) is unchanged: 0 without a
    keyword; only recall() asks for graph scoring."""
    rb = RecallBridge(parse_journal(_journal([
        ("c-a", "zebra", "zebra herd seen at the river", []),
        ("c-b", "quantum", "photon counts doubled overnight", ["(EvidenceFor c-b c-a)"]),
    ])))
    st = _store("c-a")
    q, active = rb._tokenize("zebra herd"), {"c-a"}
    assert rb._score_cluster(rb._by_id["c-b"], q, active, st) == 0.0
    assert rb._score_cluster(rb._by_id["c-b"], q, active, st, graph=True) > 0.0


def test_graph_only_score_uses_existing_spread_weights():
    """No new weights: a direct EvidenceFor neighbour scores 0.5 (direct link) + 0.2 * 0.3 (spread at depth 1,
    decay 0.3); ids carry no timestamp, so no recency factor."""
    rb = RecallBridge(parse_journal(_journal([
        ("c-a", "zebra", "zebra herd seen at the river", []),
        ("c-b", "quantum", "photon counts doubled overnight", ["(EvidenceFor c-b c-a)"]),
    ])))
    (c,) = [c for c in rb.recall("zebra herd", _store("c-a"), top_k=10) if c.cluster_id == "c-b"]
    assert c.score == pytest.approx(0.5 + 0.2 * 0.3)


# ----------------------------------------------------------------------------------------------- GAP-2

def _pf_chain():
    #   c-a <-PromotesFrom- c-p1 <-PromotesFrom- c-p2 ;  c-p1 -EvidenceFor-> c-e ;  c-x -EvidenceFor-> c-a, c-y PF c-x
    return RecallBridge(parse_journal(_journal([
        ("c-a", "zebra", "zebra herd seen at the river", []),
        ("c-p1", "summary", "weekly digest one", ["(PromotesFrom c-p1 c-a)", "(EvidenceFor c-p1 c-e)"]),
        ("c-p2", "digest", "monthly digest two", ["(PromotesFrom c-p2 c-p1)"]),
        ("c-e", "lattice", "lattice spacing measured", []),
        ("c-x", "quantum", "photon counts doubled", ["(EvidenceFor c-x c-a)"]),
        ("c-y", "rollup", "quarterly rollup", ["(PromotesFrom c-y c-x)"]),
    ])))


def test_promotes_from_neighbour_reached_at_depth_1_not_depth_2():
    rb = _pf_chain()
    s = rb.spreading_activation(["c-a"], depth=2, decay=0.3)
    assert s["c-p1"] == pytest.approx(0.3)   # depth 1 through PromotesFrom (reverse direction)
    assert "c-p2" not in s                    # a second PromotesFrom hop is not followed
    assert "c-y" not in s                     # nor a PromotesFrom edge at depth 2 after an EvidenceFor hop
    assert s["c-e"] == pytest.approx(0.09)   # EvidenceFor keeps its depth 2, also after a PromotesFrom hop


def test_promotes_from_followed_forward_from_the_promoted_item():
    rb = _pf_chain()
    s = rb.spreading_activation(["c-p2"], depth=2, decay=0.3)
    assert s["c-p1"] == pytest.approx(0.3)
    assert "c-a" not in s


def test_promotes_from_depth_0_reaches_nothing():
    assert set(_pf_chain().spreading_activation(["c-a"], depth=0)) == {"c-a"}


def test_promotes_from_neighbour_recalled_without_keywords_but_not_at_depth_2():
    rb = _pf_chain()
    st = _store("c-a")
    ids = _ids(rb, "zebra herd", st)
    assert _disjoint(rb, "zebra herd", "c-p1")
    assert "c-p1" in ids
    assert "c-p2" not in ids and "c-y" not in ids


# ------------------------------------------------------------------------------------------ superseded

def test_superseded_never_recalled_even_when_linked():
    """s8.2: a superseded cluster stays out of recall, whatever links it has to the active set (both edge kinds,
    both directions) and even when it is also the best keyword match."""
    rb = RecallBridge(parse_journal(_journal([
        ("c-a", "zebra", "zebra herd seen at the river", ["(EvidenceFor c-a c-old2)"]),
        ("c-old", "quantum", "photon counts doubled", ["(EvidenceFor c-old c-a)", "(PromotesFrom c-old c-a)"]),
        ("c-old2", "zebra", "zebra herd at the river again", []),
        ("c-new", "quantum", "photon counts tripled", ["(Supersedes c-new c-old)", "(Supersedes c-new c-old2)"]),
    ])))
    st = _store("c-a")
    ids = _ids(rb, "zebra herd river", st, top_k=50)
    assert "c-old" not in ids and "c-old2" not in ids
    s = rb.spreading_activation(["c-a"], depth=2)
    assert all(k not in rb._by_id for k in ("c-old", "c-old2"))
    assert not ({"c-old", "c-old2"} & {c.id for c in rb._clusters})
    assert "c-new" not in s                   # its old version is not a bridge to it


# ------------------------------------------------------------------------------------- budget property

def _reachable(rb, active):
    """Independent restatement of s8.1b: EvidenceFor both ways up to 2 hops, PromotesFrom both ways at hop 1."""
    ef, pf = {}, {}
    for c in rb._clusters:
        for t in c.evidence_for:
            ef.setdefault(c.id, set()).add(t)
            ef.setdefault(t, set()).add(c.id)
        for t in c.promotes_from:
            pf.setdefault(c.id, set()).add(t)
            pf.setdefault(t, set()).add(c.id)
    seeds = {a for a in active if a in rb._by_id}
    one = set()
    for a in seeds:
        one |= ef.get(a, set()) | pf.get(a, set())
    two = set()
    for n in one:
        if n in rb._by_id:
            two |= ef.get(n, set())
    return (one | two) - seeds


@pytest.mark.parametrize("seed", range(300))
def test_recall_budget_and_filters_property(seed):
    """Random graphs, active sets, queries and budgets: recall returns at most top_k distinct candidates, never an
    active or superseded cluster, every candidate has a keyword path or a graph path to the active set, and the
    result is the top_k prefix of the unbounded ranking."""
    r = random.Random(seed)
    n = r.randint(1, 60)
    vocab = [f"v{i}" for i in range(r.randint(3, 30))]
    ids = [f"k{i}" for i in range(n)]
    clusters = []
    for cid in ids:
        extra = [f"(EvidenceFor {cid} {r.choice(ids)})" for _ in range(r.randint(0, 3))]
        extra += [f"(PromotesFrom {cid} {r.choice(ids)})" for _ in range(r.randint(0, 2))]
        clusters.append((cid, r.choice(vocab), " ".join(r.sample(vocab, min(3, len(vocab)))), extra))
    sup = set(r.sample(ids, r.randint(0, n // 3)))
    rb = RecallBridge(parse_journal(_journal(clusters, [f"(Supersedes k-new {o})" for o in sorted(sup)])))
    live = [c.id for c in rb._clusters]
    active = set(r.sample(live, r.randint(0, len(live)))) if live else set()
    st = _store(*sorted(active))
    query = " ".join(r.sample(vocab, r.randint(0, min(4, len(vocab)))))
    top_k = r.randint(0, 25)
    res = rb.recall(query, st, top_k=top_k)
    got = [c.cluster_id for c in res]
    assert len(got) <= top_k
    assert len(set(got)) == len(got)
    assert not (set(got) & sup) and not (set(got) & active)
    assert all(c.score > 0 for c in res)
    assert [c.score for c in res] == sorted((c.score for c in res), reverse=True)
    reach = _reachable(rb, active)
    for cid in got:
        assert not _disjoint(rb, query, cid) or cid in reach
    full = [c.cluster_id for c in rb.recall(query, st, top_k=10 ** 6)]
    assert got == full[:top_k]
    assert len(full) <= len(live) - len(active)
