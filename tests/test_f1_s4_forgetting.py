"""F1 section 4 (t-2026-11-06-wmtm-f1-memory), acceptance condition 4, each test with its negative control.

(a) the forgetting log is keyed on the derivation (conclusion + sorted sources), not the sentence;
(b) a conclusion's starting STI comes from request relevance, not s*c, so a low-confidence conclusion is not evicted
    in the cycle that admits it."""
import json, time
from wmtm import pc_admit, pc_shadow
from wmtm.forgetting_log import ForgettingLog, content_hash, deriv_hash
from wmtm.store import WMTMStore
from wmtm.orchestrator import WMTMOrchestrator

SYN = ["cat is a mammal", "mammal is a animal", "rain -> wet", "wet -> slippery"]
LOWC = {"goal": "(Inheritance cat animal)", "stv": [0.9, 0.05], "proof": "(inh_trans sp0 sp1)", "s": 0.3,
        "sources": ["s0", "s1"]}                     # s*c = 0.045 < derived_sti_threshold 0.10


def _store():
    st = WMTMStore()
    for i, t in enumerate(SYN):
        st.admit("s%d" % i, t, source_type="recalled", initial_sti=1.0 - i * 0.01)
    return st


def _orch(tmp_path, monkeypatch):
    monkeypatch.setenv("WMTM_REASONER", "pettachainer")
    monkeypatch.setenv("WMTM_PC_SHADOW_DIR", str(tmp_path))
    monkeypatch.delenv("WMTM_PC_SHADOW", raising=False)
    monkeypatch.setattr(pc_shadow, "maybe_launch", lambda *a, **k: None)
    o = WMTMOrchestrator(_store(), use_goalchainer=False)
    o.runtime_state_dir = str(tmp_path)
    return o


def _doc(tmp_path, results):
    (tmp_path / pc_admit.ADMIT_FILE).write_text(json.dumps(
        {"ts": time.time(), "spec_ts": time.time(), "cycle": 0, "status": "ok", "canary_ok": True, "results": results}))


def _derived(o):
    return {it.content: it for it in o.store.get_active_set() if it.id.startswith("derived-pc_")}


# ---------------------------------------------------------------- (a) derivation key
def _forgot(content, srcs):
    st = WMTMStore()
    log = ForgettingLog()
    log.record(st.admit("d1", content, source_type="derived", derived_from=srcs), tick=1)
    return log


def test_new_derivation_of_forgotten_conclusion_is_not_forgotten():
    log = _forgot("cat is a animal", ["s0", "s1"])
    assert log.is_forgotten("cat is a animal", ["s2", "s3"]) is False


def test_control_same_derivation_is_forgotten_any_source_order():
    log = _forgot("cat is a animal", ["s0", "s1"])
    assert log.is_forgotten("cat is a animal", ["s1", "s0"]) is True
    assert log.is_forgotten("Cat is a animal ", ["s0", "s1"]) is True
    assert log.is_forgotten("cat is a animal") is True          # sentence-only call keeps its old meaning


def test_derivation_key_survives_roundtrip_without_format_change():
    log = _forgot("cat is a animal", ["s1", "s0"])
    d = log.to_dict()
    assert "deriv_hash" not in d["records"][0]                  # persisted state format unchanged
    back = ForgettingLog.from_dict(d)
    assert back.is_forgotten("cat is a animal", ["s0", "s1"]) and not back.is_forgotten("cat is a animal", ["s9"])
    assert deriv_hash("cat is a animal", ["s0", "s1"]) == deriv_hash("", ["s1", "s0"], content_hash("cat is a animal"))


def test_cycle_readmits_forgotten_conclusion_from_new_sources(tmp_path, monkeypatch):
    o = _orch(tmp_path, monkeypatch)
    o.forget_log.record(o.store.admit("old", "cat is a animal", source_type="derived", derived_from=["s2", "s3"]), 0)
    o.store.evict("old")
    _doc(tmp_path, [dict(LOWC, stv=[0.9, 0.6])])
    o.cycle()
    assert "cat is a animal" in _derived(o)


def test_control_cycle_skips_forgotten_same_derivation(tmp_path, monkeypatch):
    o = _orch(tmp_path, monkeypatch)
    o.forget_log.record(o.store.admit("old", "cat is a animal", source_type="derived", derived_from=["s1", "s0"]), 0)
    o.store.evict("old")
    _doc(tmp_path, [dict(LOWC, stv=[0.9, 0.6])])
    r = o.cycle()
    assert "cat is a animal" not in _derived(o) and r.reasoner_info["dropped"]["known"] == 1


# ---------------------------------------------------------------- (b) starting STI from relevance
def test_low_confidence_conclusion_survives_admitting_cycle(tmp_path, monkeypatch):
    o = _orch(tmp_path, monkeypatch)
    _doc(tmp_path, [LOWC])
    r = o.cycle()
    d = _derived(o)
    assert r.pc_admitted == 1 and "cat is a animal" in d
    assert d["cat is a animal"].attention.sti > o.forgetting.derived_sti_threshold


def test_control_s_times_c_sti_is_evicted_in_admitting_cycle(tmp_path, monkeypatch):
    # negative control: the old rule (initial STI = s*c = 0.045) loses the conclusion in the cycle that admits it
    monkeypatch.setattr(pc_admit, "initial_sti", lambda text, rel, cfg: 0.9 * 0.05)
    o = _orch(tmp_path, monkeypatch)
    _doc(tmp_path, [LOWC])
    r = o.cycle()
    assert r.pc_admitted == 1 and "cat is a animal" not in _derived(o)


def test_relevant_conclusion_starts_higher():
    rel = {"terms": {"cat": 2.0, "animal": 1.0}, "smax": 3.0}
    assert pc_admit.initial_sti("cat is a animal", rel, {}) == 5.0
    assert pc_admit.initial_sti("rain implies slippery", rel, {}) == 1.0


def test_control_no_request_all_equal_base():
    assert pc_admit.initial_sti("cat is a animal", None, {}) == pc_admit.initial_sti("rain implies slippery", None, {}) == 1.0
