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
    assert "(Inheritance cat animal)" in spec["goals"] and "(Implies rain slippery)" not in spec["goals"]   # F3 v2: no Implies chains
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


@pytest.mark.skipif(not HAVE_PC, reason="vendored PeTTa / PeTTaChainer not present")
def test_integration_synthetic(tmp_path):
    spec = pc_shadow.build_snapshot(_store(SYN), cycle=1)
    rc, rec, sp = _run_worker(tmp_path, spec)
    assert rc == 0 and rec["status"] == "ok" and rec["canary"]["ok"] and not rec["neg"]["ok"]
    assert rec["petta"].startswith(_CFG["petta_dir"]) and rec["mem_cap_mb"] == _CFG["worker_mem_mb"]
    proved = {q["goal"] for q in rec["queries"] if q["ok"]}
    assert "(Inheritance cat animal)" in proved and "(Implies rain slippery)" not in proved   # F3 v2: engine-native only
    assert rec["goal_rank"]["pool"] >= 1 and all(q.get("hops", 0) >= 1 for q in rec["queries"])   # rc2: Track N
    assert not sp.exists()                                    # spec deleted


@pytest.mark.skipif(not HAVE_PC, reason="vendored PeTTa / PeTTaChainer not present")
def test_fault_timeout_is_canary_fail_not_hang(tmp_path):
    spec = pc_shadow.build_snapshot(_store(SYN), cycle=1)
    t = time.time(); rc, rec, _ = _run_worker(tmp_path, spec, "--timeout", "0.0001")
    # 120 s: proves "no hang" while leaving margin for ~20 s 202b9379 warm-up on a loaded 4-core box (review 6: 62 s at 60 s limit)
    assert rc == 3 and rec["status"] == "canary_fail" and rec["queries"] == [] and time.time() - t < 120


@pytest.mark.skipif(not HAVE_PC, reason="vendored PeTTa / PeTTaChainer not present")
def test_fault_bad_vendor_is_warm_fail(tmp_path):
    spec = pc_shadow.build_snapshot(_store(SYN), cycle=1)
    rc, rec, _ = _run_worker(tmp_path, spec, "--vendor", str(tmp_path / "nope"), "--warm-timeout", "20")
    assert rc == 3 and rec["status"] == "warm_fail"


# F1 §3: a reasoner conclusion is never re-parsed; it enters the KB with the engine TV and its sources
def _derived_store(srcs=("s0", "s1"), polarity="positive"):
    st = _store(SYN)
    st.admit("d0", "cat is a animal", source_type="derived", derived_from=list(srcs), initial_sti=0.5,
             provenance={"reasoner": "pettachainer", "goal": "(Inheritance cat animal)", "stv": [0.81, 0.73],
                         "polarity": polarity, "proof": "(r sp0 sp1)"})
    return st


def test_derived_enters_kb_with_engine_tv_and_sources():
    from wmtm import parse_cache
    st = _derived_store()
    spec = pc_shadow.build_snapshot(st, cycle=1, k=200)
    assert "(: wm0 (Inheritance cat animal) (STV 0.8100 0.7300))" in spec["atoms"]
    assert spec["atom_src"]["wm0"] == "d0" and spec["derived_src"] == {"wm0": ["s0", "s1"]}
    assert spec["derived_items"] == 1 and spec["semparse_items"] == 4 and spec["unparsed_items"] == 0
    assert "d0" not in [r[0] for r in parse_cache.top_k_rows(st, 200)]   # never queued for re-parsing


def test_derived_dropped_when_a_source_is_withdrawn():
    spec = pc_shadow.build_snapshot(_derived_store(srcs=("s0", "gone")), cycle=1, k=200)
    assert not any(" wm" in a or "(: wm" in a for a in spec["atoms"]) and spec["derived_src"] == {}
    assert spec["derived_items"] == 1


def test_derived_negative_conclusion_not_a_fact():
    spec = pc_shadow.build_snapshot(_derived_store(polarity="negative"), cycle=1, k=200)
    assert spec["derived_src"] == {}


def test_derived_survives_raw_roundtrip():
    st = _derived_store()
    raw = [pc_shadow.raw_item(it) for it in st.get_active_set()]
    spec = pc_shadow.build_snapshot(pc_shadow._RawStore(raw), cycle=1, k=200)
    assert spec["derived_src"] == {"wm0": ["s0", "s1"]}


def test_decision1_asserted_note_is_parsed_with_itself_as_source(tmp_path):
    """Decision 1: a mem.derive() note (source_type asserted) is fed to the parser like any note, its source is the
    note itself; a GoalChainer admission (derived) stays out of the parse feed."""
    from wmtm import parse_cache
    from wmtm.api import WMTM, WMTMConfig, derived_item_id
    from wmtm.context import _sources
    m = WMTM(WMTMConfig(state_dir=tmp_path))
    note = "the kestrel archive codeword is amber"
    m.derive(note, "src-1")
    m.context_for("kestrel codeword?")
    st = m.orchestrator.store
    iid = derived_item_id(note)
    it = st.get(iid)
    assert it.source_type == "asserted"
    assert iid in [r[0] for r in parse_cache.top_k_rows(st, 200)]
    assert _sources(it.source_type, it.id, it.origin_cluster, it.derived_from) == [iid]
    assert "d0" not in [r[0] for r in parse_cache.top_k_rows(_derived_store(), 200)]


def _deep_source_store():
    """F12 decision 2: the conclusion ranks high, its sources rank below the top-k cut but are still in memory."""
    st = WMTMStore()
    st.admit("d0", "cat is a animal", source_type="derived", derived_from=["s0", "s1"], initial_sti=1.0,
             provenance={"reasoner": "pettachainer", "goal": "(Inheritance cat animal)", "stv": [0.81, 0.73],
                         "polarity": "positive", "proof": "(r sp0 sp1)"})
    for i, t in enumerate(SYN):
        st.admit("s%d" % i, t, source_type="recalled", initial_sti=0.5 - i * 0.01)
    return st


def test_decision2_sources_outside_top_k_keep_the_conclusion():
    st = _deep_source_store()
    assert [it.id for it in st.get_active_set()][0] == "d0"
    spec = pc_shadow.build_snapshot(st, cycle=1, k=1)        # only d0 is in the snapshot
    assert "(: wm0 (Inheritance cat animal) (STV 0.8100 0.7300))" in spec["atoms"]
    assert spec["derived_src"] == {"wm0": ["s0", "s1"]}


def test_decision2_worker_path_uses_store_ids():
    st = _deep_source_store()
    act = st.get_active_set()
    raw = [pc_shadow.raw_item(it) for it in act[:1]]
    with_ids = pc_shadow.build_snapshot(pc_shadow._RawStore(raw, [it.id for it in act]), cycle=1, k=1)
    assert with_ids["derived_src"] == {"wm0": ["s0", "s1"]}
    no_ids = pc_shadow.build_snapshot(pc_shadow._RawStore(raw), cycle=1, k=1)   # old spec: only snapshot ids
    assert no_ids["derived_src"] == {}


def test_decision2_withdrawn_source_still_drops():
    st = _deep_source_store()
    act = st.get_active_set()
    ids = [it.id for it in act if it.id != "s1"]
    raw = [pc_shadow.raw_item(it) for it in act[:1]]
    spec = pc_shadow.build_snapshot(pc_shadow._RawStore(raw, ids), cycle=1, k=1)
    assert spec["derived_src"] == {}


def test_decision2_maybe_launch_passes_store_ids(monkeypatch):
    st = _deep_source_store()
    seen = {}
    monkeypatch.setattr(pc_shadow, "launch", lambda spec, cfg=None, **kw: seen.update(spec) or 7)
    monkeypatch.setattr(pc_shadow, "rate_limited", lambda cfg: False)
    cfg = dict(pc_shadow.rc.resolve()); cfg.update(pc_shadow=True, shadow_k=1)
    monkeypatch.setattr(pc_shadow.rc, "busy", lambda *a, **k: False)
    assert pc_shadow.maybe_launch(st, 3, cfg=cfg) == 7
    assert len(seen["raw_items"]) == 1 and set(seen["live_ids"]) == {"d0", "s0", "s1", "s2", "s3"}


# master-adopt-v2: upstream master load order (cfg shadow_load_order=master); legacy path unchanged without it
_SPH = os.environ.get("WMTM_PC_SHADOW_SPH_TEMPLATES", "")
HAVE_SPH = bool(_SPH) and os.path.isfile(os.path.join(_SPH, "tmpl", "lower.py"))


def test_master_load_off_by_default():
    spec = pc_shadow.build_snapshot(_store(SYN), cycle=1)
    assert "load_order" not in spec and "positive_only" not in spec and "master_rules" not in spec


def test_master_load_needs_templates_dir():
    with pytest.raises(RuntimeError):
        pc_shadow._master_load({"shadow_load_order": "master", "shadow_sph_templates": ""}, [])


@pytest.mark.skipif(not HAVE_SPH, reason="WMTM_PC_SHADOW_SPH_TEMPLATES not set")
def test_master_load_spec_keys():
    d = pc_shadow._master_load({"shadow_load_order": "master", "shadow_sph_templates": _SPH},
                               ["(: a (Member alice Pilot) (STV 1.0 0.9))"])
    assert d["load_order"] == "master" and "Pilot" in d["positive_only"] and d["master_rules"]
    assert all(not r.startswith(";") for r in d["master_rules"]) and d["master_meta"]["class_symbols"] == 1


@pytest.mark.skipif(not (HAVE_PC and HAVE_SPH), reason="engine or sph templates not present")
def test_integration_master_load_order(tmp_path):
    cfg = dict(_CFG, shadow_load_order="master", shadow_sph_templates=_SPH)
    spec = pc_shadow.build_snapshot(_store(SYN), cycle=1, cfg=cfg)
    assert spec["load_order"] == "master"
    rc_, rec, _ = _run_worker(tmp_path, spec)
    assert rc_ == 0 and rec["status"] == "ok" and rec["canary"]["ok"] and not rec["neg"]["ok"]
    assert rec["load_order"] == "master" and rec["master_meta"]["rules"] > 0
    assert rec["load_order"] == "master" and rec["master_meta"] == spec["master_meta"] and rec["pred_fail"] == 0


@pytest.mark.skipif(not (HAVE_PC and HAVE_SPH), reason="engine or sph templates not present")
def test_integration_master_ops_load_order(tmp_path):
    """master-adopt-v2: the worker runs master_loader ops in order (preds, rules, statements); canary/neg gate holds."""
    from wmtm import master_loader as ML
    ops, meta = ML.plan(_SPH, [], kb_once=True, rules=True)
    ops = ops + [("pred", "pilotx"), ("atom", "(: s1 (Member ann pilotx) (STV 1.0 0.9))"),
                 ("atom", "(: s2 (Inheritance pilotx person) (STV 1.0 0.9))")]
    spec = {"load_order": "master_ops", "master_ops": ops, "atoms": [], "goals": ["(Member ann person)"],
            "master_meta": {k: v for k, v in meta.items() if k != "notes"}, "cycle": 1, "k": 0, "items": 0}
    rc_, rec, _ = _run_worker(tmp_path, spec)
    assert rc_ == 0 and rec["status"] == "ok" and rec["canary"]["ok"] and not rec["neg"]["ok"]
    assert rec["load_order"] == "master_ops" and rec["add_fail"] == 0 and rec["pred_fail"] == 0
    assert rec["master_meta"]["rules"] == meta["rules"] > 0
