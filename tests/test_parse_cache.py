"""Track H: semparse parse cache + shadow feed.  All mocked (no LLM, no PeTTa)."""
import json, os, time
import pytest
from wmtm import parse_cache as pcm, pc_shadow, runtime_config as rc
from wmtm.parse_cache import ParseCache, process_queue, content_hash
from wmtm.store import WMTMStore


def _store(texts):
    st = WMTMStore()
    for i, t in enumerate(texts):
        st.admit("s%d" % i, t, source_type="recalled", initial_sti=1.0 - i * 0.01)
    return st


class FakeLLM:
    def __init__(self, replies=None, fail=False):
        self.replies, self.fail, self.calls, self.last_usage = replies or {}, fail, [], {}
    def __call__(self, system, user):
        self.calls.append(user)
        if self.fail:
            raise RuntimeError("gateway down")
        self.last_usage = {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110}
        for k, v in self.replies.items():
            if k in user:
                return v
        return "(: f1 (Inheritance thing stuff) (STV 1.0 0.9))"


def _cache(tmp_path, **kw):
    return ParseCache(str(tmp_path / "c"), **kw)


def _ad(llm):
    from wmtm.semparse_adapter import SemParseAdapter
    return SemParseAdapter(llm, loader=None, system="SYS")


def test_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("WMTM_SEMPARSE_FEED", raising=False)
    c = _cache(tmp_path)
    assert pcm.maybe_feed(_store(["a"]), 1, cache=c) is None and not os.path.exists(c.queue_path)


def test_never_parses_same_content_twice(tmp_path):
    c = _cache(tmp_path); llm = FakeLLM()
    c.enqueue([("a", "x is a y", 1.0), ("b", "x is a y", 0.5)])     # same content, two ids -> one entry
    assert c.pending() == 1
    process_queue(c, llm, adapter=_ad(llm)); assert len(llm.calls) == 1
    st = c.enqueue([("a", "x is a y", 1.0)])
    assert st["cached"] == 1 and c.pending() == 0
    process_queue(c, llm, adapter=_ad(llm)); assert len(llm.calls) == 1
    assert c.atoms_for("x is a y") and c.atoms_for("other") is None


def test_hourly_cap_and_order(tmp_path):
    c = _cache(tmp_path, per_hour=3); llm = FakeLLM(); t0 = 1000.0
    c.enqueue([("old_low", "t0", 0.1)], now=t0)
    c.enqueue([("new_hi", "t1", 0.9), ("new_lo", "t2", 0.2), ("new_mid", "t3", 0.5), ("new_x", "t4", 0.3)], now=t0 + 10)
    order = [h for h, q in c.next_batch(10)]
    assert [c._queue()[h]["item_id"] for h in order][:3] == ["old_low", "new_hi", "new_mid"]
    recs = process_queue(c, llm, adapter=_ad(llm), now=lambda: t0 + 20)
    assert len(recs) == 3 and c.budget(t0 + 20) == 0 and c.pending() == 2
    assert process_queue(c, llm, adapter=_ad(llm), now=lambda: t0 + 30) == []      # capped
    assert len(process_queue(c, llm, adapter=_ad(llm), now=lambda: t0 + 3700)) == 2  # window rolled


def test_size_cap_skips(tmp_path):
    c = _cache(tmp_path, max_chars=10)
    st = c.enqueue([("big", "x" * 11, 1.0), ("ok", "short", 1.0)])
    assert st["skipped_long"] == 1 and c.pending() == 1


def test_cost_logged(tmp_path):
    c = _cache(tmp_path); llm = FakeLLM()
    c.enqueue([("a", "x is a y", 1.0)]); r = process_queue(c, llm, adapter=_ad(llm))[0]
    assert r["total_tokens"] == 110 and r["secs"] >= 0 and r["status"] == "ok" and r["accepted"] == 1
    assert json.loads(open(c.log_path).read().splitlines()[0])["prompt_tokens"] == 100


def test_llm_failure_retried_then_cached_failed(tmp_path):
    c = _cache(tmp_path, max_attempts=2); llm = FakeLLM(fail=True)
    c.enqueue([("a", "x is a y", 1.0)])
    assert process_queue(c, llm, adapter=_ad(llm))[0]["status"] == "llm_error" and c.pending() == 1
    process_queue(c, llm, adapter=_ad(llm))
    assert c.pending() == 0 and c.atoms_for("x is a y") is None and len(llm.calls) == 2


def test_fault_parser_failure_does_not_affect_cycle(monkeypatch, tmp_path):
    from wmtm import orchestrator as orch
    monkeypatch.setenv("WMTM_SEMPARSE_FEED", "1"); monkeypatch.setenv("WMTM_PC_SHADOW", "1")
    def boom(*a, **k): raise RuntimeError("parser exploded")
    monkeypatch.setattr(pcm, "maybe_feed", boom)
    monkeypatch.setattr(pc_shadow, "launch", lambda *a, **k: None)
    o = orch.WMTMOrchestrator(_store(["cat is a mammal"]), use_goalchainer=False)
    assert o.cycle() is not None
    # and the real hook swallows internal errors too
    monkeypatch.undo(); monkeypatch.setenv("WMTM_SEMPARSE_FEED", "1")
    monkeypatch.setattr(ParseCache, "enqueue", boom)
    assert pcm.maybe_feed(_store(["a"]), 1, cache=_cache(tmp_path)) is None


def test_fault_worker_with_dead_gateway(tmp_path, monkeypatch):
    """Worker subprocess with an unreachable gateway: records llm_error, exits, cycle side untouched."""
    import subprocess, sys
    c = _cache(tmp_path); c.enqueue([("a", "x is a y", 1.0)])
    env = dict(rc.worker_env(rc.resolve()), BASE_URL="http://127.0.0.1:9/v1", LLM_MODEL="m", AI_API_KEY="k",
               SEMPARSE_PROMPT=str(tmp_path / "p.txt"),
               WMTM_SEMPARSE_PROMPT_SHA256=__import__("hashlib").sha256(b"SYS").hexdigest())
    (tmp_path / "p.txt").write_text("SYS")
    code = subprocess.run([sys.executable, "-m", pcm.WORKER_MODULE, "--dir", c.d, "--no-loader"], env=env,
                          cwd=rc.DIST_ROOT, timeout=60).returncode
    assert code == 0
    log = [json.loads(l) for l in open(c.log_path)]
    assert log[0]["status"] == "llm_error" and c.pending() == 1


def test_shadow_uses_cache_then_falls_back(tmp_path, monkeypatch):
    c = _cache(tmp_path); monkeypatch.setenv("WMTM_SEMPARSE_DIR", c.d)
    s1, s2 = "Rex is a dog of ours.", "dog is a mammal"
    llm = FakeLLM({s1: "(: r1 (Member rex dog) (STV 1.0 0.9))"})
    c.enqueue([("s0", s1, 1.0)]); process_queue(c, llm, adapter=_ad(llm))
    spec = pc_shadow.build_snapshot(_store([s1, s2]), cycle=1)
    assert spec["semparse_items"] == 1 and spec["fallback_atoms"] >= 1
    assert "(Member rex mammal)" in spec["goals"]                    # Member x Inheritance join
    assert any(d.get("goal") == "(Member rex mammal)" for d in spec["python_derived"])


def test_build_goals_chains_and_joins():
    rel = {("Inheritance", "a", "b"), ("Inheritance", "b", "c"), ("Implies", "p", "q"), ("Implies", "q", "r"),
           ("Member", "x", "a"), ("Inheritance", "a", "c")}
    g = pc_shadow.build_goals(rel)
    assert "(Implies p r)" in g and "(Member x b)" in g and "(Member x c)" in g
    assert "(Inheritance a c)" not in g                              # already asserted


def test_worker_refuses_unpinned_prompt(tmp_path):
    """A prompt that does not match the pinned sha256 stops the worker before any LLM spend."""
    import subprocess, sys
    c = _cache(tmp_path); c.enqueue([("a", "x is a y", 1.0)])
    (tmp_path / "p.txt").write_text("not the pinned prompt")
    env = dict(rc.worker_env(rc.resolve()), BASE_URL="http://127.0.0.1:9/v1", LLM_MODEL="m", AI_API_KEY="k",
               SEMPARSE_PROMPT=str(tmp_path / "p.txt"))
    code = subprocess.run([sys.executable, "-m", pcm.WORKER_MODULE, "--dir", c.d, "--no-loader"], env=env,
                          cwd=rc.DIST_ROOT, timeout=60).returncode
    run = json.loads(open(os.path.join(c.d, "worker_runs.jsonl")).read().splitlines()[-1])
    assert code == 5 and run["status"] == "prompt_mismatch" and not os.path.exists(c.log_path) and c.pending() == 1


def test_parse_log_size_cap_keeps_hourly_count(tmp_path):
    """The parse log is size-capped, but records inside the rolling hour are never rotated away (cost cap holds)."""
    c = _cache(tmp_path, per_hour=5, log_max_bytes=200); llm = FakeLLM(); t0 = 5000.0
    c.enqueue([("i%d" % i, "text %d" % i, 1.0) for i in range(12)], now=t0)
    assert len(process_queue(c, llm, adapter=_ad(llm), now=lambda: t0 + 1)) == 5
    assert c.used_last_hour(t0 + 2) == 5 and process_queue(c, llm, adapter=_ad(llm), now=lambda: t0 + 2) == []
    assert len(process_queue(c, llm, adapter=_ad(llm), now=lambda: t0 + 3700)) == 5      # next hour
    assert os.path.exists(c.log_path + ".1") and c.used_last_hour(t0 + 3701) == 5
    assert len(open(c.log_path).read().splitlines()) == 5                               # old hour moved out


def test_cache_compaction_bounds_size(tmp_path):
    c = _cache(tmp_path, per_hour=100, cache_max_bytes=600); llm = FakeLLM()
    c.enqueue([("i%d" % i, "text %d" % i, 1.0) for i in range(20)])
    process_queue(c, llm, adapter=_ad(llm))
    assert os.path.getsize(c.entries_path) <= 600
    ent = c.entries()
    assert 0 < len(ent) < 20 and c.atoms_for("text 19") is not None   # newest kept, oldest dropped
