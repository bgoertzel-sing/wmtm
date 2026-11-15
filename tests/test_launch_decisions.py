"""L-03 (t-2026-11-15-wmtm-feed-watch): one launch-decision line per launch_worker / feed_rows decision.

Synthetic state only (tmp dirs, no LLM, no worker actually spawned)."""
import json
import os

import pytest

from wmtm import parse_cache as pcm, runtime_config as rc
from wmtm.parse_cache import ParseCache

SECRET = "zz-sentinel note text that must never reach the decision log"


def _cfg(tmp_path, **kw):
    c = rc.resolve(str(tmp_path / "sd"))
    c.update({"parse_budget_dir": str(tmp_path / "budget"), "semparse_feed": True, "shadow_k": 50,
              "speaker_link": False, "semparse_context": False, **kw})
    return c


def _cache(tmp_path, cfg, per_hour=20):
    c = ParseCache(str(tmp_path / "sd" / "semparse_cache"), cfg=cfg, per_hour=per_hour)
    os.makedirs(c.d, exist_ok=True)
    return c


def _lines(c):
    p = os.path.join(c.d, pcm.LAUNCH_LOG)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as fh:
        return [json.loads(x) for x in fh]


@pytest.fixture
def spawned(monkeypatch):
    calls = []

    def fake_spawn(cfg, module, args, pidfile):
        calls.append(args)
        return 424242
    monkeypatch.setattr(rc, "spawn_worker", fake_spawn)
    monkeypatch.setattr(rc, "busy", lambda pidfile, max_age=None: False)
    return calls


def _check_fields(rec, decision):
    assert rec["decision"] == decision and decision in pcm.LAUNCH_DECISIONS
    assert set(rec) >= {"ts", "decision", "pending", "budget_left", "role"}
    assert isinstance(rec["ts"], float)


def test_launched_line(tmp_path, spawned):
    cfg = _cfg(tmp_path)
    c = _cache(tmp_path, cfg)
    c.enqueue([("a", "x is a y", 1.0), ("b", "p is a q", 0.5)])
    assert pcm.launch_worker(c, cfg) == 424242 and len(spawned) == 1
    (rec,) = _lines(c)
    _check_fields(rec, "launched")
    assert rec["pending"] == 2 and rec["budget_left"] == 10 and rec["role"] == "task" and rec["pid"] == 424242


def test_nothing_pending_line(tmp_path, spawned):
    cfg = _cfg(tmp_path)
    c = _cache(tmp_path, cfg)
    assert pcm.launch_worker(c, cfg) is None and spawned == []
    (rec,) = _lines(c)
    _check_fields(rec, "nothing_pending")
    assert rec["pending"] == 0 and rec["budget_left"] == 10


def test_budget_zero_line(tmp_path, spawned):
    cfg = _cfg(tmp_path)
    c = _cache(tmp_path, cfg, per_hour=0)              # own cap 0 -> budget() == 0
    c.enqueue([("a", "x is a y", 1.0)])
    assert pcm.launch_worker(c, cfg, pending=1) is None and spawned == []
    (rec,) = _lines(c)
    _check_fields(rec, "budget_zero")
    assert rec["budget_left"] == 0 and rec["pending"] == 1


def test_budget_zero_from_full_live_share(tmp_path, spawned):
    live = tmp_path / "sd" / "semparse_cache"
    cfg = _cfg(tmp_path, parse_role="live", parse_live_dir=str(live), parse_share_live_per_hour=2)
    c = _cache(tmp_path, cfg)
    with open(live / "share_ledger.jsonl", "w") as fh:
        import time as _t
        for i in range(2):
            fh.write(json.dumps({"ts": _t.time() - 60, "call_id": "c%d" % i, "role": "live"}) + "\n")
    c.enqueue([("a", "x is a y", 1.0)])
    assert pcm.launch_worker(c, cfg) is None and spawned == []
    (rec,) = _lines(c)
    _check_fields(rec, "budget_zero")
    assert rec["role"] == "live"


def test_busy_line_does_not_read_budget(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    c = _cache(tmp_path, cfg)
    monkeypatch.setattr(rc, "busy", lambda pidfile, max_age=None: True)
    monkeypatch.setattr(ParseCache, "budget", lambda self, now=None: pytest.fail("budget read while busy"))
    assert pcm.launch_worker(c, cfg, pending=3) is None
    (rec,) = _lines(c)
    _check_fields(rec, "busy")
    assert rec["pending"] == 3 and rec["budget_left"] is None


def test_feed_rows_error_line_has_type_only(tmp_path, spawned, monkeypatch):
    cfg = _cfg(tmp_path)
    c = _cache(tmp_path, cfg)

    def boom(self, rows, now=None):
        raise KeyError(SECRET)
    monkeypatch.setattr(ParseCache, "enqueue", boom)
    assert pcm.feed_rows([("a", SECRET, 1.0)], cfg, cache=c) is None      # still swallowed, still None
    (rec,) = _lines(c)
    _check_fields(rec, "error")
    assert rec["error"] == "KeyError" and "pid" not in rec
    raw = open(os.path.join(c.d, pcm.LAUNCH_LOG), encoding="utf-8").read()
    assert SECRET not in raw and "sentinel" not in raw


def test_spawn_failure_is_an_error_line(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    c = _cache(tmp_path, cfg)
    monkeypatch.setattr(rc, "busy", lambda pidfile, max_age=None: False)

    def bad_spawn(*a, **k):
        raise OSError("no such interpreter")
    monkeypatch.setattr(rc, "spawn_worker", bad_spawn)
    assert pcm.feed_rows([("a", "x is a y", 1.0)], cfg, cache=c) is None
    (rec,) = _lines(c)
    _check_fields(rec, "error")
    assert rec["error"] == "OSError"


def test_maybe_feed_error_line(tmp_path, spawned):
    cfg = _cfg(tmp_path)
    c = _cache(tmp_path, cfg)

    class BadStore:
        def get_active_set(self):
            raise RuntimeError(SECRET)
    assert pcm.maybe_feed(BadStore(), 1, cache=c, cfg=cfg) is None
    (rec,) = _lines(c)
    _check_fields(rec, "error")
    assert rec["error"] == "RuntimeError"
    assert SECRET not in open(os.path.join(c.d, pcm.LAUNCH_LOG), encoding="utf-8").read()


def test_feed_rows_paths_each_leave_one_line(tmp_path, spawned):
    cfg = _cfg(tmp_path)
    c = _cache(tmp_path, cfg)
    rows = [("a", "x is a y", 1.0)]
    assert pcm.feed_rows(rows, cfg, cache=c, skip_unchanged=True) == 424242          # enqueue + launch
    assert pcm.feed_rows(rows, cfg, cache=c, skip_unchanged=True) == 424242          # unchanged signature path
    assert pcm.feed_rows(rows, cfg, cache=c) == 424242                               # cycle path
    assert [r["decision"] for r in _lines(c)] == ["launched"] * 3


def test_feed_off_writes_nothing(tmp_path, spawned):
    cfg = _cfg(tmp_path, semparse_feed=False)
    c = _cache(tmp_path, cfg)
    assert pcm.feed_rows([("a", "x is a y", 1.0)], cfg, cache=c) is None
    assert _lines(c) == []


def test_missing_dir_is_not_created(tmp_path):
    d = str(tmp_path / "nowhere")
    assert pcm.record_launch(d, "error", error="X") is False and not os.path.exists(d)


def test_record_never_raises(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    c = _cache(tmp_path, cfg)

    def broken(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(rc, "append_jsonl", broken)
    monkeypatch.setattr(rc, "busy", lambda pidfile, max_age=None: False)
    assert pcm.launch_worker(c, cfg) is None                       # nothing pending; the failed record is ignored


def test_size_capped(tmp_path, monkeypatch):
    monkeypatch.setattr(pcm, "LAUNCH_LOG_MAX_BYTES", 2000)
    d = str(tmp_path)
    for i in range(200):
        pcm.record_launch(d, "nothing_pending", 0, 10, "live", now=1000.0 + i)
    p = os.path.join(d, pcm.LAUNCH_LOG)
    assert os.path.getsize(p) <= 2000 + 200 and os.path.getsize(p + ".1") <= 2000 + 200
    assert not os.path.exists(p + ".2")


def test_return_values_match_the_old_launcher(tmp_path, monkeypatch):
    """Same inputs, same result as ddd2096's launch_worker (re-implemented here verbatim, minus the record)."""
    def old(cache, cfg=None, pending=None):
        if rc.busy(cache.pidfile, pcm.WORKER_MAX_AGE) or cache.budget() <= 0:
            return None
        if (cache.pending() if pending is None else pending) == 0:
            return None
        return rc.spawn_worker(cfg, pcm.WORKER_MODULE, [], cache.pidfile)

    monkeypatch.setattr(rc, "spawn_worker", lambda *a, **k: 7)
    for busy in (False, True):
        monkeypatch.setattr(rc, "busy", lambda pidfile, max_age=None, b=busy: b)
        for per_hour in (0, 5):
            for n_items in (0, 2):
                for pend in (None, 0, 3):
                    sub = tmp_path / ("%s-%d-%d-%s" % (busy, per_hour, n_items, pend))
                    cfg = _cfg(sub)
                    c = ParseCache(str(sub / "c"), cfg=cfg, per_hour=per_hour)
                    os.makedirs(c.d, exist_ok=True)
                    if n_items:
                        c.enqueue([("i%d" % i, "note %d" % i, 1.0) for i in range(n_items)])
                    assert pcm.launch_worker(c, cfg, pending=pend) == old(c, cfg, pending=pend)
