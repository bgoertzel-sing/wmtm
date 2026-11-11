"""t-2026-11-11-wmtm-recall-budget-10: design s8.3 / s10 recall_budget ("Each cycle: admit at most N new items
(default: 10)"; "recall_budget: 10  # max new items per cycle").

One budget per WMTM cycle, shared by every path that admits recalled items in that cycle: the user-turn recall in
api.context_for and orchestrator.cycle(recall_fn=...).  Automated ticks have no recall step.  Property tests run seeded
random journals and turn scripts; each has a negative control (no budget) showing the same script exceeds 10, so the
property is not vacuous.  Synthetic clusters only.
"""
import json
import random
import time

import pytest

from wmtm import context as ctx
from wmtm import runtime_config as rc
from wmtm.api import WMTM, WMTMConfig
from wmtm.orchestrator import WMTMOrchestrator
from wmtm.store import WMTMStore

WORDS = ["amber", "basalt", "cobalt", "dynamo", "ember", "fjord", "garnet", "harbor"]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("WMTM_RECALL_BUDGET", "WMTM_RECALL_RELEVANCE_FLOOR", "WMTM_REASONER"):
        monkeypatch.delenv(k, raising=False)


class ListJournal:
    def __init__(self, text=""):
        self.lines = text.splitlines()

    def read_lines(self):
        return list(self.lines)

    def append(self, note, supersedes=None, about=None):
        return {"ok": True}


def _journal(rng, n=70, links=60):
    """n recent clusters, each with two random WORDS (so a two-word query matches far more than 10) and a unique
    token, plus random EvidenceFor / PromotesFrom links (graph-only candidates)."""
    t0 = time.time() - 2 * 3600
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


def _mem(tmp_path, journal, flags):
    (tmp_path / "_wmtm_flags.json").write_text(json.dumps(flags))
    return WMTM(WMTMConfig(state_dir=tmp_path, journal=ListJournal(journal), reasoner="off", use_pln=False))


@pytest.fixture
def admits(monkeypatch):
    """Record every store.admit: (cycle of the live orchestrator, id, new?, source_type)."""
    log, holder = [], {}
    orig = WMTMStore.admit

    def admit(self, item_id, content, *a, **kw):
        new = item_id not in self._items
        it = orig(self, item_id, content, *a, **kw)
        orch = holder.get("orch")
        log.append((orch.cycle_count if orch else None, item_id, new, kw.get("source_type", a[0] if a else "recalled")))
        return it
    monkeypatch.setattr(WMTMStore, "admit", admit)
    return log, holder


def _per_cycle_new_recalled(log):
    out = {}
    for cyc, _iid, new, src in log:
        if new and src == "recalled":
            out[cyc] = out.get(cyc, 0) + 1
    return out


def _run_script(tmp_path, rng, flags, admits, turns=12):
    log, holder = admits
    m = _mem(tmp_path, _journal(rng), flags)
    for _ in range(turns):
        q = " ".join(rng.sample(WORDS, rng.choice([1, 2, 3])))
        m.observe({"user": q})
        m._ensure_store_ready()
        holder["orch"] = m.orchestrator
        m.context_for(q)
    return _per_cycle_new_recalled(log)


# ------------------------------------------------------------------------------------------------ config

def test_spec_default_is_design_value_10():
    assert rc.SPEC["recall_budget"][:3] == ("WMTM_RECALL_BUDGET", int, 10)
    assert ctx.recall_budget({}) == 10
    assert ctx.recall_budget(rc.resolve(None, environ={})) == 10


def test_flag_env_invalid_and_off(tmp_path):
    assert ctx.recall_budget({"recall_budget": 4}) == 4
    assert ctx.recall_budget({"recall_budget": "junk"}) == 10        # invalid -> SPEC default
    assert ctx.recall_budget({"recall_budget": 0}) is None           # 0 or less = no budget
    assert ctx.recall_budget({"recall_budget": -3}) is None
    assert ctx.recall_budget(rc.resolve(None, environ={"WMTM_RECALL_BUDGET": "7"})) == 7
    assert ctx.recall_budget(rc.resolve(None, environ={"WMTM_RECALL_BUDGET": "x"})) == 10


# ------------------------------------------------------------------------------- user turn (api.py) property

@pytest.mark.parametrize("seed", range(12))
def test_property_user_turns_never_exceed_budget(tmp_path, admits, seed):
    rng = random.Random(seed)
    budget = rng.choice([1, 3, 5, 10, 10, 12])
    per = _run_script(tmp_path, rng, {"recall_budget": budget}, admits)
    assert per, "no recall at all: the script is vacuous"
    assert max(per.values()) <= budget, per
    assert max(per.values()) == budget, per      # the budget binds on this script (not vacuous)


@pytest.mark.parametrize("seed", range(4))
def test_property_negative_control_no_budget_exceeds_10(tmp_path, admits, seed):
    """Same scripts with the budget off (0): some cycle admits more than 10 new items (the old top-15 cut), so the
    property above would catch a budget that is not applied."""
    per = _run_script(tmp_path, random.Random(seed), {"recall_budget": 0}, admits)
    assert max(per.values()) > 10, per
    assert max(per.values()) <= ctx.RECALL_TOP_K_UNBUDGETED


def test_default_budget_applies_without_a_flag(tmp_path, admits):
    per = _run_script(tmp_path, random.Random(99), {}, admits)
    assert max(per.values()) == 10, per


def test_budget_keeps_the_best_candidates(tmp_path, admits):
    """The cut keeps the highest-scoring new candidates: budget 10 admits a prefix of what budget 15 admits."""
    log, holder = admits
    rng_j = random.Random(5)
    journal = _journal(rng_j)
    got = {}
    for b in (10, 15):
        log.clear()
        d = tmp_path / ("b%d" % b); d.mkdir()
        m = _mem(d, journal, {"recall_budget": b})
        m._ensure_store_ready(); holder["orch"] = m.orchestrator
        m.observe({"user": "amber basalt cobalt"}); m.context_for("amber basalt cobalt")
        got[b] = [iid for _c, iid, new, src in log if new and src == "recalled"]
    assert len(got[10]) == 10 and len(got[15]) == 15
    assert got[10] == got[15][:10]


# --------------------------------------------------------------------------------- cycle(recall_fn) path

def _rows(rng, n, prefix="r"):
    return [("%s%d" % (prefix, i), "content %s%d" % (prefix, i), round(rng.uniform(1, 50), 3)) for i in range(n)]


def _orch(tmp_path, budget):
    (tmp_path / "_wmtm_flags.json").write_text(json.dumps({"recall_budget": budget, "reasoner": "off"}))
    o = WMTMOrchestrator(WMTMStore(capacity=500), use_pln=False)
    o.runtime_state_dir = str(tmp_path)
    return o


@pytest.mark.parametrize("seed", range(10))
def test_property_recall_fn_never_exceeds_budget_and_keeps_top_sti(tmp_path, seed):
    rng = random.Random(seed)
    budget = rng.choice([1, 4, 10, 10, 13])
    o = _orch(tmp_path, budget)
    for c in range(6):
        rows = _rows(rng, rng.randrange(0, 30), prefix="c%d-" % c)
        before = set(o.store._items)
        o.cycle(recall_fn=lambda r=rows: r)
        new = set(o.store._items) - before
        assert len(new) <= budget
        assert len(new) == min(budget, len(rows))
        want = {iid for iid, _c, _s in sorted(rows, key=lambda r: -r[2])[:budget]}
        assert new == want


def test_recall_fn_negative_control_no_budget_admits_all(tmp_path):
    o = _orch(tmp_path, 0)
    rows = _rows(random.Random(1), 25)
    o.cycle(recall_fn=lambda: rows)
    assert len(o.store) == 25


def test_recall_fn_readmission_of_residents_is_not_limited(tmp_path):
    o = _orch(tmp_path, 2)
    rows = _rows(random.Random(2), 5)
    for iid, c, s in rows:
        o.store.admit(iid, c, initial_sti=1.0)
    o.cycle(recall_fn=lambda: rows + _rows(random.Random(3), 5, prefix="n"))
    assert len(o.store) == 7                                   # 5 residents refreshed + 2 new


def test_budget_is_shared_by_both_paths_in_one_cycle(tmp_path):
    """api.context_for counts its admissions in the same cycle that cycle(recall_fn) then runs under."""
    o = _orch(tmp_path, 10)
    for _ in range(7):
        assert o.take_recall_slot(10)
    before = set(o.store._items)
    o.cycle(recall_fn=lambda: _rows(random.Random(4), 20))
    assert len(set(o.store._items) - before) == 3
    assert o.recall_slots(10) == 10                            # the next cycle has a fresh budget


def test_spent_budget_survives_snapshot_restore_in_the_same_cycle(tmp_path):
    o = _orch(tmp_path, 10)
    for _ in range(10):
        assert o.take_recall_slot(10)
    assert not o.take_recall_slot(10)
    o2 = WMTMOrchestrator(WMTMStore(capacity=500), use_pln=False)
    o2.restore_state(json.loads(json.dumps(o.snapshot_state())))
    assert o2.recall_slots(10) == 0
    o2.cycle()
    assert o2.recall_slots(10) == 10


def test_user_turn_then_cycle_cannot_exceed_budget(tmp_path, admits):
    """A user turn spends the budget; a recall_fn admission later in the same cycle number gets nothing."""
    log, holder = admits
    m = _mem(tmp_path, _journal(random.Random(7)), {"recall_budget": 10})
    m._ensure_store_ready(); holder["orch"] = o = m.orchestrator
    real_cycle = o.cycle
    extra = _rows(random.Random(8), 12, prefix="x")
    o.cycle = lambda append_fn=None, recall_fn=None: real_cycle(recall_fn=lambda: extra, append_fn=append_fn)
    m.observe({"user": "amber basalt"}); m.context_for("amber basalt")
    per = _per_cycle_new_recalled(log)
    assert per[0] == 10, per
    assert not any(iid.startswith("x") for iid in o.store._items)


# -------------------------------------------------------------------------------------- automated ticks

def test_automated_ticks_admit_no_recalled_items(tmp_path, admits):
    log, holder = admits
    m = _mem(tmp_path, _journal(random.Random(11)), {"recall_budget": 10})
    m._ensure_store_ready(); holder["orch"] = m.orchestrator
    m.observe({"user": "amber"}); m.context_for("amber")
    ids0 = set(json.loads((tmp_path / "_wmtm_state.json").read_text())["store"]["items"])
    for _ in range(3):
        m.context_for("", automated=True)
    ids1 = set(json.loads((tmp_path / "_wmtm_state.json").read_text())["store"]["items"])
    assert ids1 <= ids0                                        # nothing new enters on an automated tick
