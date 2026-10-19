"""Track P (v0.5.0-rc3): recall/context plumbing.  Synthetic data only (invented notes, no real memories).

(a) stale cleanup spares items recalled for the current request (user path and automated fast path);
(b) the block is ranked by request relevance + STI, with longer items under a total character budget;
(c) the request is admitted as a source_type=user item; derived conclusions matching it rank into the block;
(d) parse-gate identifier rule: any short prefix before a hash-like run (ref_, tag_, ...);
(e) worker priority re-asserted every 1 s.
"""
import json
import time

import pytest

from wmtm import context as ctx
from wmtm import parse_gate as pg
from wmtm import pc_shadow
from wmtm import runtime_config as rc
from wmtm.api import WMTM, WMTMConfig
from wmtm.store import WMTMStore

DAY = 86400.0
OLD = time.gmtime(time.time() - 10 * DAY)          # 10 days: past the 48 h zero-utility recall cutoff


def _cluster(cid_ts, iso, note, about="journal"):
    cid = "ep-note-" + cid_ts
    return (f";;; BEGIN MemoryCluster {cid}\n(MemoryCluster {cid})\n(SchemaVersion {cid} medium-memory-v1)\n"
            f"(ClusterType {cid} Episode)\n(ClusterSource {cid} iter-experience)\n"
            f"(ClusterOpenedAt {cid} {iso})\n(Contains {cid} ev-{cid})\n(ObservedEvent ev-{cid})\n"
            f"(About {cid} {about})\n(EventNote ev-{cid} \"{note}\")\n;;; END MemoryCluster {cid}\n"), cid


def _old(offset_s, note):
    t = time.gmtime(time.time() - 10 * DAY + offset_s)
    return _cluster(time.strftime("%Y%m%dT%H%M%SZ", t), time.strftime("%Y-%m-%dT%H:%M:%SZ", t), note)


LONG_TAIL = " ".join(["filler"] * 40) + " the decisive number is 7731 seconds"
OTTER, OTTER_ID = _old(0, "The otter-lamp project uses a brass hinge from the Varnwick supplier. " + LONG_TAIL)
HERON, HERON_ID = _old(60, "Varnwick supplier ships brass hinges in batches of twelve for the otter-lamp")
NOISE, NOISE_ID = _old(120, "Gardening log: tomato seedlings moved to the greenhouse on Tuesday")
JOURNAL = OTTER + HERON + NOISE
Q = "which supplier makes the brass hinge for the otter-lamp project?"


class ListJournal:
    def __init__(self, text=""):
        self.lines = text.splitlines()

    def read_lines(self):
        return list(self.lines)

    def append(self, note, supersedes=None, about=None):
        return {"ok": True}


def _mem(tmp_path, flags=None, journal=JOURNAL):
    if flags is not None:
        (tmp_path / "_wmtm_flags.json").write_text(json.dumps(flags))
    return WMTM(WMTMConfig(state_dir=tmp_path, journal=ListJournal(journal), reasoner="off"))


def _turn(m, q=Q):
    m.observe({"user": q})
    return m.context_for(q)


def _state(tmp_path):
    return json.loads((tmp_path / "_wmtm_state.json").read_text())


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("WMTM_CLEANUP_PROTECT_RECENT", "WMTM_CONTEXT_RANK", "WMTM_REQUEST_ITEM", "WMTM_REASONER"):
        monkeypatch.delenv(k, raising=False)


# ── (a) fresh recalls survive cleanup ────────────────────────────────

def test_fresh_old_recall_reaches_block_and_survives_fast_path(tmp_path):
    m = _mem(tmp_path)
    block = _turn(m)
    assert block and "Varnwick" in block, block
    st = _state(tmp_path)
    assert OTTER_ID in st["store"]["items"] and st["store"]["items"][OTTER_ID]["recalled_at"] > 0
    auto = ctx.fast_path_automated(str(tmp_path / "_wmtm_state.json"), run_hooks=False, admit=False)
    assert "Varnwick" in auto
    assert OTTER_ID in _state(tmp_path)["store"]["items"]       # not evicted by the automated tick either


def test_rc2_behaviour_when_protect_off(tmp_path):
    m = _mem(tmp_path, {"cleanup_protect_recent": False})
    block = _turn(m)
    assert block is None or "Varnwick" not in block              # rc2 bug, kept reachable behind the flag
    assert OTTER_ID not in _state(tmp_path)["store"]["items"]


def test_cleanup_grace_window_and_noise():
    now = time.time()
    s = WMTMStore(capacity=10)
    a = s.admit("ep-note-a", "brass hinge note with enough words", origin_timestamp=now - 10 * DAY)
    b = s.admit("ep-note-b", "another old note with enough words", origin_timestamp=now - 10 * DAY)
    n = s.admit("ep-note-n", "ChannelContractError: processing/ is empty again", origin_timestamp=now - 10 * DAY)
    a.mark_recalled(5)
    n.mark_recalled(5)
    prot = {"turns": 2, "s": 0.0}
    ctx.cleanup_stale_items(s, 7, protect=prot)
    assert "ep-note-a" in s and "ep-note-b" not in s and "ep-note-n" not in s   # noise is never protected
    ctx.cleanup_stale_items(s, 8, protect=prot)                                   # 3 cycles later, 0 s grace
    assert "ep-note-a" not in s
    assert ctx.is_recent_recall(now - 10, 0, 100, now, {"turns": 0, "s": 60})     # wall-clock grace
    assert not ctx.is_recent_recall(0.0, 5, 5, now, {"turns": 10, "s": 60})       # never recalled
    assert ctx.protect_settings({"cleanup_protect_recent": False}) is None
    assert ctx.protect_settings({}) == {"turns": 10, "s": 1800.0}


def test_fast_path_grace_expires(tmp_path):
    now = time.time()
    item = {"id": "ep-note-x", "content": "an old recalled note about hinges", "source_type": "recalled",
            "origin_cluster": None, "derived_from": [], "attention": {"sti": 5.0, "ati": 0, "lti": 0},
            "age": 0, "utility": 0.0, "last_used": 0, "created_at": now, "origin_timestamp": now - 10 * DAY}
    for recalled_at, recalled_cycle, kept in ((now - 5, 99, True), (now - 7200, 50, False)):
        d = dict(item, attention=dict(item["attention"]), recalled_at=recalled_at, recalled_cycle=recalled_cycle)
        p = tmp_path / ("s%d.json" % kept)
        p.write_text(json.dumps({"cycle": 100, "store": {"capacity": 60, "tick": 0, "items": {"ep-note-x": d}}}))
        ctx.fast_path_automated(str(p), run_hooks=False, admit=False)
        assert ("ep-note-x" in json.loads(p.read_text())["store"]["items"]) is kept


# ── (b) ranking + budget ─────────────────────────────────────────────

def _entry(i, sti, content, src="recalled"):
    return {"id": i, "src": src, "sti": sti, "util": 0.0, "age": 3600.0, "content": content, "total": sti}


def test_ranking_relevance_beats_attention_and_budget_holds():
    ents = [_entry("hi-sti-%d" % k, 50.0 - k, "unrelated high attention note %d " % k + "x" * 600) for k in range(20)]
    ents.append(_entry("relevant", 0.5, "the answer " + "y" * 700))
    ents.append(_entry("req", 99.0, "the request itself", src="user"))
    rel = {"scores": {"relevant": 1.0}}
    cfg = {"context_item_chars": 500, "context_total_chars": 2000, "context_max_items": 4}
    text, shown = ctx.render_ranked(ents, rel, 7, cfg)
    assert shown[0] == "relevant" and "req" not in shown
    lines = text.split("\n")
    assert lines[0] == "[WMTM Active Working Memory (21 items, showing top %d, cycle 7)]" % len(shown)
    assert " rel=1.00] the answer" in lines[1]
    body = sum(len(l.split("] ", 1)[1]) for l in lines[1:])
    assert body <= 2000 and len(lines[1].split("] ", 1)[1]) == 500           # 500 chars, not rc2's 200
    assert len(shown) == 4


def test_budget_is_shared_between_items():
    ents = [_entry("e%d" % k, 10.0 - k, "z" * 900) for k in range(15)]
    text, shown = ctx.render_ranked(ents, None, 1, {"context_total_chars": 6000, "context_item_chars": 600})
    assert len(shown) == 15
    assert all(len(l.split("] ", 1)[1]) == 400 for l in text.split("\n")[1:])     # 6000 / 15


def test_long_item_shows_request_window():
    note = "Oct01 10:00 consolidation. " + "unrelated words here " * 40 + "the hinge torque limit is 42 newton metres. " \
        + "more unrelated text " * 20
    out = ctx._clip(note, 300, {"torque": 5.0, "hinge": 3.0})
    assert out.startswith("Oct01 10:00 consolidation. … ") and "torque limit is 42" in out and len(out) <= 300
    assert ctx._clip(note, 300) == note[:299].rstrip() + "…"                          # no terms: plain head cut


def test_min_request_items_pinned():
    ents = [_entry("s%d" % k, 100.0, "attention item %d" % k) for k in range(20)]
    ents += [_entry("r%d" % k, 0.1, "weak match %d" % k) for k in range(3)]
    rel = {"scores": {"r0": 0.05, "r1": 0.04, "r2": 0.03}}
    _, shown = ctx.render_ranked(ents, rel, 1, {"context_min_request_items": 2, "context_rank_weights": "0.1,0.9"})
    assert shown[:2] == ["r0", "r1"] and "r2" not in shown


def test_min_score_drops_filler_only_with_a_request():
    ents = [_entry("rel", 1.0, "match")] + [_entry("f%d" % k, 1.0, "filler %d" % k) for k in range(5)]
    ents.append(_entry("hot", 10.0, "high attention"))
    _, shown = ctx.render_ranked(ents, {"scores": {"rel": 1.0}}, 1, {})
    assert shown == ["rel", "hot"]                      # filler: 0.3 * 1/10 < 0.2
    _, shown = ctx.render_ranked(ents, None, 1, {})
    assert len(shown) == 7                              # no request known: nothing dropped (STI order)


def test_rank_off_is_rc2_format(tmp_path):
    m = _mem(tmp_path, {"context_rank": False})
    block = _turn(m)
    assert " rel=" not in block
    for line in block.split("\n")[1:]:
        assert len(line.split("] ", 1)[1]) <= 200
    assert "context_rel" not in _state(tmp_path)


def test_user_turn_shows_long_relevant_text_first(tmp_path):
    m = _mem(tmp_path)
    block = _turn(m)
    lines = block.split("\n")
    assert "otter-lamp" in lines[1] and " rel=1.00]" in lines[1]
    assert "7731 seconds" in block                         # past rc2's 200-char cut
    assert "tomato" not in block
    st = _state(tmp_path)
    assert st["context_rel"]["scores"][OTTER_ID] > 0 and "hinge" in st["context_rel"]["terms"]


# ── (c) request item + derived relevance ─────────────────────────────

def test_request_item_admitted_replaced_and_hidden(tmp_path):
    m = _mem(tmp_path)
    block = _turn(m)
    users = [d for d in _state(tmp_path)["store"]["items"].values() if d["source_type"] == "user"]
    assert len(users) == 1 and users[0]["content"] == Q and Q not in block
    _turn(m, "and how many hinges come in one Varnwick batch?")
    users = [d for d in _state(tmp_path)["store"]["items"].values() if d["source_type"] == "user"]
    assert len(users) == 1 and "batch" in users[0]["content"]
    raw = [pc_shadow.raw_item_from_dict(d) for d in users]
    assert raw[0]["source_type"] == "user"
    items = pc_shadow._RawStore(raw).get_active_set()
    ents, toks = pc_shadow.request_terms({}, items, set())
    assert "varnwick" in toks and "hinges" in toks       # request-overlap goal ranking now has request terms


def test_request_item_off(tmp_path):
    m = _mem(tmp_path, {"request_item": False})
    _turn(m)
    assert not [d for d in _state(tmp_path)["store"]["items"].values() if d["source_type"] == "user"]


def test_derived_conclusion_matching_request_ranks_into_block(tmp_path):
    m = _mem(tmp_path)
    m.context_for("warm up the store with an unrelated question about tomato seedlings")
    m._orchestrator.store.admit("derived-pc_deduction-1-abcd1234", "varnwick_supplier is a hinge_maker",
                                source_type="derived", initial_sti=0.4)
    for k in range(20):
        m._orchestrator.store.admit("derived-x%d" % k, "unrelated derived note number %d about kettles" % k,
                                    source_type="derived", initial_sti=30.0)
    m._orchestrator.store.get("derived-pc_deduction-1-abcd1234").utility = 1.0
    block = _turn(m, "who is the hinge maker, is it the Varnwick supplier?")
    shown = block.split("\n")[1:]
    pos = [i for i, l in enumerate(shown) if "varnwick_supplier is a hinge_maker" in l]
    assert pos and pos[0] < 5, block


def test_fast_path_scores_late_derived_items_against_last_request(tmp_path):
    m = _mem(tmp_path)
    _turn(m)
    p = tmp_path / "_wmtm_state.json"
    st = json.loads(p.read_text())
    st["store"]["items"]["derived-pc_deduction-9-0000beef"] = {
        "id": "derived-pc_deduction-9-0000beef", "content": "otter_lamp is a brass_hinge_project",
        "source_type": "derived", "origin_cluster": None, "derived_from": [],
        "attention": {"sti": 0.3, "ati": 0, "lti": 0}, "age": 0, "utility": 1.0, "last_used": 0,
        "created_at": time.time(), "origin_timestamp": 0.0}
    p.write_text(json.dumps(st))
    auto = ctx.fast_path_automated(str(p), run_hooks=False, admit=False)
    line = [l for l in auto.split("\n") if "otter_lamp is a brass_hinge_project" in l]
    assert line and " rel=" in line[0]


# ── (d) identifier rule ──────────────────────────────────────────────

ST = pg.settings({})


@pytest.mark.parametrize("subj", ["ref_3c9e1a7", "ref-3c9e1a7", "tag_0a1b2c3d", "build_1a2b3c4", "sha_deadbee1",
                                  "rev_1234567", "commit_0123456789abcdef"])
def test_identifier_after_any_short_prefix_typed_as_branch(subj):
    assert pg.is_identifier(subj)
    assert pg.check_fact(("Member", subj, "branch", 0.9, 0.9), None, ST)[1:] == ("identifier_category", "reject")


@pytest.mark.parametrize("name", ["release_20250307", "demo_deploy_20250307", "tool_36b3fe6_dedup", "ref_deadbeef",
                                  "phase_m", "x_1234567", "branch_feature"])
def test_names_are_not_identifiers(name):
    assert not pg.is_identifier(name)
    assert pg.check_fact(("Member", name, "branch", 0.9, 0.9), None, ST)[1] is None


# ── (e) worker priority refresh ──────────────────────────────────────

def test_priority_refresh_default_1s():
    assert rc.resolve(None, environ={})["worker_prio_refresh_s"] == 1.0
    assert rc.PriorityGuard({}).interval == 1.0
    assert rc.PriorityGuard(rc.resolve(None, environ={})).interval == 1.0


def test_track_p_flags_have_defaults_and_env():
    cfg = rc.resolve(None, environ={"WMTM_CONTEXT_RANK": "0", "WMTM_CONTEXT_ITEM_CHARS": "300"})
    assert cfg["context_rank"] is False and cfg["context_item_chars"] == 300
    d = rc.resolve(None, environ={})
    assert (d["cleanup_protect_recent"], d["request_item"], d["context_total_chars"]) == (True, True, 6000)


# ── recall latency: spreading activation computed once per active set ──

def test_spread_cache_matches_uncached():
    from wmtm.recall_bridge import LTMCluster, RecallBridge
    cl = [LTMCluster(id="c%d" % i, event_note="note %d about hinges" % i,
                     evidence_for=["c%d" % ((i + 1) % 6)]) for i in range(6)]
    rb = RecallBridge(cl)
    st = WMTMStore(capacity=10)
    for cid in ("c0", "c3"):
        st.admit(cid, "x")
    active = {"c0", "c3"}
    got = [rb._spreading_activation_for(c, active, st) for c in cl]
    ref = []
    for c in cl:
        rb._spread_cache = None
        ref.append(rb._spreading_activation_for(c, active, st))
    assert got == ref and any(got)
    other = {"c5"}
    assert rb._spreading_activation_for(cl[2], other, st) != rb._spreading_activation_for(cl[2], active, st)
