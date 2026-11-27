"""M-07 (t-2026-11-26-wmtm-m07-forgetting-log): pruning the forgetting-log window must not end forgotten status.

A derivation pruned from the window is still forgotten: it is re-admitted only through should_re_admit's STI test.
The window is capped on load (from_dict), a prune is O(1), and old saved logs load unchanged."""
import json
from wmtm.forgetting_log import ForgettingLog, content_hash, deriv_hash
from wmtm.store import WMTMStore
from wmtm.orchestrator import WMTMOrchestrator
from wmtm.candidate import InferenceCandidate
from wmtm import runtime_config as rc


def _derived_item(i, srcs=None):
    st = WMTMStore(capacity=10)
    it = st.admit("d%d" % i, "conclusion %d" % i, source_type="derived", initial_sti=1.0)
    it.derived_from = list(srcs if srcs is not None else ["s%d" % i, "t%d" % i])
    return it


def _replay(cap, n):
    log = ForgettingLog(max_records=cap)
    for i in range(n):
        log.record(_derived_item(i), tick=i)
    return log


def test_synthetic_replay_cap3_five_records_pruned_stay_forgotten():
    log = _replay(3, 5)
    assert len(log) == 3 and [r.item_id for r in log.get_records()] == ["d2", "d3", "d4"]
    for i in range(5):     # d0, d1 were pruned from the window, still forgotten
        assert log.is_forgotten("conclusion %d" % i, ["s%d" % i, "t%d" % i]), i
    assert log.is_pruned_only("conclusion 0", ["s0", "t0"]) and not log.is_pruned_only("conclusion 4", ["s4", "t4"])
    assert not log.is_forgotten("conclusion 0", ["other"])     # F1 §4: other sources = a new derivation


def test_round_trip_save5_load_cap2():
    d = _replay(10, 5).to_dict()
    d = json.loads(json.dumps(d))
    log = ForgettingLog.from_dict(d, max_records=2)
    assert len(log) == 2 and log.max_records == 2
    assert [r.item_id for r in log.get_records()] == ["d3", "d4"]
    for i in range(5):
        assert log.is_forgotten("conclusion %d" % i, ["s%d" % i, "t%d" % i]), i
    log2 = ForgettingLog.from_dict(json.loads(json.dumps(log.to_dict())))     # the cap and the filter persist
    assert log2.max_records == 2 and all(log2.is_forgotten("conclusion %d" % i, ["s%d" % i, "t%d" % i]) for i in range(5))


def test_from_dict_saved_cap_applied_without_argument():
    d = _replay(10, 5).to_dict()
    d["max_records"] = 2
    assert len(ForgettingLog.from_dict(d)) == 2


def _orch():
    o = WMTMOrchestrator(WMTMStore(capacity=50), use_goalchainer=False, use_pln=False)
    o.forget_log = _replay(3, 5)      # d0 pruned from the window
    return o


def _cand(sti):
    return InferenceCandidate(content="conclusion 0", confidence=0.9, derived_from=["s0", "t0"],
                              inference_type="pc_deduction", initial_sti=sti)


def test_pruned_rederived_low_sti_refused():
    o = _orch()
    assert o._is_skipworthy(_cand(1.0)) is True
    assert o.forget_log.should_re_admit("conclusion 0", 5.0, 1.0, derived_from=["s0", "t0"]) is False


def test_pruned_rederived_high_sti_admitted():
    o = _orch()
    assert o._is_skipworthy(_cand(o.forget_log_override_threshold)) is False
    assert o.forget_log.should_re_admit("conclusion 0", 5.0, 5.0, derived_from=["s0", "t0"]) is True


def test_prune_is_o1_refcounts():
    log = ForgettingLog(max_records=2)
    for i in range(3):       # the same derivation three times: refcount keeps it in the window
        log.record(_derived_item(0), tick=i)
    assert len(log) == 2 and log._derivs[deriv_hash("conclusion 0", ["s0", "t0"])] == 2
    assert log.is_id_forgotten("d0")


def test_recalled_prunes_do_not_fill_filter():
    log = ForgettingLog(max_records=2)
    st = WMTMStore(capacity=10)
    for i in range(5):
        log.record(st.admit("r%d" % i, "recalled %d" % i, initial_sti=1.0), tick=i)
    assert log.pruned_total == 3 and "pruned" not in log.to_dict()


def test_old_saved_log_loads_and_saves_like_before():
    old = {"max_records": 500, "records": [{"item_id": "d1", "content_hash": content_hash("x"), "source_type": "derived",
           "evicted_at_tick": 3, "age_at_eviction": 1, "final_utility": 0.0, "final_sti": 0.2, "derived_from": ["a"]}]}
    log = ForgettingLog.from_dict(old)
    assert log.is_forgotten("x", ["a"]) and log.get_records()[0].final_confidence is None
    assert log.to_dict() == old           # no new keys until a prune / a known confidence


def test_final_confidence_recorded_from_stv():
    it = _derived_item(0)
    it.provenance = {"stv": [0.8, 0.35]}
    log = ForgettingLog()
    assert log.record(it, 1).final_confidence == 0.35
    assert ForgettingLog.from_dict(log.to_dict()).get_records()[0].final_confidence == 0.35


def test_runtime_config_key_default_500():
    assert rc.SPEC["forgetting_log_max"][2] == 500 and rc.resolve(None, environ={}).get("forgetting_log_max") == 500
