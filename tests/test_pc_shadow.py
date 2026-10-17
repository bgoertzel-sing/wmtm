"""Track G: PeTTaChainer shadow.  Unit tests are mocked (no PeTTa); integration tests skip without vendored PeTTa."""
import json, os, subprocess, sys, time
import pytest
from wmtm import pc_shadow, runtime_config as rc
from wmtm.store import WMTMStore

# Integration tests need the vendored runtime (scripts/vendor_runtime.sh); point WMTM_PC_PETTA / WMTM_PC_VENDOR
# (and WMTM_SWIPL_BIN if swipl is not on PATH) at it, or vendor it next to the package (runtime_config defaults).
_CFG = rc.resolve()
HAVE_PC = os.path.isdir(os.path.join(_CFG["petta_dir"], "python")) and os.path.isdir(os.path.join(_CFG["pettachainer_dir"], "pettachainer"))


def _store(texts):
    st = WMTMStore()
    for i, t in enumerate(texts):
        st.admit("s%d" % i, t, source_type="recalled", initial_sti=1.0 - i * 0.01)
    return st


SYN = ["cat is a mammal", "mammal is a animal", "rain -> wet", "wet -> slippery"]


@pytest.fixture(autouse=True)
def _semparse(monkeypatch):
    import _fake_semparse; _fake_semparse.install(monkeypatch)   # Track K: reasoner reads semparse atoms only


def test_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("WMTM_PC_SHADOW", raising=False)
    called = []
    monkeypatch.setattr(pc_shadow, "launch", lambda *a, **k: called.append(1))
    assert pc_shadow.maybe_launch(_store(SYN), 1) is None and not called
    assert pc_shadow.maybe_launch(_store(SYN), 1, state_dir=str(tmp_path)) is None and not called   # no flags file


def test_snapshot_maps_atoms_and_goals():
    spec = pc_shadow.build_snapshot(_store(SYN), cycle=7, k=200)
    assert spec["cycle"] == 7 and spec["items"] == 4
    joined = " ".join(spec["atoms"])
    assert "(Inheritance cat mammal)" in joined and "(Implies rain wet)" in joined
    assert "(Implication " not in joined            # facts must not look like rules
    assert "(Inheritance cat animal)" in spec["goals"] and "(Implies rain slippery)" in spec["goals"]
    assert spec["semparse_items"] == 4 and spec["unparsed_items"] == 0 and "python_derived" not in spec


def test_snapshot_unparsed_items_add_no_facts():
    spec = pc_shadow.build_snapshot(_store(SYN + ["the weather looks odd today"]), cycle=1, k=200)
    assert spec["semparse_items"] == 4 and spec["unparsed_items"] == 1 and spec["facts"] == 4


def test_snapshot_topk_limits_items():
    spec = pc_shadow.build_snapshot(_store(SYN), k=2)
    assert spec["items"] == 2 and "(Implies rain slippery)" not in spec["goals"]


def test_maybe_launch_swallows_errors(monkeypatch):
    monkeypatch.setenv("WMTM_PC_SHADOW", "1")
    def boom(*a, **k): raise RuntimeError("x")
    monkeypatch.setattr(pc_shadow, "launch", boom)
    assert pc_shadow.maybe_launch(_store(SYN), 1) is None


def test_maybe_launch_is_raw_only_and_worker_builds(monkeypatch, tmp_path):
    """Cycle side ships raw top-K fields only; snapshot_from_raw (worker side) rebuilds the same goals."""
    monkeypatch.setenv("WMTM_PC_SHADOW", "1"); monkeypatch.setenv("WMTM_RUNTIME_DIR", str(tmp_path))
    got = []
    monkeypatch.setattr(pc_shadow, "launch", lambda spec, *a, **k: got.append(spec) or 123)
    assert pc_shadow.maybe_launch(_store(SYN), 5) == 123
    spec = got[0]
    assert spec["atoms"] == [] and len(spec["raw_items"]) == 4 and spec["cycle"] == 5
    full = pc_shadow.snapshot_from_raw(spec)
    assert full["goals"] == pc_shadow.build_snapshot(_store(SYN), cycle=5)["goals"] and "build_s" in full


def test_launch_never_waits_and_busy_guard(tmp_path, monkeypatch):
    mod = tmp_path / "slowmod"; mod.mkdir(); (mod / "__init__.py").write_text("")
    (mod / "slow.py").write_text("import time; time.sleep(5)\n")
    cfg = rc.resolve(str(tmp_path))
    env0 = rc.worker_env
    monkeypatch.setattr(rc, "worker_env", lambda c, base=None: dict(env0(c, base), PYTHONPATH=str(tmp_path)))
    t = time.time(); pid = pc_shadow.launch({"cycle": 1, "atoms": ["x"]}, cfg, out_dir=str(tmp_path), module="slowmod.slow")
    assert pid and time.time() - t < 1.0                     # detached: returns immediately
    assert pc_shadow.launch({"cycle": 2, "atoms": ["x"]}, cfg, out_dir=str(tmp_path), module="slowmod.slow") is None  # busy
    os.killpg(os.getpgid(pid), 9)
    assert json.load(open(tmp_path / "worker_config.json"))["shadow_dir"] == str(tmp_path)


def test_orchestrator_cycle_unaffected_when_shadow_raises(monkeypatch):
    from wmtm import orchestrator as orch
    monkeypatch.setenv("WMTM_PC_SHADOW", "1")
    def boom(*a, **k): raise RuntimeError("shadow exploded")
    monkeypatch.setattr(pc_shadow, "maybe_launch", boom)
    o = orch.WMTMOrchestrator(_store(SYN), use_goalchainer=False) if "use_goalchainer" in orch.WMTMOrchestrator.__init__.__code__.co_varnames else orch.WMTMOrchestrator(_store(SYN))
    r = o.cycle()
    assert r is not None


def _run_worker(tmp_path, spec, *extra):
    sp = tmp_path / "spec.json"; sp.write_text(json.dumps(spec)); out = tmp_path / "shadow.jsonl"
    code = subprocess.run([sys.executable, "-m", "wmtm.workers.pc_shadow", "--spec", str(sp), "--out", str(out)] + list(extra),
                          env=rc.worker_env(_CFG), cwd=rc.DIST_ROOT, timeout=120).returncode
    return code, json.loads(out.read_text().strip().splitlines()[-1]), sp


@pytest.mark.skipif(not HAVE_PC, reason="vendored PeTTa v1.0.6 / PeTTaChainer not present")
def test_integration_synthetic(tmp_path):
    spec = pc_shadow.build_snapshot(_store(SYN), cycle=1)
    rc, rec, sp = _run_worker(tmp_path, spec)
    assert rc == 0 and rec["status"] == "ok" and rec["canary"]["ok"] and not rec["neg"]["ok"]
    assert rec["petta"].startswith(_CFG["petta_dir"]) and rec["mem_cap_mb"] == _CFG["worker_mem_mb"]
    proved = {q["goal"] for q in rec["queries"] if q["ok"]}
    assert {"(Inheritance cat animal)", "(Implies rain slippery)"} <= proved
    assert not sp.exists()                                    # spec deleted


@pytest.mark.skipif(not HAVE_PC, reason="vendored PeTTa v1.0.6 / PeTTaChainer not present")
def test_fault_timeout_is_canary_fail_not_hang(tmp_path):
    spec = pc_shadow.build_snapshot(_store(SYN), cycle=1)
    t = time.time(); rc, rec, _ = _run_worker(tmp_path, spec, "--timeout", "0.0001")
    assert rc == 3 and rec["status"] == "canary_fail" and rec["queries"] == [] and time.time() - t < 60


@pytest.mark.skipif(not HAVE_PC, reason="vendored PeTTa v1.0.6 / PeTTaChainer not present")
def test_fault_bad_vendor_is_warm_fail(tmp_path):
    spec = pc_shadow.build_snapshot(_store(SYN), cycle=1)
    rc, rec, _ = _run_worker(tmp_path, spec, "--vendor", str(tmp_path / "nope"), "--warm-timeout", "20")
    assert rc == 3 and rec["status"] == "warm_fail"
