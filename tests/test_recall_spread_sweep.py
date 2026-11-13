"""t-2026-11-13-wmtm-spread-seed-sweep: flags recall_spread_fallback_pct and recall_spread_add_pct.

Both apply only with recall_spread_seeds=turn (E).  They add the top x% of residents by STI to E's seeds:
  fallback_pct: only on a turn where no cluster matches the query by keyword (E has no keyword seeds there);
  add_pct:      on every turn.
0 (the default) = plain E; with recall_spread_seeds unset (all) nothing changes at all.  Every behaviour test has a
negative control.  Synthetic clusters only.
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
ENV = ("WMTM_RECALL_BUDGET", "WMTM_RECALL_RELEVANCE_FLOOR", "WMTM_REASONER", "WMTM_RECALL_SPREAD_SEEDS",
       "WMTM_RECALL_SPREAD_FALLBACK_PCT", "WMTM_RECALL_SPREAD_ADD_PCT")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ENV:
        monkeypatch.delenv(k, raising=False)


def _c(cid, note, ev=(), pf=()):
    return LTMCluster(id=cid, event_note=note, evidence_for=list(ev), promotes_from=list(pf),
                      opened_at=time.time() - 3600)


def _world():
    """Residents H (STI 90), X (80), L (5), L2 (4), R (3, matches "zephyr"); non-residents GH -> H, GX -> X, GL -> L,
    GL2 -> L2, GR -> R, K (matches "zephyr"), GK -> K, N (nothing)."""
    cl = [
        _c("H", "hub alpha"), _c("X", "hub beta"), _c("L", "old gamma"), _c("L2", "old delta"),
        _c("R", "zephyr resident note"),
        _c("GH", "linked one", ev=["H"]), _c("GX", "linked six", ev=["X"]), _c("GL", "linked two", ev=["L"]),
        _c("GL2", "linked three", ev=["L2"]), _c("GR", "linked four", ev=["R"]),
        _c("K", "zephyr fresh keyword hit"), _c("GK", "linked five", pf=["K"]), _c("N", "unrelated"),
    ]
    rb = RecallBridge(cl)
    st = WMTMStore(capacity=50)
    for cid, sti in (("H", 90.0), ("X", 80.0), ("L", 5.0), ("L2", 4.0), ("R", 3.0)):
        st.admit(cid, cid, source_type="recalled", initial_sti=sti)
    return rb, st


MATCH, NOMATCH = "zephyr", "consequence then what follows"


def _ids(rb, st, q, **kw):
    return {c.cluster_id: c.score for c in rb.recall(q, st, top_k=50, floor=0.1, **kw)}


# ------------------------------------------------------------------------------------------------------- config

def test_spec_defaults_off():
    assert rc.SPEC["recall_spread_fallback_pct"][:3] == ("WMTM_RECALL_SPREAD_FALLBACK_PCT", float, 0.0)
    assert rc.SPEC["recall_spread_add_pct"][:3] == ("WMTM_RECALL_SPREAD_ADD_PCT", float, 0.0)
    for k in ("recall_spread_fallback_pct", "recall_spread_add_pct"):
        assert ctx.recall_spread_pct({}, k) == 0.0
        assert ctx.recall_spread_pct(rc.resolve(None, environ={}), k) == 0.0


@pytest.mark.parametrize("raw,want", [(50, 50.0), ("25", 25.0), (" 10 ", 10.0), (0, 0.0), (-5, 0.0), ("x", 0.0),
                                      (None, 0.0), (float("nan"), 0.0), (250, 100.0)])
def test_pct_parse(raw, want):
    assert ctx.recall_spread_pct({"recall_spread_add_pct": raw}, "recall_spread_add_pct") == want


def test_pct_from_env():
    cfg = rc.resolve(None, environ={"WMTM_RECALL_SPREAD_FALLBACK_PCT": "50", "WMTM_RECALL_SPREAD_ADD_PCT": "10"})
    assert ctx.recall_spread_pct(cfg, "recall_spread_fallback_pct") == 50.0
    assert ctx.recall_spread_pct(cfg, "recall_spread_add_pct") == 10.0


# ---------------------------------------------------------------------------------------------- top_sti_ids

def test_top_sti_ids_rounding():
    rb, st = _world()
    res = st.get_active_set()
    assert RecallBridge.top_sti_ids(res, 10) == {"H"}                 # ceil(0.5) = 1
    assert RecallBridge.top_sti_ids(res, 25) == {"H", "X"}            # ceil(1.25) = 2
    assert RecallBridge.top_sti_ids(res, 50) == {"H", "X", "L"}       # ceil(2.5) = 3, = focus
    assert RecallBridge.top_sti_ids(res, 100) == {"H", "X", "L", "L2", "R"}
    assert RecallBridge.top_sti_ids(res, 0) == set() and RecallBridge.top_sti_ids([], 50) == set()
    n60 = [type("I", (), {"id": "r%d" % i, "attention": type("A", (), {"sti": 100.0 - i})()})() for i in range(60)]
    assert len(RecallBridge.top_sti_ids(n60, 10)) == 6 and len(RecallBridge.top_sti_ids(n60, 25)) == 15
    assert len(RecallBridge.top_sti_ids(n60, 50)) == 30


@pytest.mark.parametrize("seed", range(10))
def test_top_50_equals_focus(seed):
    rng = random.Random(seed)
    rb = RecallBridge(_random_clusters(rng))
    st = _random_store(rng, rb, k=rng.randrange(1, 30))
    assert RecallBridge.top_sti_ids(st.get_active_set(), 50) == rb.spread_seed_ids("focus", set(), st)


# ------------------------------------------------------------------------------------------- default unchanged

def test_turn_with_zero_pcts_is_plain_turn():
    rb, st = _world()
    for q in (MATCH, NOMATCH):
        qt = rb._tokenize(q)
        plain = rb.spread_seed_ids("turn", qt, st, "user-1")
        assert rb.spread_seed_ids("turn", qt, st, "user-1", fallback_pct=0, add_pct=0) == plain
        assert _ids(rb, st, q, spread_seeds="turn", fallback_pct=0.0, add_pct=0.0) == _ids(rb, st, q, spread_seeds="turn")


@pytest.mark.parametrize("mode", ["all", "focus"])
def test_pcts_ignored_outside_turn(mode):
    rb, st = _world()
    for q in (MATCH, NOMATCH):
        assert _ids(rb, st, q, spread_seeds=mode, fallback_pct=50, add_pct=25) == _ids(rb, st, q, spread_seeds=mode)


# ---------------------------------------------------------------------------------------------------- fallback

def test_fallback_silent_on_match_turn():
    rb, st = _world()
    qt = rb._tokenize(MATCH)
    assert rb.spread_seed_ids("turn", qt, st, fallback_pct=50) == {"K", "R"}
    got = _ids(rb, st, MATCH, spread_seeds="turn", fallback_pct=50)
    assert got == _ids(rb, st, MATCH, spread_seeds="turn")
    assert "GH" not in got and "GK" in got


def test_fallback_fires_on_no_match_turn():
    rb, st = _world()
    qt = rb._tokenize(NOMATCH)
    assert rb.spread_seed_ids("turn", qt, st, "user-1") == {"user-1"}
    assert rb.spread_seed_ids("turn", qt, st, "user-1", fallback_pct=50) == {"user-1", "H", "X", "L"}
    assert rb.spread_seed_ids("turn", qt, st, fallback_pct=25) == {"H", "X"}
    got = _ids(rb, st, NOMATCH, spread_seeds="turn", fallback_pct=50)
    assert {"GH", "GX", "GL"} <= set(got) and not ({"GL2", "GR", "GK"} & set(got))
    # negative control: plain E recalls nothing on this turn
    assert _ids(rb, st, NOMATCH, spread_seeds="turn") == {}


def test_fallback_on_no_match_equals_focus_seeds():
    rb, st = _world()
    qt = rb._tokenize(NOMATCH)
    assert rb.spread_seed_ids("turn", qt, st, fallback_pct=50) == rb.spread_seed_ids("focus", qt, st)


# ---------------------------------------------------------------------------------------------------- additive

def test_add_on_match_turn():
    rb, st = _world()
    qt = rb._tokenize(MATCH)
    assert rb.spread_seed_ids("turn", qt, st, add_pct=25) == {"K", "R", "H", "X"}
    got = _ids(rb, st, MATCH, spread_seeds="turn", add_pct=25)
    assert {"GK", "GR", "GH", "GX"} <= set(got) and not ({"GL", "GL2"} & set(got))
    # negative controls: plain E and E + fallback do not reach H's and X's links on a matching turn
    for kw in ({}, {"fallback_pct": 25}):
        g = _ids(rb, st, MATCH, spread_seeds="turn", **kw)
        assert "GH" not in g and "GX" not in g


def test_add_on_no_match_turn_and_size():
    rb, st = _world()
    qt = rb._tokenize(NOMATCH)
    assert rb.spread_seed_ids("turn", qt, st, add_pct=10) == {"H"}
    assert set(_ids(rb, st, NOMATCH, spread_seeds="turn", add_pct=10)) == {"GH"}


def test_both_set_no_match_takes_larger():
    rb, st = _world()
    q0, q1 = rb._tokenize(NOMATCH), rb._tokenize(MATCH)
    assert rb.spread_seed_ids("turn", q0, st, fallback_pct=50, add_pct=10) == {"H", "X", "L"}
    assert rb.spread_seed_ids("turn", q1, st, fallback_pct=50, add_pct=10) == {"K", "R", "H"}


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


@pytest.mark.parametrize("seed", range(10))
def test_property_fallback_only_on_no_match(seed):
    """Over random worlds and queries (half match nothing): E + fallback recalls exactly what plain E recalls on a
    matching turn, and exactly what E with the top x% added does on a no-match turn; there it differs from plain E
    on at least one world (negative control, checked in aggregate)."""
    rng = random.Random(seed)
    differs = 0
    for _ in range(6):
        rb = RecallBridge(_random_clusters(rng))
        st = _random_store(rng, rb)
        for q in (" ".join(rng.sample(WORDS, 1)), "quixotic zzyzx"):
            qt = rb._tokenize(q)
            nomatch = not any(rb._keyword_matches(c, qt) for c in rb._clusters)
            fb = _ids(rb, st, q, spread_seeds="turn", fallback_pct=50)
            plain = _ids(rb, st, q, spread_seeds="turn")
            if nomatch:
                assert fb == _ids(rb, st, q, spread_seeds="turn", add_pct=50)
                assert plain == {}
                differs += fb != plain
            else:
                assert fb == plain
    assert differs > 0


@pytest.mark.parametrize("seed", range(10))
def test_property_add_every_turn(seed):
    """E + add x%: the seeds are E's plus exactly the top x% residents on every turn, matching or not."""
    rng = random.Random(100 + seed)
    rb = RecallBridge(_random_clusters(rng))
    st = _random_store(rng, rb)
    res = st.get_active_set()
    for x in (10, 25):
        for q in (" ".join(rng.sample(WORDS, 2)), "quixotic zzyzx"):
            qt = rb._tokenize(q)
            plain = rb.spread_seed_ids("turn", qt, st)
            assert rb.spread_seed_ids("turn", qt, st, add_pct=x) == plain | RecallBridge.top_sti_ids(res, x)
            assert len(RecallBridge.top_sti_ids(res, x)) == -(-len(res) * x // 100)


# ------------------------------------------------------------------------------------------- API (live turn)

class ListJournal:
    def __init__(self, text=""):
        self.lines = text.splitlines()

    def read_lines(self):
        return list(self.lines)

    def append(self, note, supersedes=None, about=None):
        return {"ok": True}


FIXED_NOW = 1794350000.0


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


def _run_api(tmp_path, seed, flags, nomatch_every=0, turns=10):
    """A seeded 10-turn script through WMTM.observe + context_for -> (new recalled ids in order, context blocks).
    nomatch_every=k: every k-th turn asks a query that matches no cluster ("quixotic zzyzx")."""
    rng = random.Random(seed)
    jt = _journal(rng)
    qs = [" ".join(rng.sample(WORDS, rng.choice([1, 2]))) for _ in range(turns)]
    if nomatch_every:
        qs = ["quixotic zzyzx" if (i + 1) % nomatch_every == 0 else q for i, q in enumerate(qs)]
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
            blocks.append("\n".join(ln for ln in ctxt.splitlines()[1:]))
    finally:
        WMTMStore.admit = orig
        time.time = real_time
    return admitted, blocks


@pytest.mark.parametrize("seed", range(4))
def test_api_default_unchanged(tmp_path, seed):
    """Flags unset = all; pct flags without turn = all; turn with pcts 0 = plain turn (same admissions and blocks)."""
    base = _run_api(tmp_path / "unset", seed, {}, nomatch_every=3)
    assert _run_api(tmp_path / "pcts", seed, {"recall_spread_fallback_pct": 50, "recall_spread_add_pct": 25},
                    nomatch_every=3) == base
    turn = _run_api(tmp_path / "turn", seed, {"recall_spread_seeds": "turn"}, nomatch_every=3)
    assert _run_api(tmp_path / "turn0", seed, {"recall_spread_seeds": "turn", "recall_spread_fallback_pct": 0,
                                               "recall_spread_add_pct": 0}, nomatch_every=3) == turn


@pytest.mark.parametrize("seed", range(4))
def test_api_fallback_only_changes_no_match_scripts(tmp_path, seed):
    f = {"recall_spread_seeds": "turn"}
    fb = dict(f, recall_spread_fallback_pct=50)
    # every query matches: the fallback never fires, so the run equals plain E
    assert _run_api(tmp_path / "a", seed, fb) == _run_api(tmp_path / "b", seed, f)
    # negative control: with no-match turns it admits something plain E does not
    assert _run_api(tmp_path / "c", seed, fb, nomatch_every=2)[0] != _run_api(tmp_path / "d", seed, f, nomatch_every=2)[0]


def test_api_passes_pcts(tmp_path, monkeypatch):
    seen = []
    orig = RecallBridge.recall

    def spy(self, q, store, *a, **kw):
        seen.append(dict(kw))
        return orig(self, q, store, *a, **kw)
    monkeypatch.setattr(RecallBridge, "recall", spy)
    (tmp_path / "_wmtm_flags.json").write_text("{}")
    rng = random.Random(3)
    m = WMTM(WMTMConfig(state_dir=tmp_path, journal=ListJournal(_journal(rng)), reasoner="off", use_pln=False))
    monkeypatch.setenv("WMTM_RECALL_SPREAD_SEEDS", "turn")
    monkeypatch.setenv("WMTM_RECALL_SPREAD_FALLBACK_PCT", "50")
    monkeypatch.setenv("WMTM_RECALL_SPREAD_ADD_PCT", "10")
    m.observe({"user": "amber"}); m.context_for("amber")
    assert seen[-1]["fallback_pct"] == 50.0 and seen[-1]["add_pct"] == 10.0 and seen[-1]["spread_seeds"] == "turn"
    monkeypatch.delenv("WMTM_RECALL_SPREAD_ADD_PCT"); monkeypatch.setenv("WMTM_RECALL_SPREAD_FALLBACK_PCT", "0")
    m.observe({"user": "ember"}); m.context_for("ember")
    assert "fallback_pct" not in seen[-1] and "add_pct" not in seen[-1]          # plain E: the probe's call
    monkeypatch.delenv("WMTM_RECALL_SPREAD_SEEDS"); monkeypatch.setenv("WMTM_RECALL_SPREAD_ADD_PCT", "25")
    m.observe({"user": "cobalt"}); m.context_for("cobalt")
    assert "spread_seeds" not in seen[-1] and "add_pct" not in seen[-1]          # default all: the old call
