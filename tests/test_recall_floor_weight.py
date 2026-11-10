"""t-2026-11-10-wmtm-graph-recall-floor-replay: design s8.2 recall_relevance_floor, and a direct PromotesFrom link
weighted 0.5 like a direct EvidenceFor link.  Each test has a negative control.  Synthetic clusters only."""
import pytest

from wmtm import api, runtime_config as rc
from wmtm.recall_bridge import RecallBridge, parse_journal
from test_graph_recall import _journal, _store, _disjoint


def _chain():
    #   c-a <-EF- c-b <-EF- c-c  (c-c is a depth-2 EvidenceFor neighbour of the active c-a)
    #   c-p1 -PF-> c-a (reverse), c-a -PF-> c-q (forward), c-p2 -PF-> c-p1 (depth 2, not followed)
    return RecallBridge(parse_journal(_journal([
        ("c-a", "zebra", "zebra herd seen at the river", ["(PromotesFrom c-a c-q)"]),
        ("c-b", "quantum", "photon counts doubled overnight", ["(EvidenceFor c-b c-a)"]),
        ("c-c", "lattice", "lattice spacing measured", ["(EvidenceFor c-c c-b)"]),
        ("c-p1", "summary", "weekly digest one", ["(PromotesFrom c-p1 c-a)"]),
        ("c-p2", "digest", "monthly digest two", ["(PromotesFrom c-p2 c-p1)"]),
        ("c-q", "source", "original raw entry", []),
    ])))


def _scores(rb, floor):
    return {c.cluster_id: c.score for c in rb.recall("zebra herd", _store("c-a"), top_k=50, floor=floor)}


# ------------------------------------------------------------------------------------------------ floor

def test_spec_default_floor_is_0_1():
    assert rc.SPEC["recall_relevance_floor"][2] == 0.1
    assert api._recall_floor({}) == pytest.approx(0.1)


def test_floor_drops_depth_2_neighbour():
    rb = _chain()
    assert _disjoint(rb, "zebra herd", "c-c")
    s = _scores(rb, 0.1)
    assert "c-c" not in s                      # 0.2 * 0.09 = 0.018 <= 0.1
    assert "c-b" in s                          # direct EvidenceFor neighbour survives


def test_floor_negative_control_zero_keeps_depth_2_neighbour():
    s = _scores(_chain(), 0.0)
    assert s["c-c"] == pytest.approx(0.2 * 0.09)


def test_floor_is_strict_at_the_boundary():
    rb = _chain()
    b = _scores(rb, 0.0)["c-b"]
    assert "c-b" not in _scores(rb, b)         # not above the floor -> dropped
    assert "c-b" in _scores(rb, b - 1e-9)      # control: just below keeps it


def test_floor_does_not_drop_keyword_match():
    rb = _chain()
    ids = [c.cluster_id for c in rb.recall("lattice spacing", _store("c-a"), top_k=50, floor=0.1)]
    assert "c-c" in ids                        # control: the same cluster with a keyword hit stays


def test_api_reads_floor_flag_and_falls_back():
    assert api._recall_floor({"recall_relevance_floor": 0.3}) == pytest.approx(0.3)
    assert api._recall_floor({"recall_relevance_floor": "not-a-number"}) == pytest.approx(0.1)


# ------------------------------------------------------------------------------------ PromotesFrom 0.5

@pytest.mark.parametrize("cid", ["c-p1", "c-q"])          # reverse and forward direction
def test_direct_promotes_from_gets_direct_weight(cid):
    rb = _chain()
    assert _disjoint(rb, "zebra herd", cid)
    s = _scores(rb, 0.1)
    assert s[cid] == pytest.approx(0.5 + 0.2 * 0.3)       # same as a direct EvidenceFor neighbour
    assert s[cid] == pytest.approx(s["c-b"])


def test_promotes_from_weight_negative_control_depth_2_not_boosted():
    s = _scores(_chain(), 0.0)
    assert "c-p2" not in s                     # a second PromotesFrom hop gets neither spread nor the 0.5


def test_promotes_from_weight_negative_control_unlinked():
    rb = RecallBridge(parse_journal(_journal([
        ("c-a", "zebra", "zebra herd seen at the river", []),
        ("c-p1", "summary", "weekly digest one", ["(PromotesFrom c-p1 c-z)"]),
        ("c-z", "other", "unrelated item", []),
    ])))
    s = {c.cluster_id: c.score for c in rb.recall("zebra herd", _store("c-a"), top_k=50, floor=0.0)}
    assert "c-p1" not in s and "c-z" not in s  # PromotesFrom to a non-active item: no boost
