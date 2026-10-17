"""Track I/K: reasoner switch (python | pettachainer; Track K: no "both", no Python fallback).  Mocked/synthetic; integration skips without vendored PeTTa."""
import json, os, time
import pytest
from wmtm import pc_admit, pc_shadow, runtime_config as rc
from wmtm.store import WMTMStore
from wmtm.orchestrator import WMTMOrchestrator

SYN = ["cat is a mammal", "mammal is a animal", "rain -> wet", "wet -> slippery"]
_CFG = rc.resolve()
HAVE_PC = os.path.isdir(os.path.join(_CFG["petta_dir"], "python")) and os.path.isdir(os.path.join(_CFG["pettachainer_dir"], "pettachainer"))


def _store(texts=SYN):
    st = WMTMStore()
    for i, t in enumerate(texts):
        st.admit("s%d" % i, t, source_type="recalled", initial_sti=1.0 - i * 0.01)
    return st


def _orch(tmp_path, mode, monkeypatch, launches=None):
    monkeypatch.setenv("WMTM_REASONER", mode)
    monkeypatch.setenv("WMTM_PC_SHADOW_DIR", str(tmp_path))
    monkeypatch.delenv("WMTM_PC_SHADOW", raising=False)
    monkeypatch.setattr(pc_shadow, "maybe_launch", lambda *a, **k: (launches.append(k) if launches is not None else None))
    o = WMTMOrchestrator(_store(), use_goalchainer=False)
    o.runtime_state_dir = str(tmp_path)
    return o


def _admit_doc(tmp_path, results, status="ok", canary_ok=True, age=0.0):
    doc = {"ts": time.time() - age, "spec_ts": time.time() - age, "cycle": 0, "status": status, "canary_ok": canary_ok,
           "results": results}
    (tmp_path / pc_admit.ADMIT_FILE).write_text(json.dumps(doc))


R_CAT = {"goal": "(Inheritance cat animal)", "stv": [0.9, 0.6], "proof": "(inh_trans sp0 sp1)", "s": 0.3, "sources": ["s0", "s1"]}
R_RAIN = {"goal": "(Implies rain slippery)", "stv": [0.8, 0.5], "proof": "(imp_trans sp2 sp3)", "s": 0.2, "sources": ["s2", "s3"]}


def _derived(o):
    return {it.content: it for it in o.store.get_active_set()
            if it.source_type == "derived" and it.id.startswith(("derived-pln_", "derived-pc_"))}


# ------------------------------------------------------------------ flag
def test_mode_parsing():
    assert pc_admit.mode({}) == "python" and pc_admit.mode({"reasoner": "PettaChainer"}) == "pettachainer"
    assert pc_admit.mode({"reasoner": "both"}) == "python" and pc_admit.mode({"reasoner": "junk"}) == "python"   # Track K: "both" removed
    assert pc_admit.mode({"reasoner": ""}, default="pettachainer") == "pettachainer"


def test_runtime_config_reasoner(tmp_path):
    (tmp_path / rc.FLAGS_FILENAME).write_text(json.dumps({"reasoner": "pettachainer"}))
    assert rc.resolve(str(tmp_path), environ={})["reasoner"] == "pettachainer"
    (tmp_path / rc.FLAGS_FILENAME).write_text(json.dumps({"reasoner": "both"}))
    assert rc.resolve(str(tmp_path), environ={})["reasoner"] == "python"     # Track K: "both" is invalid
    (tmp_path / rc.FLAGS_FILENAME).write_text(json.dumps({"reasoner": "nope"}))
    cfg = rc.resolve(str(tmp_path), environ={})
    assert cfg["reasoner"] == "python" and "reasoner" in cfg["_source"]["invalid"]
    assert rc.resolve(None, environ={})["reasoner"] == ""          # unset -> API default


# ------------------------------------------------------------------ admission
def test_python_mode_unchanged_ignores_admit_file(tmp_path, monkeypatch):
    launches = []
    o = _orch(tmp_path, "python", monkeypatch, launches)
    _admit_doc(tmp_path, [dict(R_CAT, goal="(Inheritance cat robot)")])
    r = o.cycle()
    d = _derived(o)
    assert r.reasoner == "python" and r.pc_admitted == 0 and "cat is a robot" not in d
    # Python PLN items were admitted (they may be evicted the same cycle by contradiction resolution + tick)
    assert r.pln_admitted > 0 and all(it.provenance is None for it in d.values()) and launches == []


def test_pettachainer_mode_admits_with_provenance_and_replaces_python(tmp_path, monkeypatch):
    launches = []
    o = _orch(tmp_path, "pettachainer", monkeypatch, launches)
    _admit_doc(tmp_path, [R_CAT, R_RAIN])
    r = o.cycle()
    d = _derived(o)
    assert r.reasoner == "pettachainer" and not r.reasoner_skipped and r.pc_admitted == 2
    assert set(d) == {"cat is a animal", "rain implies slippery"}      # no Python PLN items
    it = d["cat is a animal"]
    assert it.provenance["reasoner"] == "pettachainer" and it.provenance["stv"] == [0.9, 0.6]
    assert it.provenance["proof"] == "(inh_trans sp0 sp1)" and it.derived_from == ["s0", "s1"]
    assert abs(it.attention.sti - 0.54) < 1e-6 or it.attention.sti <= 0.54   # initial STI = s*c (then decay)
    assert launches and launches[0].get("force") is True              # worker launched although pc_shadow off


def test_provenance_survives_snapshot_roundtrip(tmp_path, monkeypatch):
    o = _orch(tmp_path, "pettachainer", monkeypatch)
    _admit_doc(tmp_path, [R_CAT]); o.cycle()
    o2 = WMTMOrchestrator(WMTMStore(), use_goalchainer=False)
    o2.restore_state(json.loads(json.dumps(o.snapshot_state())))
    assert _derived(o2)["cat is a animal"].provenance["proof"] == "(inh_trans sp0 sp1)"


def test_admission_filters(tmp_path):
    rows = [dict(R_CAT, sources=["gone"]),                                          # source evicted
            dict(R_RAIN, stv=[0.05, 0.9]),                                         # below threshold
            {"goal": "(Inheritance a b)", "stv": [0.9, 0.9], "proof": "", "sources": ["s0"]},  # no proof term
            {"goal": "garbage", "stv": [0.9, 0.9], "proof": "(inh_trans p)", "sources": ["s0"]},
            {"goal": "(Inheritance a b)", "stv": "x", "proof": "(inh_trans p)", "sources": ["s0"]}]
    _admit_doc(tmp_path, rows)
    cands, info = pc_admit.load_candidates({"shadow_dir": str(tmp_path)}, _store())
    assert cands == [] and info["dropped"] == {"asserted": 0, "no_live_source": 1, "below_threshold": 1, "bad": 3, "known": 0, "per_fact_cap": 0}


def test_max_admit_cap(tmp_path):
    rows = [{"goal": "(Inheritance a%d b)" % i, "stv": [0.9, 0.5], "proof": "(inh_trans sp%d)" % i, "sources": ["s0"]} for i in range(50)]
    _admit_doc(tmp_path, rows)
    cands, info = pc_admit.load_candidates({"shadow_dir": str(tmp_path), "reasoner_max_admit": 7}, _store())
    assert len(cands) == 7 and info["candidates"] == 7


# ------------------------------------------------------------------ worker side
def test_write_admit_file_only_admissible():
    import tempfile
    spec = {"ts": 1.0, "cycle": 3, "atom_src": {"sp0": "s0", "sp1": "s1"}, "fact_src": [["Inheritance", "q", "r", "s9"]]}
    good = {"goal": "(Inheritance cat animal)", "ok": True, "timeout": False, "stv": [0.9, 0.6], "proof": "(inh_trans sp0 sp1)", "s": 0.1}
    rec = {"status": "ok", "canary": {"ok": True}, "neg": {"ok": False, "timeout": False}, "queries": [
        good,
        dict(good, goal="(Inheritance q r2)", proof="(x)"),                       # no labels -> fact_src fallback
        dict(good, goal="(Inheritance t1 t2)", timeout=True, ok=False),          # timed out
        dict(good, goal="(Inheritance t3 t4)", structural_fail=True),
        dict(good, goal="(Inheritance t5 t6)", proof=""),                       # no proof term
        dict(good, goal="(Inheritance t7 t8)", stv=None)]}
    with tempfile.TemporaryDirectory() as d:
        doc = pc_admit.write_admit_file(d, rec, spec)
        assert [r["goal"] for r in doc["results"]] == ["(Inheritance cat animal)", "(Inheritance q r2)"]
        assert doc["results"][0]["sources"] == ["s0", "s1"] and doc["results"][1]["sources"] == ["s9"]
        assert "py_invalid_chain" not in doc and doc["spec_ts"] == 1.0
        for bad in ({"status": "canary_fail"}, {"neg": {"ok": True}}, {"neg": {"ok": False, "timeout": True}}):
            assert pc_admit.write_admit_file(d, dict(rec, **bad), spec)["results"] == []


def test_snapshot_records_provenance_labels(monkeypatch):
    import _fake_semparse; _fake_semparse.install(monkeypatch)
    spec = pc_shadow.build_snapshot(_store(), cycle=1, k=200)
    assert spec["atom_src"] and set(spec["atom_src"].values()) <= {"s0", "s1", "s2", "s3"}
    assert ["Inheritance", "cat", "mammal", "s0"] in spec["fact_src"]


# ------------------------------------------------------------------ faults: Track K - admit nothing, cycle unaffected
@pytest.mark.parametrize("setup,why", [
    (lambda p: None, "no_admit_file"),                                              # worker never ran / dead
    (lambda p: (p / pc_admit.ADMIT_FILE).write_text("{not json"), "bad_admit_file"),
    (lambda p: _admit_doc(p, [R_CAT], age=5000), "stale"),                          # worker died long ago
    (lambda p: _admit_doc(p, [R_CAT], status="canary_fail", canary_ok=False), "run_canary_fail"),
    (lambda p: _admit_doc(p, [R_CAT], status="warm_fail", canary_ok=False), "run_warm_fail"),
])
def test_fault_pettachainer_admits_nothing_no_python_fallback(tmp_path, monkeypatch, setup, why):
    o = _orch(tmp_path, "pettachainer", monkeypatch); setup(tmp_path)
    r = o.cycle()
    assert r.reasoner_skipped and r.reasoner_info["skipped"] == why and r.pc_admitted == 0
    assert _derived(o) == {} and r.pln_admitted == 0 and r.active_count > 0      # nothing derived, cycle ran


def base_pln(o):
    return sum(1 for it in o.store.get_active_set() if it.source_type == "derived")


def test_fault_loader_raises_cycle_unaffected(tmp_path, monkeypatch):
    o = _orch(tmp_path, "pettachainer", monkeypatch)
    def boom(*a, **k): raise RuntimeError("x")
    monkeypatch.setattr(pc_admit, "load_candidates", boom)
    r = o.cycle()
    assert r.reasoner_skipped and r.reasoner_info["skipped"] == "error:RuntimeError" and r.pln_admitted == 0


def test_fault_launch_raises_cycle_unaffected(tmp_path, monkeypatch):
    o = _orch(tmp_path, "pettachainer", monkeypatch)
    def boom(*a, **k): raise RuntimeError("x")
    monkeypatch.setattr(pc_shadow, "maybe_launch", boom)
    _admit_doc(tmp_path, [R_CAT])
    r = o.cycle()
    assert r.pc_admitted == 1 and r.active_count > 0


def test_fault_dead_worker_pidfile_does_not_block(tmp_path, monkeypatch):
    (tmp_path / "worker.pid").write_text("999999")                                  # no such process
    assert not rc.busy(str(tmp_path / "worker.pid"))
    o = _orch(tmp_path, "pettachainer", monkeypatch)
    t = time.time(); r = o.cycle()
    assert time.time() - t < 2 and r.reasoner_skipped


# ------------------------------------------------------------------ integration (real PeTTaChainer)
@pytest.mark.skipif(not HAVE_PC, reason="vendored PeTTa v1.0.6 / PeTTaChainer not present")
def test_integration_worker_writes_admit_file_and_cycle_admits(tmp_path, monkeypatch):
    import subprocess, sys
    import _fake_semparse; _fake_semparse.install(monkeypatch)
    spec = pc_shadow.build_snapshot(_store(), cycle=1)
    sp = tmp_path / "spec.json"; sp.write_text(json.dumps(spec))
    p = subprocess.run([sys.executable, "-m", "wmtm.workers.pc_shadow", "--spec", str(sp), "--out", str(tmp_path / "shadow.jsonl")],
                       cwd=rc.DIST_ROOT, env=rc.worker_env(_CFG), timeout=120)
    assert p.returncode == 0
    doc = json.loads((tmp_path / pc_admit.ADMIT_FILE).read_text())
    assert doc["status"] == "ok" and doc["canary_ok"]
    goals = {r["goal"]: r for r in doc["results"]}
    assert {"(Inheritance cat animal)", "(Implies rain slippery)"} <= set(goals)
    assert set(goals["(Inheritance cat animal)"]["sources"]) == {"s0", "s1"}
    o = _orch(tmp_path, "pettachainer", monkeypatch)
    r = o.cycle()
    assert not r.reasoner_skipped and {"cat is a animal", "rain implies slippery"} <= set(_derived(o))


def test_fact_or_revision_proof_not_admitted(tmp_path):
    rows = [dict(R_CAT, proof="(: sp504 (Inheritance cat animal) (STV 0.9 0.9))"),
            dict(R_RAIN, proof="(: (merge/revision sp1 sp2) (Implies rain slippery) (STV 1 0.99))")]
    _admit_doc(tmp_path, rows)
    cands, info = pc_admit.load_candidates({"shadow_dir": str(tmp_path)}, _store())
    assert cands == [] and info["dropped"]["asserted"] == 2


# ------------------------------------------------------------------ v0.4: journal writeback of admitted conclusions
def _aged_for_writeback(o):
    for it in o.store.get_active_set():
        it.age = 100; it.utility = 10.0
        it.attention.sti = max(it.attention.sti, 5.0)


@pytest.mark.parametrize("flag,expect_pc", [(None, False), (False, False), (True, True)])
def test_reasoner_writeback_flag(tmp_path, monkeypatch, flag, expect_pc):
    """Default: PeTTaChainer conclusions stay in working memory (not appended to the journal)."""
    monkeypatch.delenv("WMTM_REASONER_WRITEBACK", raising=False)
    if flag is not None:
        (tmp_path / rc.FLAGS_FILENAME).write_text(json.dumps({"reasoner_writeback": flag}))
    assert rc.resolve(str(tmp_path), environ={})["reasoner_writeback"] is bool(flag)
    o = _orch(tmp_path, "pettachainer", monkeypatch)
    _admit_doc(tmp_path, [R_CAT])
    o.cycle()
    pc = _derived(o)["cat is a animal"]
    o.store.admit("tool-1", "a tool-derived note", source_type="derived", derived_from=["s0"], initial_sti=20.0)
    _aged_for_writeback(o)
    notes = []
    from wmtm.orchestrator import CycleResult
    res = CycleResult(cycle=1)
    o._do_writeback(lambda n: notes.append(n), res, rc.resolve(str(tmp_path), environ={}))
    wrote_pc = any(("wmtm-derived-" + pc.id) in n for n in notes)
    assert wrote_pc is expect_pc
    assert any("wmtm-derived-tool-1" in n for n in notes)          # other derived items unaffected
    assert any("wmtm-enrich-s0" in n for n in notes)               # recalled enrichment unaffected


def test_cycle_does_not_write_back_pc_conclusion_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("WMTM_REASONER_WRITEBACK", raising=False)
    o = _orch(tmp_path, "pettachainer", monkeypatch)
    _admit_doc(tmp_path, [R_CAT])
    o.cycle()
    assert "cat is a animal" in _derived(o)
    _aged_for_writeback(o)
    notes = []
    o.cycle(append_fn=lambda n: notes.append(n))
    assert notes and not any("DerivedBelief" in n and "cat is a animal" in n for n in notes)
