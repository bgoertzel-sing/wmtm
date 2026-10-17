"""v0.4.0-rc2: PeTTaChainer admission independent of the cycle budget, on automated turns, once per run, logged.

Synthetic data only; no worker is started (pc_shadow.maybe_launch is stubbed on the cycle path, pc_shadow flag off).
"""
import json, os, statistics, time
import pytest
from wmtm import context as ctx, pc_admit, pc_shadow, runtime_config as rc
from wmtm.api import WMTM, WMTMConfig

_ENV_KEYS = [v[0] for v in rc.SPEC.values()]
R_CAT = {"goal": "(Inheritance tabby_housecat vertebrate_animal)", "stv": [0.9, 0.6], "proof": "(inh_trans sp0 sp1)", "s": 0.3, "sources": ["s0", "s1"]}
R_RAIN = {"goal": "(Implies heavy_rainfall slippery_roads)", "stv": [0.8, 0.5], "proof": "(imp_trans sp2 sp3)", "s": 0.2, "sources": ["s2", "s3"]}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for k in _ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(pc_shadow, "maybe_launch", lambda *a, **k: None)
    monkeypatch.setattr(rc, "spawn_worker", lambda *a, **k: None)


class _Journal:
    def read_lines(self):
        return []

    def append(self, note, supersedes=None, about=None):
        return {"ok": True}


def _setup(d, flags=None, n=4):
    now = time.time()
    items = {}
    for i, t in enumerate(["The tabby housecat is a kind of mammal", "Mammals are vertebrate animals with fur",
                               "Heavy rainfall makes the streets wet", "Wet streets become slippery roads quickly"][:n]):
        iid = "s%d" % i
        items[iid] = {"id": iid, "content": t, "source_type": "derived", "origin_cluster": iid, "derived_from": [],
                      "attention": {"sti": 10.0 - i, "ati": 0.0, "lti": 0.0, "sti_decay": 0.9},
                      "age": 0, "utility": 5.0, "last_used": 0, "created_at": now - 60, "origin_timestamp": 0.0}
    with open(os.path.join(str(d), "_wmtm_state.json"), "w") as f:
        json.dump({"cycle": 7, "store": {"capacity": 60, "tick": 0, "items": items}}, f)
    with open(os.path.join(str(d), rc.FLAGS_FILENAME), "w") as f:
        json.dump(dict({"reasoner": "pettachainer"}, **(flags or {})), f)
    return os.path.join(str(d), "_wmtm_state.json")


def _shadow(d):
    p = os.path.join(str(d), "_wmtm_shadow", "pc_shadow")
    os.makedirs(p, exist_ok=True)
    return p


def _admit_doc(d, results=(R_CAT, R_RAIN), status="ok", canary_ok=True, age=0.0, spec_ts=None):
    ts = spec_ts if spec_ts is not None else time.time() - age
    doc = {"ts": ts + 1, "spec_ts": ts, "cycle": 0, "status": status, "canary_ok": canary_ok, "results": list(results)}
    with open(os.path.join(_shadow(d), pc_admit.ADMIT_FILE), "w") as f:
        json.dump(doc, f)
    return doc


def _pc_items(d):
    st = json.load(open(os.path.join(str(d), "_wmtm_state.json")))
    return {v["content"]: v for v in st["store"]["items"].values()
            if (v.get("provenance") or {}).get("reasoner") == "pettachainer"}


def _log(d):
    p = os.path.join(_shadow(d), pc_admit.ADMIT_LOG)
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


def _mem(d, **kw):
    return WMTM(WMTMConfig(state_dir=d, journal=_Journal(), **kw))


# ------------------------------------------------------------------ user turn, cycle skipped for budget
def test_budget_exceeded_user_turn_still_admits(tmp_path):
    _setup(tmp_path); _admit_doc(tmp_path)
    m = _mem(tmp_path, cycle_budget=0.0)                       # full cycle never fits: rc1 admitted nothing here
    m.observe({"user": "tell me about cats and the rain please"})
    out = m.context_for("tell me about cats and the rain please")
    pc = _pc_items(tmp_path)
    assert set(pc) == {"tabby_housecat is a vertebrate_animal", "heavy_rainfall implies slippery_roads"} and "tabby_housecat is a vertebrate_animal" in out
    it = pc["tabby_housecat is a vertebrate_animal"]
    assert it["id"].startswith("derived-pc_deduction-") and it["derived_from"] == ["s0", "s1"]
    assert it["provenance"]["proof"] == "(inh_trans sp0 sp1)"
    rec = _log(tmp_path)[-1]
    assert rec["path"] == "budget-skipped" and rec["admitted"] == 2 and rec["candidates"] == 2
    assert {"journal_s", "derives_cleanup_s", "admit_s", "total_s", "elapsed_before_cycle_s"} <= set(rec["timing"])
    assert "tabby" not in json.dumps(rec) and "housecat" not in json.dumps(rec)                         # numbers / ids only, no content


def test_full_cycle_user_turn_logs_timing(tmp_path):
    _setup(tmp_path); _admit_doc(tmp_path)
    m = _mem(tmp_path)
    m.context_for("tell me about cats and the rain please")
    rec = _log(tmp_path)[-1]
    assert rec["path"] == "user" and rec["admitted"] == 2 and "cycle_s" in rec["timing"]
    assert len(_pc_items(tmp_path)) == 2


# ------------------------------------------------------------------ automated turn
def test_automated_turn_admits_and_shows(tmp_path):
    _setup(tmp_path); _admit_doc(tmp_path)
    out = _mem(tmp_path).context_for("", automated=True)
    assert "tabby_housecat is a vertebrate_animal" in out and "heavy_rainfall implies slippery_roads" in out
    pc = _pc_items(tmp_path)
    assert len(pc) == 2 and all(v["source_type"] == "derived" for v in pc.values())
    st = json.load(open(os.path.join(str(tmp_path), "_wmtm_state.json")))
    assert st["pc_admit"]["consumed_run"] == pc_admit.run_id(json.load(open(os.path.join(_shadow(tmp_path), "admit.json"))))
    assert st["utility"]["records"]["s0"]["inferred_from_count"] == 1
    rec = _log(tmp_path)[-1]
    assert rec["path"] == "automated" and rec["admitted"] == 2 and "admit_s" in rec["timing"]


def test_automated_respects_caps_and_guards(tmp_path):
    _setup(tmp_path, flags={"reasoner_max_admit": 1}); _admit_doc(tmp_path)
    ctx.fast_path_automated(os.path.join(str(tmp_path), "_wmtm_state.json"))
    assert len(_pc_items(tmp_path)) == 1


# ------------------------------------------------------------------ once per run
def test_same_run_not_admitted_twice(tmp_path):
    sf = _setup(tmp_path); _admit_doc(tmp_path)
    m = _mem(tmp_path)
    m.context_for("", automated=True)
    first = set(v["id"] for v in _pc_items(tmp_path).values())
    # purge the admitted items: the same run must still not come back, on either path
    st = json.load(open(sf))
    st["store"]["items"] = {k: v for k, v in st["store"]["items"].items() if not v.get("provenance")}
    json.dump(st, open(sf, "w"))
    m.context_for("", automated=True)
    m2 = _mem(tmp_path, cycle_budget=0.0)
    m2.context_for("tell me about cats and the rain please")
    m3 = _mem(tmp_path)
    m3.context_for("tell me about cats and the rain please")
    assert len(first) == 2 and _pc_items(tmp_path) == {}
    assert [r["skipped"] for r in _log(tmp_path)[1:]] == ["already_consumed"] * 3
    # a new run is admitted again
    _admit_doc(tmp_path, spec_ts=time.time() + 1)
    _mem(tmp_path).context_for("", automated=True)
    assert len(_pc_items(tmp_path)) == 2 and _log(tmp_path)[-1]["admitted"] == 2


def test_no_live_source_does_not_consume(tmp_path):
    sf = _setup(tmp_path); _admit_doc(tmp_path, results=[dict(R_CAT, sources=["gone"])])
    ctx.fast_path_automated(sf)
    assert "pc_admit" not in json.load(open(sf)) and _log(tmp_path)[-1]["skipped"] == "no_candidates"


# ------------------------------------------------------------------ failed / stale runs
@pytest.mark.parametrize("kw,reason", [({"age": 1000.0}, "stale"), ({"canary_ok": False}, "run_ok"),
                                       ({"status": "canary_fail"}, "run_canary_fail")])
def test_stale_or_failed_run_admits_nothing(tmp_path, kw, reason):
    _setup(tmp_path); _admit_doc(tmp_path, **kw)
    _mem(tmp_path).context_for("", automated=True)
    _mem(tmp_path, cycle_budget=0.0).context_for("tell me about cats and the rain please")
    _mem(tmp_path).context_for("tell me about cats and the rain please")
    assert _pc_items(tmp_path) == {}
    assert [r["skipped"] for r in _log(tmp_path)] == [reason] * 3
    assert [r["path"] for r in _log(tmp_path)] == ["automated", "budget-skipped", "user"]


def test_missing_admit_file_logged(tmp_path):
    sf = _setup(tmp_path)
    ctx.fast_path_automated(sf)
    assert _pc_items(tmp_path) == {} and _log(tmp_path)[-1]["skipped"] == "no_admit_file"


# ------------------------------------------------------------------ flags
def test_flag_off_no_automated_admission(tmp_path):
    _setup(tmp_path, flags={"reasoner_admit_on_automated": False}); _admit_doc(tmp_path)
    _mem(tmp_path).context_for("", automated=True)
    assert _pc_items(tmp_path) == {} and _log(tmp_path)[-1]["skipped"] == "automated_off"
    _mem(tmp_path, cycle_budget=0.0).context_for("tell me about cats and the rain please")   # user turns still admit
    assert len(_pc_items(tmp_path)) == 2


def test_python_mode_no_admission_no_log(tmp_path):
    _setup(tmp_path, flags={"reasoner": "python"}); _admit_doc(tmp_path)
    _mem(tmp_path).context_for("", automated=True)
    _mem(tmp_path, cycle_budget=0.0).context_for("tell me about cats and the rain please")
    assert _pc_items(tmp_path) == {} and _log(tmp_path) == []


def test_admit_log_rotates(tmp_path):
    cfg = {"shadow_dir": _shadow(tmp_path), "admit_log_max_bytes": 300}
    for _ in range(20):
        pc_admit.log_admission(cfg, "automated", {"skipped": "stale", "admitted": 0})
    p = os.path.join(_shadow(tmp_path), pc_admit.ADMIT_LOG)
    assert os.path.getsize(p) <= 600 and os.path.exists(p + ".1")


# ------------------------------------------------------------------ latency
def test_fast_path_admit_latency(tmp_path):
    """Steady state (run already consumed): median added latency of the admission step well below 30 ms."""
    sf = _setup(tmp_path); _admit_doc(tmp_path)
    ctx.fast_path_automated(sf)                                     # admits + consumes
    base, adm = [], []
    for _ in range(40):
        t = time.perf_counter(); ctx.fast_path_automated(sf, admit=False); base.append(time.perf_counter() - t)
        t = time.perf_counter(); ctx.fast_path_automated(sf); adm.append(time.perf_counter() - t)
    added_ms = (statistics.median(adm) - statistics.median(base)) * 1e3
    assert added_ms < 30.0, added_ms


# ------------------------------------------------------------------ known conclusions do not fill the cap
@pytest.mark.parametrize("path", ["automated", "budget-skipped", "user"])
def test_new_run_reproving_admitted_conclusions_admits_new_ones(tmp_path, path):
    _setup(tmp_path, flags={"reasoner_max_admit": 1})
    _admit_doc(tmp_path, results=[R_CAT])
    _mem(tmp_path).context_for("", automated=True)
    assert set(_pc_items(tmp_path)) == {"tabby_housecat is a vertebrate_animal"}
    _admit_doc(tmp_path, results=[dict(R_CAT, stv=[0.95, 0.9]), R_RAIN], spec_ts=time.time() + 1)   # R_CAT ranks first
    if path == "automated":
        _mem(tmp_path).context_for("", automated=True)
    else:
        _mem(tmp_path, **({"cycle_budget": 0.0} if path == "budget-skipped" else {})).context_for("tell me about cats and the rain please")
    assert set(_pc_items(tmp_path)) == {"tabby_housecat is a vertebrate_animal", "heavy_rainfall implies slippery_roads"}
    rec = _log(tmp_path)[-1]
    assert rec["path"] == path and rec["admitted"] == 1 and rec["dropped"]["known"] == 1


def test_automated_skips_forgotten_conclusion(tmp_path):
    from wmtm.forgetting_log import content_hash
    sf = _setup(tmp_path); _admit_doc(tmp_path)
    st = json.load(open(sf))
    st["forgetting_log"] = {"max_records": 500, "records": [{"item_id": "x", "content_hash": content_hash("tabby_housecat is a vertebrate_animal")}]}
    json.dump(st, open(sf, "w"))
    ctx.fast_path_automated(sf)
    assert set(_pc_items(tmp_path)) == {"heavy_rainfall implies slippery_roads"} and _log(tmp_path)[-1]["dropped"]["known"] == 1
