"""Runtime flags file (<state_dir>/_wmtm_flags.json), env overrides, paths, caps, skolem goal filter.  No PeTTa/LLM."""
import json, os, subprocess, sys

import pytest

from wmtm import runtime_config as rc, pc_shadow, parse_cache as pcm
from wmtm.store import WMTMStore

ENV_KEYS = [v[0] for v in rc.SPEC.values()]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ENV_KEYS:
        monkeypatch.delenv(k, raising=False)


def _flags(d, **kw):
    (d / rc.FLAGS_FILENAME).write_text(json.dumps(kw))


def test_defaults_off_without_file(tmp_path):
    cfg = rc.resolve(str(tmp_path))
    assert cfg["pc_shadow"] is False and cfg["semparse_feed"] is False
    assert cfg["parse_cap_per_hour"] == 20 and cfg["_source"]["loaded"] is False
    assert cfg["runtime_dir"] == str(tmp_path / rc.RUNTIME_SUBDIR)
    assert cfg["shadow_dir"] == str(tmp_path / rc.RUNTIME_SUBDIR / "pc_shadow")
    assert cfg["semparse_dir"] == str(tmp_path / rc.RUNTIME_SUBDIR / "semparse_cache")
    assert cfg["petta_dir"] == os.path.join(rc.VENDOR_ROOT, "petta-v1.0.6")
    assert cfg["pettachainer_dir"] == os.path.join(rc.VENDOR_ROOT, "pettachainer-36b3fe6-dedup")
    assert cfg["semparse_prompt"] == os.path.join(rc.VENDOR_ROOT, "semparse-hitl-3ec15bd1", "prompt.txt")
    assert cfg["swipl_bin"] == "" and cfg["llm_env_file"] == ""


def test_no_state_dir_uses_dev_local_data():
    cfg = rc.resolve(None)
    assert cfg["runtime_dir"] == os.path.join(rc.DIST_ROOT, ".local-data") and cfg["_source"]["flags_file"] is None


def test_flags_file_turns_on_and_sets_values(tmp_path):
    _flags(tmp_path, pc_shadow=True, semparse_feed=True, parse_cap_per_hour=40, shadow_k=50,
           runtime_dir="rt", swipl_bin="/opt/swipl/bin", petta_dir="/x/petta")
    cfg = rc.resolve(str(tmp_path))
    assert cfg["pc_shadow"] and cfg["semparse_feed"] and cfg["parse_cap_per_hour"] == 40 and cfg["shadow_k"] == 50
    assert cfg["runtime_dir"] == str(tmp_path / "rt") and cfg["semparse_dir"] == str(tmp_path / "rt" / "semparse_cache")
    assert cfg["swipl_bin"] == "/opt/swipl/bin" and cfg["petta_dir"] == "/x/petta" and cfg["_source"]["loaded"]


def test_env_overrides_file(tmp_path, monkeypatch):
    _flags(tmp_path, pc_shadow=True, semparse_feed=True, parse_cap_per_hour=40)
    monkeypatch.setenv("WMTM_PC_SHADOW", "0"); monkeypatch.setenv("WMTM_SEMPARSE_PER_HOUR", "7")
    cfg = rc.resolve(str(tmp_path))
    assert cfg["pc_shadow"] is False and cfg["semparse_feed"] is True and cfg["parse_cap_per_hour"] == 7
    monkeypatch.setenv("WMTM_PC_SHADOW", "")                       # empty = unset
    assert rc.resolve(str(tmp_path))["pc_shadow"] is True


@pytest.mark.parametrize("content", ["{not json", "[1, 2]", '"on"', ""])
def test_bad_flags_file_means_off(tmp_path, content):
    (tmp_path / rc.FLAGS_FILENAME).write_text(content)
    cfg = rc.resolve(str(tmp_path))
    assert cfg["pc_shadow"] is False and cfg["semparse_feed"] is False and "error" in cfg["_source"]


def test_bad_value_falls_back_to_default(tmp_path):
    _flags(tmp_path, pc_shadow="maybe", parse_cap_per_hour="lots", semparse_feed=True, typo_key=1)
    cfg = rc.resolve(str(tmp_path))
    assert cfg["pc_shadow"] is False and cfg["parse_cap_per_hour"] == 20 and cfg["semparse_feed"] is True
    assert set(cfg["_source"]["invalid"]) == {"pc_shadow", "parse_cap_per_hour"}
    assert cfg["_source"]["unknown_keys"] == ["typo_key"]


def _orch_store():
    st = WMTMStore()
    st.admit("s0", "cat is a mammal", source_type="recalled", initial_sti=1.0)
    st.admit("s1", "mammal is a animal", source_type="recalled", initial_sti=0.9)
    return st


def test_api_cycle_follows_flags_file_without_restart(tmp_path, monkeypatch):
    """One long-lived WMTM instance: flipping the flags file switches the hooks on the next cycle."""
    from wmtm.api import WMTM, WMTMConfig
    calls = []
    monkeypatch.setattr(pc_shadow, "maybe_launch", lambda store, cycle=0, state_dir=None, cfg=None: calls.append(("g", cfg["shadow_dir"])))
    monkeypatch.setattr(pcm, "maybe_feed", lambda store, cycle=0, state_dir=None, cache=None, cfg=None: calls.append(("h", cfg["parse_cap_per_hour"])))
    (tmp_path / "_journal").mkdir()
    mem = WMTM(WMTMConfig(state_dir=tmp_path))
    mem.observe({"user": "tell me about cats and mammals please"})
    mem.context_for("tell me about cats and mammals please")
    assert calls == []                                             # no flags file: off
    _flags(tmp_path, pc_shadow=True, semparse_feed=True, parse_cap_per_hour=30)
    mem.context_for("tell me about cats and mammals again")
    assert ("g", str(tmp_path / rc.RUNTIME_SUBDIR / "pc_shadow")) in calls and ("h", 30) in calls
    _flags(tmp_path, pc_shadow=False, semparse_feed=False)
    n = len(calls); mem.context_for("and once more about mammals")
    assert len(calls) == n                                         # switched off again, same process


def test_scratch_orchestrator_never_fires_from_flags(tmp_path, monkeypatch):
    """Orchestrators built without a state dir (e.g. decide()'s scratch store) ignore the bot's flags file."""
    from wmtm.orchestrator import WMTMOrchestrator
    _flags(tmp_path, pc_shadow=True, semparse_feed=True)
    calls = []
    monkeypatch.setattr(pc_shadow, "maybe_launch", lambda *a, **k: calls.append(1))
    monkeypatch.setattr(pcm, "maybe_feed", lambda *a, **k: calls.append(1))
    WMTMOrchestrator(_orch_store(), use_goalchainer=False).cycle()
    assert calls == []


def test_skolem_goals_filtered_but_facts_kept(tmp_path, monkeypatch):
    rel = {("Member", "sk_req_1__i_n1", "request"), ("Inheritance", "request", "message"),
           ("Member", "alice_x", "request")}
    g = pc_shadow.build_goals(rel)
    assert "(Member alice_x message)" in g and not any("sk_" in x for x in g)
    assert "(Member sk_req_1__i_n1 message)" in pc_shadow.build_goals(rel, skolem_goals=True)
    # end to end through a cached parse: the skolem fact is in the KB, its goal is not asked
    c = pcm.ParseCache(str(tmp_path / "c"), per_hour=5)
    monkeypatch.setenv("WMTM_SEMPARSE_DIR", c.d)
    text = "Someone sent a request; requests are messages."
    c.enqueue([("n1", text, 1.0)])

    class LLM:
        last_usage = {}
        def __call__(self, s, u):
            return ("(: a (Member sk_req_1 request) (STV 1.0 0.9))\n(: b (Inheritance request message) (STV 1.0 0.9))\n"
                    "(: c (Member zed request) (STV 1.0 0.9))")
    from wmtm.semparse_adapter import SemParseAdapter
    llm = LLM(); pcm.process_queue(c, llm, adapter=SemParseAdapter(llm, loader=None, system="SYS"))
    st = WMTMStore(); st.admit("n1", text, source_type="recalled", initial_sti=1.0)
    spec = pc_shadow.build_snapshot(st, cycle=1)
    assert any("(Member sk_req_1__i_n1 request)" in a for a in spec["atoms"])      # fact kept
    assert "(Member zed message)" in spec["goals"] and not any("sk_" in x for x in spec["goals"])
    monkeypatch.setenv("WMTM_PC_SHADOW_SKOLEM_GOALS", "1")
    assert "(Member sk_req_1__i_n1 message)" in pc_shadow.build_snapshot(st, cycle=1)["goals"]


def test_rotate_jsonl(tmp_path):
    p = str(tmp_path / "x.jsonl")
    for i in range(50):
        rc.append_jsonl(p, {"i": i, "pad": "x" * 40}, max_bytes=300)
    assert os.path.getsize(p) <= 300 + 80 and os.path.getsize(p + ".1") <= 300 + 80
    last = json.loads(open(p).read().splitlines()[-1])
    assert last["i"] == 49


def test_mem_cap_applies_in_child():
    code = ("from wmtm import runtime_config as rc; import resource; rc.apply_mem_cap(512); "
            "print(resource.getrlimit(resource.RLIMIT_AS)[0]); bytearray(800 * 1024 * 1024)")
    r = subprocess.run([sys.executable, "-c", code], cwd=rc.DIST_ROOT, capture_output=True, text=True, timeout=60)
    assert r.stdout.strip() == str(512 * 1024 * 1024) and r.returncode != 0 and "MemoryError" in r.stderr


def test_worker_env_and_busy(tmp_path):
    env = rc.worker_env({"swipl_bin": "/opt/swipl/bin", "petta_dir": "/x/petta"}, base={"PATH": "/usr/bin"})
    assert env["PATH"].startswith("/opt/swipl/bin" + os.pathsep) and env["PYTHONPATH"] == rc.DIST_ROOT
    assert env["PETTA_PATH"] == "/x/petta"
    pf = tmp_path / "w.pid"
    assert rc.busy(str(pf)) is False
    pf.write_text("999999999"); assert rc.busy(str(pf)) is False
    pf.write_text(str(os.getpid())); assert rc.busy(str(pf)) is True


def test_lower_priority_sched_idle_inherited():
    code = ("import os, subprocess, sys; from wmtm import runtime_config as rc; print(rc.lower_priority({'worker_nice': 19}));"
            "print(subprocess.run([sys.executable, '-c', 'import os; print(os.sched_getscheduler(0) == os.SCHED_IDLE, os.getpriority(os.PRIO_PROCESS, 0))'],"
            " capture_output=True, text=True).stdout.strip())")
    r = subprocess.run([sys.executable, "-c", code], cwd=rc.DIST_ROOT, capture_output=True, text=True, timeout=60)
    first, child = r.stdout.strip().splitlines()
    assert "'policy': 'idle'" in first and "'nice': 19" in first and child == "True 19"
