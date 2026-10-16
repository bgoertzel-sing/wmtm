"""Track G: PeTTaChainer shadow.  Unit tests are mocked (no PeTTa); integration tests skip without vendored PeTTa."""
import json, os, subprocess, sys, time
import pytest
from wmtm import pc_shadow
from wmtm.store import WMTMStore
from wmtm.item import WMTMItem
from wmtm.attention import AttentionValue

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKER = os.path.join(W, "scripts", "pettachainer", "pc_shadow_worker.py")
HAVE_PC = os.path.isdir(os.path.join(W, ".vendor-petta106", "python")) and os.path.isdir(os.path.join(W, ".vendor36", "pettachainer"))


def _store(texts):
    st = WMTMStore()
    for i, t in enumerate(texts):
        st.admit("s%d" % i, t, source_type="recalled", initial_sti=1.0 - i * 0.01)
    return st


SYN = ["cat is a mammal", "mammal is a animal", "rain -> wet", "wet -> slippery"]


def test_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("WMTM_PC_SHADOW", raising=False)
    called = []
    monkeypatch.setattr(pc_shadow, "launch", lambda *a, **k: called.append(1))
    assert pc_shadow.maybe_launch(_store(SYN), 1) is None and not called


def test_snapshot_maps_atoms_and_goals():
    spec = pc_shadow.build_snapshot(_store(SYN), cycle=7, k=200)
    assert spec["cycle"] == 7 and spec["items"] == 4
    joined = " ".join(spec["atoms"])
    assert "(Inheritance cat mammal)" in joined and "(Implies rain wet)" in joined
    assert "(Implication " not in joined            # facts must not look like rules
    assert "(Inheritance cat animal)" in spec["goals"] and "(Implies rain slippery)" in spec["goals"]
    assert any(d.get("goal") == "(Inheritance cat animal)" for d in spec["python_derived"])


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
    monkeypatch.setenv("WMTM_PC_SHADOW", "1"); monkeypatch.setattr(pc_shadow, "OUT", str(tmp_path))
    got = []
    monkeypatch.setattr(pc_shadow, "launch", lambda spec, *a, **k: got.append(spec) or 123)
    assert pc_shadow.maybe_launch(_store(SYN), 5) == 123
    spec = got[0]
    assert spec["atoms"] == [] and len(spec["raw_items"]) == 4 and spec["cycle"] == 5
    full = pc_shadow.snapshot_from_raw(spec)
    assert full["goals"] == pc_shadow.build_snapshot(_store(SYN), cycle=5)["goals"] and "build_s" in full


def test_launch_never_waits_and_busy_guard(tmp_path):
    slow = tmp_path / "slow.py"; slow.write_text("import time; time.sleep(5)\n")
    t = time.time(); pid = pc_shadow.launch({"cycle": 1, "atoms": ["x"]}, out_dir=str(tmp_path), worker=str(slow))
    assert pid and time.time() - t < 1.0                     # detached: returns immediately
    assert pc_shadow.launch({"cycle": 2, "atoms": ["x"]}, out_dir=str(tmp_path), worker=str(slow)) is None  # busy -> skip
    os.killpg(os.getpgid(pid), 9)


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
    env = dict(os.environ)
    sw = "/home/openclaw/research-agent/projects/petta-memory/toolchains/local/swi-prolog-9.3.36/lib/swipl/bin/x86_64-linux"
    if os.path.isdir(sw): env["PATH"] = sw + ":" + env.get("PATH", "")
    rc = subprocess.run([sys.executable, WORKER, "--spec", str(sp), "--out", str(out)] + list(extra), env=env, timeout=120).returncode
    return rc, json.loads(out.read_text().strip().splitlines()[-1]), sp


@pytest.mark.skipif(not HAVE_PC, reason="vendored PeTTa v1.0.6 / PeTTaChainer not present")
def test_integration_synthetic(tmp_path):
    spec = pc_shadow.build_snapshot(_store(SYN), cycle=1)
    rc, rec, sp = _run_worker(tmp_path, spec)
    assert rc == 0 and rec["status"] == "ok" and rec["canary"]["ok"] and not rec["neg"]["ok"]
    assert "vendor-petta106" in rec["petta"]
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
