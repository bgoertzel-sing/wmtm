"""M-05 (S2 design part a; design s7.1c / s7.1b / s10 / s12.1 / s12.4): composite capacity eviction, flag composite_eviction."""
import os

import pytest

from wmtm import runtime_config as rc
from wmtm.eviction import composite_score, eviction_cfg
from wmtm.forgetting import ForgettingPolicy
from wmtm.orchestrator import WMTMOrchestrator
from wmtm.store import WMTMStore


@pytest.fixture(autouse=True)
def _isolated_flags(monkeypatch, tmp_path):
    for k in list(os.environ):
        if k.startswith("WMTM_") and k not in ("WMTM_PC_PETTA", "WMTM_PC_VENDOR", "WMTM_SWIPL_BIN"):
            monkeypatch.delenv(k, raising=False)
    monkeypatch.chdir(tmp_path)


ON = {"composite_eviction": True}


def _set(store, sid, util=0.0, lti=0.0):
    it = store.get(sid)
    it.utility = util
    it.attention.lti = lti
    return it


def test_flag_off_by_default():
    assert rc.SPEC["composite_eviction"][2] is False
    assert eviction_cfg({}) is None and eviction_cfg(rc.resolve()) is None
    assert WMTMStore().eviction_cfg is None


def test_s12_1_composite_unit():
    """s7.1c: STI*0.4 + utility*0.4 + LTI*0.2; derived / 1.5 (s10)."""
    st = WMTMStore(capacity=10)
    st.admit("a", "a", source_type="recalled", initial_sti=2.0)
    st.admit("d", "d", source_type="derived", initial_sti=2.0)
    _set(st, "a", util=3.0, lti=1.0)
    _set(st, "d", util=3.0, lti=1.0)
    cfg = eviction_cfg(ON)
    assert composite_score(st.get("a"), cfg) == pytest.approx(0.8 + 1.2 + 0.2)
    assert composite_score(st.get("d"), cfg) == pytest.approx((0.8 + 1.2 + 0.2) / 1.5)
    c2 = eviction_cfg({**ON, "eviction_weights": "1,0,0", "derived_eviction_penalty": 2.0})
    assert composite_score(st.get("d"), c2) == pytest.approx(1.0)
    bad = eviction_cfg({**ON, "eviction_weights": "x", "derived_eviction_penalty": 0, "eviction_min_utility": "nan"})
    assert bad == {"weights": (0.4, 0.4, 0.2), "derived_penalty": 1.5, "min_utility": 2.0}


def _replay(flag_on):
    orch = WMTMOrchestrator(WMTMStore(capacity=3), use_goalchainer=False)
    st = orch.store
    st.eviction_cfg = eviction_cfg(ON) if flag_on else None
    sizes = []
    st.admit("rec_lo", "recalled low STI high utility", source_type="recalled", initial_sti=1.0)
    _set(st, "rec_lo", util=5.0); sizes.append(len(st))
    st.admit("der", "derived same values", source_type="derived", derived_from=["rec_lo"], initial_sti=1.0)
    _set(st, "der", util=5.0); sizes.append(len(st))
    st.admit("rec_hi", "recalled high STI low utility", source_type="recalled", initial_sti=5.0)
    sizes.append(len(st))
    st.admit("new", "fourth item", source_type="recalled", initial_sti=3.0)
    sizes.append(len(st))
    orch._log_capacity_evictions()
    logged = [r.item_id for r in orch.forget_log.get_records()]
    return st, logged, sizes


def test_replay_capacity3_flag_on_evicts_derived_into_forget_log():
    st, logged, sizes = _replay(True)
    assert "der" not in st and {"rec_lo", "rec_hi", "new"} <= {i.id for i in st.get_active_set()}
    assert logged == ["der"]
    assert all(n <= 3 for n in sizes) and len(st) <= st.capacity   # s12.4 capacity invariant


def test_replay_capacity3_flag_off_is_pre_m05_lowest_sti():
    st, logged, sizes = _replay(False)
    assert logged == ["rec_lo"] and "der" in st and all(n <= 3 for n in sizes)


def test_both_capacity_paths_rank_identically():
    """store.admit overflow and ForgettingPolicy._evict_over_capacity pick the same victim (flag on)."""
    def build():
        st = WMTMStore(capacity=4)
        st.eviction_cfg = eviction_cfg(ON)
        for i, (stype, sti, u, l) in enumerate([("recalled", 4.0, 0.0, 0.0), ("derived", 2.0, 2.0, 0.5),
                                                ("asserted", 1.0, 3.0, 0.0), ("recalled", 0.5, 4.0, 1.0)]):
            st.admit(f"x{i}", "t", source_type=stype, initial_sti=sti)
            _set(st, f"x{i}", util=u, lti=l)
        return st
    a = build()
    expect = min(a.get_active_set(), key=lambda it: composite_score(it, a.eviction_cfg)).id
    a.admit("y", "t", initial_sti=9.0)
    via_admit = [e.id for e in a.drain_pending_evicted()]
    b = build()
    b.capacity = 3
    via_policy = [e.id for e in ForgettingPolicy._evict_over_capacity(b)]
    assert via_admit == via_policy == [expect]


def test_user_request_item_still_goes_last_flag_on():
    st = WMTMStore(capacity=2)
    st.eviction_cfg = eviction_cfg(ON)
    st.admit("u", "request", source_type="user", initial_sti=0.0)
    st.admit("r", "recalled", initial_sti=9.0)
    _set(st, "r", util=9.0)
    st.admit("n", "new", initial_sti=1.0)
    assert "u" in st and "r" not in st


def test_s7_1b_age_review_flag_on():
    st = WMTMStore(capacity=10)
    st.eviction_cfg = eviction_cfg(ON)
    pol = ForgettingPolicy()
    for sid, u in (("keep", 3.0), ("drop", 1.0)):
        st.admit(sid, sid, initial_sti=5.0)
        it = _set(st, sid, util=u)
        it.age = pol.max_age
    ev = [e.id for e in pol._evict_aged_low_utility(st)]
    assert ev == ["drop"] and st.get("keep").age == 0


def test_s7_1b_age_review_flag_off_unchanged():
    st = WMTMStore(capacity=10)
    pol = ForgettingPolicy()
    st.admit("k", "k", initial_sti=5.0)
    it = _set(st, "k", util=1.0)          # 1.0 >= policy min_utility 0.5: kept, age not reset (pre-M-05)
    it.age = pol.max_age
    assert pol._evict_aged_low_utility(st) == [] and st.get("k").age == pol.max_age


def test_orchestrator_syncs_flag_from_runtime_config(monkeypatch):
    orch = WMTMOrchestrator(WMTMStore(capacity=5), use_goalchainer=False)
    orch.forget_phase()
    assert orch.store.eviction_cfg is None
    monkeypatch.setenv("WMTM_COMPOSITE_EVICTION", "1")
    orch.forget_phase()
    assert orch.store.eviction_cfg is not None and orch.store.eviction_cfg["derived_penalty"] == 1.5
