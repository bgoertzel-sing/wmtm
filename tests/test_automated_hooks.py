"""rc2: Track G/H hooks on the automated fast path, shadow rate limit, worker CPU priority.

Synthetic data only.  Workers are never really started here except the two priority tests, which run the
real worker modules down a path that exits before any LLM/PeTTa work (missing prompt / missing PeTTa vendor).
"""
import json, os, statistics, subprocess, sys, time
import pytest
from wmtm import context as ctx, pc_shadow, parse_cache as pcm, runtime_config as rc

_ENV_KEYS = [v[0] for v in rc.SPEC.values()]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in _ENV_KEYS:
        monkeypatch.delenv(k, raising=False)


def _state(d, n=6, now=None):
    now = time.time() if now is None else now
    items = {}
    for i in range(n):
        iid = "syn-%02d" % i
        items[iid] = {"id": iid, "content": "synthetic widget%d is a gadget%d" % (i, i), "source_type": "recalled",
                      "origin_cluster": iid, "derived_from": [],
                      "attention": {"sti": 10.0 + i, "ati": 0.0, "lti": 0.0, "sti_decay": 0.9},
                      "age": 0, "utility": 5.0, "last_used": 0, "created_at": now - 60, "origin_timestamp": 0.0}
    p = os.path.join(str(d), "_wmtm_state.json")
    with open(p, "w") as f:
        json.dump({"cycle": 41, "store": {"items": items}}, f)
    return p


def _flags(d, **kw):
    with open(os.path.join(str(d), rc.FLAGS_FILENAME), "w") as f:
        json.dump(kw, f)


@pytest.fixture
def spawns(monkeypatch):
    """Record worker launches instead of starting processes."""
    calls = []

    def fake(cfg, module, args, pidfile):
        calls.append((module, list(args)))
        return 4242
    monkeypatch.setattr(rc, "spawn_worker", fake)
    return calls


def _mods(calls):
    return [m for m, _ in calls]


def test_fast_path_launches_both_hooks_when_flags_on(tmp_path, spawns):
    sf = _state(tmp_path)
    _flags(tmp_path, pc_shadow=True, semparse_feed=True)
    out = ctx.fast_path_automated(sf)
    assert out and "WMTM Active Working Memory" in out
    assert sorted(_mods(spawns)) == sorted([pc_shadow.WORKER_MODULE, pcm.WORKER_MODULE])
    args = dict(spawns)[pc_shadow.WORKER_MODULE]
    spec = json.load(open(args[args.index("--spec") + 1]))
    assert spec["source"] == "automated" and spec["cycle"] == 41 and spec["atoms"] == []
    ids = [r["id"] for r in spec["raw_items"]]
    assert ids == ["syn-%02d" % i for i in range(5, -1, -1)]            # active-set order (attention desc)
    assert spec["raw_items"][0]["content"] == "synthetic widget5 is a gadget5"
    q = json.load(open(tmp_path / "_wmtm_shadow" / "semparse_cache" / "queue.json"))
    assert len(q) == 6
    assert json.load(open(sf))["cycle"] == 42                            # fast-path bookkeeping unchanged


@pytest.mark.parametrize("flags", [None, {"pc_shadow": False, "semparse_feed": False},
                                   {"pc_shadow": True, "semparse_feed": True, "hooks_on_automated": False},
                                   "not json"])
def test_fast_path_no_hooks_when_off(tmp_path, spawns, flags):
    sf = _state(tmp_path)
    if isinstance(flags, dict):
        _flags(tmp_path, **flags)
    elif flags:
        (tmp_path / rc.FLAGS_FILENAME).write_text(flags)
    assert ctx.fast_path_automated(sf)
    assert spawns == [] and not (tmp_path / "_wmtm_shadow").exists()


def test_run_hooks_false_and_env_switch(tmp_path, spawns, monkeypatch):
    sf = _state(tmp_path)
    _flags(tmp_path, pc_shadow=True, semparse_feed=True)
    ctx.fast_path_automated(sf, run_hooks=False)
    monkeypatch.setenv("WMTM_HOOKS_ON_AUTOMATED", "0")
    ctx.fast_path_automated(sf)
    assert spawns == []


def test_api_automated_turn_runs_hooks(tmp_path, spawns):
    from wmtm.api import WMTM, WMTMConfig
    _state(tmp_path)
    _flags(tmp_path, pc_shadow=True)
    mem = WMTM(WMTMConfig(state_dir=str(tmp_path)))
    assert mem.context_for("")
    assert _mods(spawns) == [pc_shadow.WORKER_MODULE] and mem.orchestrator is None   # no engine loaded


def test_shadow_rate_limit(tmp_path, spawns):
    sf = _state(tmp_path)
    _flags(tmp_path, pc_shadow=True, shadow_min_interval_s=300)
    for _ in range(3):
        ctx.fast_path_automated(sf)
    assert _mods(spawns) == [pc_shadow.WORKER_MODULE]                   # 3 ticks, 1 launch
    stamp = tmp_path / "_wmtm_shadow" / "pc_shadow" / pc_shadow.LAST_LAUNCH
    old = time.time() - 301
    os.utime(stamp, (old, old))
    ctx.fast_path_automated(sf)
    assert _mods(spawns) == [pc_shadow.WORKER_MODULE] * 2               # interval elapsed -> next launch
    _flags(tmp_path, pc_shadow=True, shadow_min_interval_s=0)
    ctx.fast_path_automated(sf)
    assert len(spawns) == 3                                             # 0 = no limit


def test_rate_limit_applies_to_cycle_hook_too(tmp_path, spawns):
    from wmtm.store import WMTMStore
    st = WMTMStore()
    st.admit("a", "synthetic cat is a mammal", source_type="recalled", initial_sti=1.0)
    cfg = rc.resolve(str(tmp_path), environ={"WMTM_PC_SHADOW": "1"})
    assert pc_shadow.maybe_launch(st, 1, cfg=cfg) == 4242
    assert pc_shadow.maybe_launch(st, 2, cfg=cfg) is None
    assert pc_shadow.rate_limited(cfg) and not pc_shadow.rate_limited(dict(cfg, shadow_min_interval_s=0))


def test_busy_worker_blocks_launch(tmp_path, spawns):
    sf = _state(tmp_path)
    _flags(tmp_path, pc_shadow=True, semparse_feed=True, shadow_min_interval_s=0)
    for sub in ("pc_shadow", "semparse_cache"):
        d = tmp_path / "_wmtm_shadow" / sub
        d.mkdir(parents=True)
        (d / "worker.pid").write_text(str(os.getpid()))                 # a live process = busy
    ctx.fast_path_automated(sf)
    assert spawns == []


def test_parse_cap_respected(tmp_path, spawns):
    sf = _state(tmp_path)
    _flags(tmp_path, semparse_feed=True, parse_cap_per_hour=0)
    ctx.fast_path_automated(sf)
    assert spawns == []
    assert len(json.load(open(tmp_path / "_wmtm_shadow" / "semparse_cache" / "queue.json"))) == 6   # still queued


def test_feed_skips_enqueue_when_topk_unchanged(tmp_path, spawns, monkeypatch):
    sf = _state(tmp_path)
    _flags(tmp_path, semparse_feed=True, parse_cap_per_hour=0)
    calls = []
    orig = pcm.ParseCache.enqueue
    monkeypatch.setattr(pcm.ParseCache, "enqueue", lambda self, rows, now=None: calls.append(1) or orig(self, rows, now))
    ctx.fast_path_automated(sf)
    ctx.fast_path_automated(sf)
    assert len(calls) == 1
    s = json.load(open(sf))
    s["store"]["items"]["syn-00"]["content"] = "synthetic new content about gadgets"
    json.dump(s, open(sf, "w"))
    ctx.fast_path_automated(sf)
    assert len(calls) == 2


def test_feed_unchanged_still_launches_pending(tmp_path, spawns):
    sf = _state(tmp_path)
    _flags(tmp_path, semparse_feed=True)
    ctx.fast_path_automated(sf)
    assert _mods(spawns) == [pcm.WORKER_MODULE]
    ctx.fast_path_automated(sf)                                          # same top-K, queue still pending
    assert _mods(spawns) == [pcm.WORKER_MODULE] * 2


@pytest.mark.parametrize("target", ["pc", "feed", "resolve", "spawn"])
def test_no_exception_escapes(tmp_path, monkeypatch, target, capsys):
    sf = _state(tmp_path)
    _flags(tmp_path, pc_shadow=True, semparse_feed=True)

    def boom(*a, **k):
        raise RuntimeError("synthetic failure")
    if target == "pc":
        monkeypatch.setattr(pc_shadow, "maybe_launch_raw", boom)
    elif target == "feed":
        monkeypatch.setattr(pcm, "feed_rows", boom)
    elif target == "resolve":
        monkeypatch.setattr(rc, "resolve", boom)
    else:
        monkeypatch.setattr(rc, "spawn_worker", boom)
    out = ctx.fast_path_automated(sf)
    assert out and "cycle 41" in out and json.load(open(sf))["cycle"] == 42


def test_fast_path_does_not_import_engine(tmp_path):
    sf = _state(tmp_path)
    _flags(tmp_path, pc_shadow=True, semparse_feed=True, python="/bin/true")
    code = ("import sys; from wmtm import context as c; c.fast_path_automated(%r);"
            "heavy = [m for m in ('wmtm.orchestrator', 'wmtm.inference', 'wmtm.pln', 'wmtm.store', 'wmtm.semparse_adapter',"
            " 'wmtm.recall_bridge', 'numpy') if m in sys.modules]; print(heavy)") % sf
    r = subprocess.run([sys.executable, "-c", code], cwd=rc.DIST_ROOT, capture_output=True, text=True, timeout=60)
    assert r.stdout.strip() == "[]", r.stderr
    assert (tmp_path / "_wmtm_shadow" / "pc_shadow" / pc_shadow.LAST_LAUNCH).exists()


def test_latency_added_by_hooks(tmp_path, spawns):
    """Steady state (shadow rate-limited, top-K unchanged): median added latency far below the 20 ms target."""
    sf = _state(tmp_path, n=50)
    _flags(tmp_path, pc_shadow=True, semparse_feed=True)
    ctx.fast_path_automated(sf)                                          # warm imports, first launch + enqueue
    base, hooked = [], []
    for _ in range(40):
        t = time.perf_counter(); ctx.fast_path_automated(sf, run_hooks=False); base.append(time.perf_counter() - t)
        t = time.perf_counter(); ctx.fast_path_automated(sf); hooked.append(time.perf_counter() - t)
    added_ms = (statistics.median(hooked) - statistics.median(base)) * 1e3
    assert added_ms < 20.0, added_ms


# ---------------------------------------------------------------- worker CPU priority
def test_priority_guard_reasserts_after_reset(monkeypatch):
    """A scheduler daemon resetting the policy (cannot be done unprivileged, so simulated) is undone and counted."""
    state = {"pol": os.SCHED_OTHER, "nice": 12}
    monkeypatch.setattr(rc.os, "sched_getscheduler", lambda tid: state["pol"])
    monkeypatch.setattr(rc.os, "sched_setscheduler", lambda tid, pol, p: state.update(pol=pol))
    monkeypatch.setattr(rc.os, "getpriority", lambda which, tid: state["nice"])
    monkeypatch.setattr(rc.os, "setpriority", lambda which, tid, n: state.update(nice=n))
    monkeypatch.setattr(rc, "_tids", lambda pid="self": [0])
    monkeypatch.setattr(rc, "_descendants", lambda pid: [])
    g = rc.PriorityGuard({"worker_nice": 19, "worker_prio_refresh_s": 0})
    assert g.start() == {"nice": 19, "policy": "idle"}
    state.update(pol=os.SCHED_OTHER, nice=12)                            # daemon reset (system76-scheduler style)
    g.check()
    assert state == {"pol": os.SCHED_IDLE, "nice": 19} and g.resets == 1
    state.update(pol=os.SCHED_OTHER, nice=12)
    st = g.stats()
    assert st["end"] == {"nice": 12, "policy": "other"} and st["resets"] == 2 and state["pol"] == os.SCHED_IDLE


def test_priority_guard_thread_and_children():
    code = ("import os, subprocess, sys, time; from wmtm import runtime_config as rc;"
            "g = rc.PriorityGuard({'worker_nice': 19, 'worker_prio_refresh_s': 0.05}); print(g.start());"
            "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(2)']); time.sleep(0.3);"
            "print(p.pid in rc._descendants(os.getpid()), rc.priority_of(p.pid));"
            "import threading; print(sorted({rc.priority_of(t)['policy'] for t in rc._tids()}));"
            "s = g.stats(); p.kill(); print(s['end'], s['checks'] > 1)")
    r = subprocess.run([sys.executable, "-c", code], cwd=rc.DIST_ROOT, capture_output=True, text=True, timeout=60)
    lines = r.stdout.strip().splitlines()
    assert lines[0] == "{'nice': 19, 'policy': 'idle'}", r.stderr
    assert lines[1] == "True {'nice': 19, 'policy': 'idle'}"
    assert lines[2] == "['idle']"                                        # main + guard thread
    assert lines[3] == "{'nice': 19, 'policy': 'idle'} True"


@pytest.mark.skipif(not os.path.exists("/usr/bin/chrt"), reason="no chrt (the worker still sets SCHED_IDLE itself)")
def test_spawned_worker_is_idle_from_exec(tmp_path, monkeypatch):
    mod = tmp_path / "prmod"; mod.mkdir(); (mod / "__init__.py").write_text("")
    out = tmp_path / "prio.txt"
    (mod / "w.py").write_text("import os; open(%r, 'w').write('%%d %%d' %% (os.sched_getscheduler(0), "
                              "os.getpriority(os.PRIO_PROCESS, 0)))\n" % str(out))
    env0 = rc.worker_env
    monkeypatch.setattr(rc, "worker_env", lambda c, base=None: dict(env0(c, base), PYTHONPATH=str(tmp_path)))
    rc.spawn_worker(rc.resolve(str(tmp_path)), "prmod.w", [], str(tmp_path / "w.pid"))
    for _ in range(100):
        if out.exists() and out.read_text():
            break
        time.sleep(0.05)
    assert out.read_text() == "%d 19" % os.SCHED_IDLE


def _worker_cfg(tmp_path, **kw):
    cfg = rc.resolve(str(tmp_path)); cfg.update(kw)
    p = tmp_path / "wc.json"; p.write_text(json.dumps(cfg))
    return str(p)


def test_semparse_worker_records_actual_priority(tmp_path):
    d = tmp_path / "c"; d.mkdir()
    cp = _worker_cfg(tmp_path, semparse_prompt=str(tmp_path / "missing_prompt.txt"))
    r = subprocess.run([sys.executable, "-m", pcm.WORKER_MODULE, "--dir", str(d), "--config", cp, "--no-loader"],
                       cwd=rc.DIST_ROOT, env=rc.worker_env({}), capture_output=True, timeout=60)
    assert r.returncode == 5
    rec = json.loads((d / "worker_runs.jsonl").read_text().splitlines()[-1])
    assert rec["status"] == "prompt_missing"
    assert rec["prio"] == {"nice": 19, "policy": "idle"}
    assert rec["prio_end"]["end"] == {"nice": 19, "policy": "idle"} and rec["prio_end"]["resets"] == 0


def test_shadow_worker_records_actual_priority(tmp_path):
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"cycle": 1, "atoms": [], "goals": [], "source": "automated"}))
    out = tmp_path / "shadow.jsonl"
    cp = _worker_cfg(tmp_path)
    r = subprocess.run([sys.executable, "-m", pc_shadow.WORKER_MODULE, "--spec", str(spec), "--out", str(out),
                        "--config", cp, "--vendor", str(tmp_path / "nope"), "--petta", str(tmp_path / "nope"),
                        "--warm-timeout", "20"], cwd=rc.DIST_ROOT, env=rc.worker_env({}), capture_output=True,
                       timeout=90)
    rec = json.loads(out.read_text().splitlines()[-1])
    assert r.returncode == 3 and rec["status"] == "warm_fail" and rec["source"] == "automated"
    assert rec["prio"] == {"nice": 19, "policy": "idle"}
    assert rec["prio_end"]["end"] == {"nice": 19, "policy": "idle"}
