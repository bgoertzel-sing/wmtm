"""t-2026-11-11-wmtm-spread-seeds-probe: flag recall_spread_seeds, where recall's spreading activation starts.

all   = every resident seeds layer 5 (direct links + spread); the behaviour before the flag (the flag default until
        t-2026-11-13-wmtm-spread-seed-default, which made turn + recall_spread_add_pct 10 the default; all stays
        selectable, see tests/test_recall_spread_default.py).
focus = the attention focus: the top 50% of residents by STI (design s9.2; s3.1 get_active_set "sorted by STI").
turn  = this turn only: the clusters matching this turn's query by keyword, plus the request item.

Every mode test has a negative control: the same store and query under another mode give the opposite outcome, so
the assertion would fail if the flag were ignored.  Synthetic clusters only.
"""
import json
import random
import time

import pytest

from wmtm import context as ctx
from wmtm import runtime_config as rc
from wmtm.api import WMTM, WMTMConfig
from wmtm.recall_bridge import LTMCluster, RecallBridge
from wmtm.store import WMTMStore

WORDS = ["amber", "basalt", "cobalt", "dynamo", "ember", "fjord", "garnet", "harbor"]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("WMTM_RECALL_BUDGET", "WMTM_RECALL_RELEVANCE_FLOOR", "WMTM_REASONER", "WMTM_RECALL_SPREAD_SEEDS"):
        monkeypatch.delenv(k, raising=False)


# ----------------------------------------------------------------------------------------------- hand-built world

def _c(cid, note, ev=(), pf=()):
    return LTMCluster(id=cid, event_note=note, evidence_for=list(ev), promotes_from=list(pf),
                      opened_at=time.time() - 3600)


def _world():
    """Residents H (STI 90), X (80), L (5), L2 (4, but LTI 1000 so its attention.total is the highest), R (3, matches
    the query "zephyr"); non-residents: GH -> H, GL -> L, GL2 -> L2, GR -> R, K (matches "zephyr", no resident link),
    GK -> K (PromotesFrom), and N (no link, no match)."""
    cl = [
        _c("H", "hub alpha"), _c("X", "hub beta"), _c("L", "old gamma"), _c("L2", "old delta"),
        _c("R", "zephyr resident note"),
        _c("GH", "linked one", ev=["H"]), _c("GL", "linked two", ev=["L"]), _c("GL2", "linked three", ev=["L2"]),
        _c("GR", "linked four", ev=["R"]),
        _c("K", "zephyr fresh keyword hit"), _c("GK", "linked five", pf=["K"]), _c("N", "unrelated"),
    ]
    rb = RecallBridge(cl)
    st = WMTMStore(capacity=50)
    for cid, sti in (("H", 90.0), ("X", 80.0), ("L", 5.0), ("L2", 4.0), ("R", 3.0)):
        st.admit(cid, cid, source_type="recalled", initial_sti=sti)
    st.get("L2").attention.lti = 1000.0
    return rb, st


def _ids(rb, st, mode, q="zephyr", **kw):
    if mode is None:
        out = rb.recall(q, st, top_k=50, floor=0.1, **kw)
    else:
        out = rb.recall(q, st, top_k=50, floor=0.1, spread_seeds=mode, **kw)
    return {c.cluster_id: c.score for c in out}


# ------------------------------------------------------------------------------------------------------ config

def test_spec_default_is_turn():
    # t-2026-11-13-wmtm-spread-seed-default: the default moved from all to turn (with recall_spread_add_pct 10)
    assert rc.SPEC["recall_spread_seeds"][:3] == ("WMTM_RECALL_SPREAD_SEEDS", str, "turn")
    assert ctx.recall_spread_seeds({}) == "turn"
    assert ctx.recall_spread_seeds(rc.resolve(None, environ={})) == "turn"


def test_flag_env_and_invalid():
    for v in ("all", "focus", "turn", " Focus ", "TURN"):
        assert ctx.recall_spread_seeds({"recall_spread_seeds": v}) == v.strip().lower()
    assert ctx.recall_spread_seeds({"recall_spread_seeds": "junk"}) == "turn"       # invalid = the default
    assert ctx.recall_spread_seeds({"recall_spread_seeds": None}) == "turn"
    assert ctx.recall_spread_seeds(rc.resolve(None, environ={"WMTM_RECALL_SPREAD_SEEDS": "focus"})) == "focus"
    assert ctx.recall_spread_seeds(rc.resolve(None, environ={"WMTM_RECALL_SPREAD_SEEDS": "all"})) == "all"
    assert ctx.recall_spread_seeds(rc.resolve(None, environ={"WMTM_RECALL_SPREAD_SEEDS": "x"})) == "turn"


# --------------------------------------------------------------------------------------------- mode C: all

def test_all_every_resident_seeds():
    rb, st = _world()
    got = _ids(rb, st, "all")
    assert {"GH", "GL", "GL2", "GR", "K"} <= set(got)
    assert "GK" not in got and "N" not in got           # K is not resident, so it seeds nothing under all
    assert rb.spread_seed_ids("all", {"zephyr"}, st) == {"H", "X", "L", "L2", "R"}


def test_unset_equals_all_hand_built():
    rb, st = _world()
    assert _ids(rb, st, None) == _ids(rb, st, "all")


def test_all_negative_control_focus_drops_low_sti_links():
    rb, st = _world()
    assert "GL2" in _ids(rb, st, "all") and "GL2" not in _ids(rb, st, "focus")


# ------------------------------------------------------------------------------------------- mode D: focus

def test_focus_is_top_half_by_sti_not_total():
    rb, st = _world()
    # 5 residents -> ceil(5/2) = 3 by STI: H 90, X 80, L 5.  L2 has the highest attention.total (LTI 1000) but STI 4.
    assert rb.spread_seed_ids("focus", set(), st) == {"H", "X", "L"}
    assert st.get_active_set()[0].id == "L2"            # get_active_set order is by total, so it is not used here
    got = _ids(rb, st, "focus")
    assert "GH" in got and "GL" in got
    assert "GL2" not in got and "GR" not in got
    assert "K" in got                                     # keyword hits are never affected
    assert "GK" not in got


def test_focus_negative_control_all_keeps_them():
    rb, st = _world()
    got = _ids(rb, st, "all")
    assert "GL2" in got and "GR" in got


def test_focus_rounds_up_and_single_resident():
    rb = RecallBridge([_c("A", "a"), _c("GA", "ga", ev=["A"])])
    st = WMTMStore(capacity=10)
    st.admit("A", "A", initial_sti=1.0)
    assert rb.spread_seed_ids("focus", set(), st) == {"A"}       # ceil(1/2) = 1: one resident still seeds
    assert "GA" in _ids(rb, st, "focus", q="nothing")
    st2 = WMTMStore(capacity=10)
    for i, s in enumerate((5.0, 4.0, 3.0, 2.0)):
        st2.admit("r%d" % i, "r", initial_sti=s)
    assert rb.spread_seed_ids("focus", set(), st2) == {"r0", "r1"}   # 4 residents -> 2


# --------------------------------------------------------------------------------------------- mode E: turn

def test_turn_seeds_keyword_hits_and_request():
    rb, st = _world()
    seeds = rb.spread_seed_ids("turn", rb._tokenize("zephyr"), st, request_id="user-abc")
    assert seeds == {"K", "R", "user-abc"}                # K (fresh) and R (resident) match; + the request item
    got = _ids(rb, st, "turn", request_id="user-abc")
    assert "GK" in got                                     # linked to this turn's keyword hit K
    assert "GR" in got                                     # linked to resident R, which matches this turn
    assert not ({"GH", "GL", "GL2"} & set(got))           # linked only to residents not matching this turn
    assert "K" in got


def test_turn_negative_control_all():
    rb, st = _world()
    got = _ids(rb, st, "all")
    assert "GK" not in got and {"GH", "GL", "GL2"} <= set(got)


def test_turn_no_self_boost_for_seed_keyword_hit():
    """K seeds the spread under turn; its own hop-0 activation must not count as a link.  K has no link to a
    resident, so its score is the same as under all (where it gets no spread either)."""
    rb, st = _world()
    assert _ids(rb, st, "turn")["K"] == pytest.approx(_ids(rb, st, "all")["K"])
    # negative control: without the exclusion the seed would score 0.2 * 1.0 more (times recency 1.3)
    q = rb._tokenize("zephyr")
    seeds = rb.spread_seed_ids("turn", q, st)
    k = rb._by_id["K"]
    with_self = rb._score_cluster(k, q, seeds, st, graph=True)
    without = rb._score_cluster(k, q, seeds, st, graph=True, exclude_seed_self=True)
    assert with_self - without == pytest.approx(0.2 * 1.3)


def test_turn_request_item_has_no_edges():
    rb, st = _world()
    assert _ids(rb, st, "turn", request_id="user-abc") == _ids(rb, st, "turn")


def test_keyword_matches_agrees_with_layers_1_2():
    rng = random.Random(7)
    rb = RecallBridge(_random_clusters(rng))
    st = WMTMStore(capacity=60)
    for _ in range(30):
        q = rb._tokenize(" ".join(rng.sample(WORDS, rng.choice([1, 2, 3])) + ["record"][:rng.randrange(2)]))
        for c in rb._clusters:
            assert rb._keyword_matches(c, q) == (rb._score_cluster(c, q, set(), st) > 0)


# ------------------------------------------------------------------------------------- seeded property tests

def _random_clusters(rng, n=70, links=60):
    t0 = time.time() - 2 * 3600
    ids = ["c%02d" % i for i in range(n)]
    ev, pf = {}, {}
    for _ in range(links):
        a, b = rng.sample(range(n), 2)
        (ev if rng.random() < 0.5 else pf).setdefault(a, []).append(ids[b])
    return [LTMCluster(id=ids[i], event_note="%s record u%d" % (" ".join(rng.sample(WORDS, 2)), i),
                       evidence_for=ev.get(i, []), promotes_from=pf.get(i, []), opened_at=t0 + 60 * i)
            for i in range(n)]


def _random_store(rng, rb, k=16):
    st = WMTMStore(capacity=60)
    for c in rng.sample(rb._clusters, k):
        st.admit(c.id, c.id, initial_sti=rng.uniform(1, 100))
    return st


def _reach(rb, seeds):
    """Every cluster layer 5 can score from seeds: direct link either way (EvidenceFor, PromotesFrom) or in the
    depth-2 spread."""
    out = set(rb.spreading_activation(list(seeds), depth=2, decay=0.3))
    for c in rb._clusters:
        nb = set(c.evidence_for) | set(c.promotes_from)
        nb |= set(rb._evidence_for_targets.get(c.id, [])) | set(rb._promotes_from_targets.get(c.id, []))
        if nb & set(seeds):
            out.add(c.id)
    return out


@pytest.mark.parametrize("seed", range(10))
@pytest.mark.parametrize("mode", ["focus", "turn"])
def test_property_graph_only_candidates_come_from_the_seeds(seed, mode):
    rng = random.Random(seed)
    rb = RecallBridge(_random_clusters(rng))
    st = _random_store(rng, rb)
    q = " ".join(rng.sample(WORDS, 1))
    qt = rb._tokenize(q)
    seeds = rb.spread_seed_ids(mode, qt, st)
    if mode == "focus":
        stis = sorted((it.attention.sti for it in st.get_active_set()), reverse=True)
        assert len(seeds) == (len(stis) + 1) // 2
        assert min(st.get(s).attention.sti for s in seeds) >= stis[len(seeds) - 1]
    reach = _reach(rb, seeds)
    out = rb.recall(q, st, top_k=200, floor=0.1, spread_seeds=mode)
    graph_only = [c.cluster_id for c in out if not rb._keyword_matches(rb._by_id[c.cluster_id], qt)]
    assert all(cid in reach for cid in graph_only)
    assert not any(cid in st for cid in (c.cluster_id for c in out))           # residents never candidates


@pytest.mark.parametrize("seed", range(10))
@pytest.mark.parametrize("mode", ["focus", "turn"])
def test_property_negative_control_all_reaches_outside_the_seeds(seed, mode):
    """Under all, graph-only candidates outside the focus/turn seeds' reach exist on the same kind of worlds (in
    aggregate over three seeds), so the property above is not vacuous."""
    outside = 0
    for s in range(seed * 3, seed * 3 + 3):
        rng = random.Random(s)
        rb = RecallBridge(_random_clusters(rng))
        st = _random_store(rng, rb)
        q = " ".join(rng.sample(WORDS, 1))
        qt = rb._tokenize(q)
        reach = _reach(rb, rb.spread_seed_ids(mode, qt, st))
        out = rb.recall(q, st, top_k=200, floor=0.1, spread_seeds="all")
        outside += sum(1 for c in out if not rb._keyword_matches(rb._by_id[c.cluster_id], qt)
                       and c.cluster_id not in reach)
    assert outside > 0


# ------------------------------------------------------------------------------------------- API (live turn)

class ListJournal:
    def __init__(self, text=""):
        self.lines = text.splitlines()

    def read_lines(self):
        return list(self.lines)

    def append(self, note, supersedes=None, about=None):
        return {"ok": True}


FIXED_NOW = 1794350000.0     # the probe's fixed clock: both runs of a comparison see the same time and cluster ids


def _journal(rng, n=70, links=60):
    t0 = FIXED_NOW - 2 * 3600
    ids, out = [], []
    for i in range(n):
        t = time.gmtime(t0 + 60 * i)
        cid = "ep-note-" + time.strftime("%Y%m%dT%H%M%SZ", t)
        ids.append(cid)
        w = rng.sample(WORDS, 2)
        out.append((cid, time.strftime("%Y-%m-%dT%H:%M:%SZ", t), f"{w[0]} {w[1]} record u{i}x{rng.randrange(10**6)}"))
    edges = {}
    for _ in range(links):
        a, b = rng.sample(range(n), 2)
        edges.setdefault(a, []).append("(%s %s %s)" % (rng.choice(["EvidenceFor", "PromotesFrom"]), ids[a], ids[b]))
    text = ""
    for i, (cid, iso, note) in enumerate(out):
        text += (f";;; BEGIN MemoryCluster {cid}\n(MemoryCluster {cid})\n(SchemaVersion {cid} medium-memory-v1)\n"
                 f"(ClusterType {cid} Episode)\n(ClusterSource {cid} iter-experience)\n(ClusterOpenedAt {cid} {iso})\n"
                 f"(Contains {cid} ev-{cid})\n(ObservedEvent ev-{cid})\n(About {cid} journal)\n"
                 f"(EventNote ev-{cid} \"{note}\")\n" + "".join(e + "\n" for e in edges.get(i, [])) +
                 f";;; END MemoryCluster {cid}\n")
    return text


def _run_api(tmp_path, seed, flags, turns=10):
    """A seeded 10-turn script through WMTM.observe + context_for -> (new recalled ids in order, context blocks)."""
    rng = random.Random(seed)
    jt = _journal(rng)
    qs = [" ".join(rng.sample(WORDS, rng.choice([1, 2]))) for _ in range(turns)]
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "_wmtm_flags.json").write_text(json.dumps(flags))
    m = WMTM(WMTMConfig(state_dir=tmp_path, journal=ListJournal(jt), reasoner="off", use_pln=False))
    admitted, blocks = [], []
    orig = WMTMStore.admit

    def rec(self, item_id, content, *a, **kw):
        if item_id not in self._items and kw.get("source_type", "recalled") == "recalled":
            admitted.append(item_id)
        return orig(self, item_id, content, *a, **kw)
    WMTMStore.admit = rec
    real_time = time.time
    try:
        for i, q in enumerate(qs):
            time.time = lambda i=i: FIXED_NOW + 60.0 * i
            m.observe({"user": q})
            ctxt = m.context_for(q) or ""
            blocks.append("\n".join(ln for ln in ctxt.splitlines()[1:]))    # the header line carries a timestamp
    finally:
        WMTMStore.admit = orig
        time.time = real_time
    return admitted, blocks


@pytest.mark.parametrize("seed", range(6))
def test_api_unset_flag_behaves_as_turn_plus_10(tmp_path, seed):
    """No flag (nothing in the flags file, no env) admits and shows exactly what turn + recall_spread_add_pct 10 does
    (the default since t-2026-11-13-wmtm-spread-seed-default; before it, all)."""
    assert _run_api(tmp_path / "unset", seed, {}) == \
        _run_api(tmp_path / "p10", seed, {"recall_spread_seeds": "turn", "recall_spread_add_pct": 10})


@pytest.mark.parametrize("seed", range(6))
def test_api_negative_control_focus_or_turn_differ(tmp_path, seed):
    """The comparison above is not vacuous: on the same scripts focus or turn admits something else."""
    base = _run_api(tmp_path / "all", seed, {"recall_spread_seeds": "all"})[0]
    assert _run_api(tmp_path / "focus", seed, {"recall_spread_seeds": "focus"})[0] != base or \
        _run_api(tmp_path / "turn", seed, {"recall_spread_seeds": "turn"})[0] != base


def test_api_passes_mode_and_request_id(tmp_path, monkeypatch):
    seen = []
    orig = RecallBridge.recall

    def spy(self, q, store, *a, **kw):
        seen.append(dict(kw))
        return orig(self, q, store, *a, **kw)
    monkeypatch.setattr(RecallBridge, "recall", spy)
    monkeypatch.setenv("WMTM_RECALL_SPREAD_SEEDS", "turn")
    rng = random.Random(3)
    (tmp_path / "_wmtm_flags.json").write_text("{}")
    m = WMTM(WMTMConfig(state_dir=tmp_path, journal=ListJournal(_journal(rng)), reasoner="off", use_pln=False))
    m.observe({"user": "amber ember"})
    m.context_for("amber ember")
    assert seen and seen[-1]["spread_seeds"] == "turn"
    rid = ctx.request_item_id("amber ember", m._flags())
    assert seen[-1]["request_id"] == rid and rid in m.orchestrator.store      # the id admit_request_item used
    seen.clear()
    monkeypatch.setenv("WMTM_RECALL_SPREAD_SEEDS", "all")
    m.observe({"user": "cobalt"})
    m.context_for("cobalt")
    assert seen and "spread_seeds" not in seen[-1] and "request_id" not in seen[-1]   # all: the old call
    seen.clear()
    monkeypatch.delenv("WMTM_RECALL_SPREAD_SEEDS")
    m.observe({"user": "garnet"})
    m.context_for("garnet")
    assert seen and seen[-1]["spread_seeds"] == "turn" and seen[-1]["add_pct"] == 10.0   # default: turn + 10


def test_request_item_id_off_and_empty():
    assert ctx.request_item_id("", {}) is None
    assert ctx.request_item_id("hello there", {"request_item": False}) is None
    assert ctx.request_item_id("hello   there", {}) == ctx.request_item_id("hello there", {})
