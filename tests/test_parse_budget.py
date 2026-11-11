"""t-2026-11-10-wmtm-shared-parse-count-v2: fixed parse-call shares (live 10/h, all tasks together 10/h), each
counted across every log of the share.  Synthetic logs and fake LLMs only: 0 real parse calls.

Each acceptance test has a control that fails without the change:
  * two task callers: the same scenario with per-cache counting (each caller counts only its own log, the rule at
    27c1a41 parse_cache.py:141) lets them make 20 calls together;
  * live vs tasks: under the cancelled v1 rule (one pool of 20, tasks get what live leaves) live's 15 calls would
    leave tasks 5, not 10.
"""
import hashlib
import json
import os
import threading
import time

import pytest

from wmtm import parse_budget as pb
from wmtm import runtime_config as rc
from wmtm.parse_cache import ParseCache, process_queue


class _Res:
    def __init__(self, accepted=(), error=None):
        self.accepted, self.rejected, self.error, self.queries = list(accepted), [], error, []


class _Adapter:
    """Stands in for SemParseAdapter: one llm call per item; an llm exception becomes 'llm error: ...'."""
    prompt_sha256 = "0" * 64

    def __init__(self, llm):
        self.llm = llm

    def parse_item(self, item_id, content):
        try:
            self.llm("SYS", content)
        except Exception as e:                      # noqa: BLE001  (as SemParseAdapter.parse_item)
            return _Res(error="llm error: %s" % e)
        return _Res(accepted=["(: f (Member a b) (STV 1.0 0.9))"])


def _fake_provider(budget, delay=0.0, sent=None):
    """A gated fake provider: the production gate (parse_budget.gated, as upstream_llm uses) around a fake send."""
    def send(system, user):
        if delay:
            time.sleep(delay)
        if sent is not None:
            sent.append(user)
        return "ok"
    return pb.gated(send, budget)


def _cfg(tmp_path, **kw):
    c = rc.resolve(str(tmp_path / "sd"))
    c.update({"parse_budget_dir": str(tmp_path / "budget"), **kw})
    return c


def _task_cache(tmp_path, name, cfg, n_items=12):
    c = ParseCache(str(tmp_path / name / "semparse_cache"), cfg=cfg, per_hour=20)
    c.enqueue([("%s-%d" % (name, i), "synthetic note %s %d" % (name, i), 1.0) for i in range(n_items)])
    return c


def _drain(cache):
    llm = _fake_provider(cache.share)
    return process_queue(cache, llm, adapter=_Adapter(llm), n=50)


def _rows(path):
    return [json.loads(x) for x in open(path, encoding="utf-8")] if os.path.exists(path) else []


# ---------------------------------------------------------------- acceptance 1a: tasks share one count
def test_two_task_callers_never_exceed_task_share(tmp_path):
    cfg = _cfg(tmp_path)
    a, b = _task_cache(tmp_path, "taskA", cfg), _task_cache(tmp_path, "taskB", cfg)
    ra = _drain(a)                       # A alone would use the whole share ...
    rb = _drain(b)                       # ... so B, a different cache with its own log, gets nothing
    assert len(ra) + len(rb) == 10 == cfg["parse_share_tasks_per_hour"]
    assert len(rb) == 0 and b.last_stop["status"] == "share_full" and b.last_stop["remaining"] == 0
    assert a.share.used() == b.share.used() == 10           # one count, seen from either task
    led = _rows(a.share.ledger)
    assert len(led) == 10 and {r["log"] for r in led} == {a.log_path}
    assert all(r.get("call_ids") for r in _rows(a.log_path))  # cache rows join the ledger: counted once


def test_two_task_callers_interleaved_and_concurrent(tmp_path):
    cfg = _cfg(tmp_path)
    a, b = _task_cache(tmp_path, "taskA", cfg), _task_cache(tmp_path, "taskB", cfg)
    sent = []
    la, lb = _fake_provider(a.share, 0.01, sent), _fake_provider(b.share, 0.01, sent)
    out = []
    ts = [threading.Thread(target=lambda c=c, l=l: out.extend(process_queue(c, l, adapter=_Adapter(l), n=50)))
          for c, l in ((a, la), (b, lb))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len(sent) == 10 and len(out) == 10              # never more than the share across both callers
    assert len(_rows(a.share.ledger)) == 10


def test_control_per_cache_counting_lets_two_tasks_reach_20(tmp_path):
    """Control: the same two callers, each counting only its own log (separate budget dirs = the 27c1a41 rule)."""
    out = 0
    for name in ("taskA", "taskB"):
        cfg = _cfg(tmp_path, parse_budget_dir=str(tmp_path / ("own-" + name)))
        out += len(_drain(_task_cache(tmp_path, name, cfg)))
    assert out == 20 > 10                                   # what the shared count prevents


def test_task_counts_registered_logs_without_ledger(tmp_path):
    """A task log written by older code (rows without call_ids) still counts against the task share."""
    cfg = _cfg(tmp_path)
    old = tmp_path / "old_tool" / "parse_log.jsonl"
    old.parent.mkdir(parents=True)
    now = time.time()
    old.write_text("".join(json.dumps({"ts": now - 60 * i, "status": "ok"}) + "\n" for i in range(7))
                   + json.dumps({"ts": now - 4000, "status": "ok"}) + "\n")      # outside the hour
    bud = pb.ParseBudget("task", cfg=cfg)
    bud.register_log(str(old))
    assert bud.used() == 7 and bud.remaining() == 3
    assert len(_drain(_task_cache(tmp_path, "taskC", cfg))) == 3


# ---------------------------------------------------------------- acceptance 1b: live does not use the task share
def _live_dir(tmp_path, base=4, ctx=5, spk=6, ids=False):
    root = tmp_path / "bot" / "memory" / "_wmtm_shadow" / "semparse_cache"
    now = time.time()
    for sub, n in (("", base), ("ctx1", ctx), ("spk1", spk)):
        d = root / sub if sub else root
        d.mkdir(parents=True, exist_ok=True)
        (d / "parse_log.jsonl").write_text("".join(json.dumps({"ts": now - 30 * (i + 1), "status": "ok"}) + "\n"
                                                   for i in range(n)))
    return root


def _snapshot(root):
    out = {}
    for dp, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(dp, f)
            out[p] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return out


def test_live_calls_do_not_use_task_share(tmp_path):
    root = _live_dir(tmp_path)                               # 15 live calls in the hour (rc2 rows, no call ids)
    cfg = _cfg(tmp_path, parse_live_dir=str(root))
    before = _snapshot(root)
    live = pb.ParseBudget("live", cfg=cfg)
    assert live.used() == 15 and live.remaining() == 0       # counted across base + ctx1 + spk1 together
    task = pb.ParseBudget("task", cfg=cfg)
    assert task.used() == 0 and task.remaining() == 10
    assert len(_drain(_task_cache(tmp_path, "taskA", cfg))) == 10
    assert _snapshot(root) == before                         # tasks read the live logs, never write them
    st = pb.host_status(cfg)
    assert st["live"]["used_last_hour"] == 15 and st["tasks"]["used_last_hour"] == 10
    assert _snapshot(root) == before


def test_control_v1_pool_rule_would_starve_tasks(tmp_path):
    """Control: the cancelled v1 rule (20 per hour shared, tasks get what live leaves) gives tasks 5 here."""
    root = _live_dir(tmp_path)
    cfg = _cfg(tmp_path, parse_live_dir=str(root))
    v1_task_room = max(0, 20 - pb.ParseBudget("live", cfg=cfg).used() - pb.ParseBudget("task", cfg=cfg).used())
    assert v1_task_room == 5 != pb.ParseBudget("task", cfg=cfg).remaining()


def test_live_share_counts_across_subcaches(tmp_path):
    """Each live log alone is under 10, together they are 9: one call left for live, whichever sub-cache asks."""
    root = _live_dir(tmp_path, base=3, ctx=3, spk=3)
    cfg = _cfg(tmp_path, parse_role="live")
    spk = ParseCache(str(root / "spk1"), cfg=cfg, per_hour=20)
    assert spk.share.role == "live" and spk.share.used() == 9 and spk.budget() == 1
    spk.enqueue([("n%d" % i, "synthetic live note %d" % i, 1.0) for i in range(5)])
    assert len(_drain(spk)) == 1 and spk.last_stop["status"] == "share_full"
    base = ParseCache(str(root), cfg=cfg, per_hour=20)
    assert base.budget() == 0                                # the base cache sees spk1's call too
    # control: the 27c1a41 rule (own log only) would still give the base cache 17 calls
    assert base.per_hour - base.used_last_hour() == 17


def test_task_cache_inside_live_dir_is_refused(tmp_path):
    root = _live_dir(tmp_path)
    cfg = _cfg(tmp_path, parse_live_dir=str(root))
    before = _snapshot(root)
    with pytest.raises(pb.LiveDirWriteRefused):
        ParseCache(str(root / "spk1"), cfg=cfg).share
    with pytest.raises(pb.LiveDirWriteRefused):
        pb.ParseBudget("task", cfg=cfg).register_log(str(root / "parse_log.jsonl"))
    assert _snapshot(root) == before


# ---------------------------------------------------------------- full share: wait or stop
def test_full_share_stops_without_recording_or_sending(tmp_path):
    cfg = _cfg(tmp_path, parse_share_tasks_per_hour=2)
    c = _task_cache(tmp_path, "taskA", cfg, n_items=5)
    sent = []
    llm = _fake_provider(c.share, sent=sent)
    out = process_queue(c, llm, adapter=_Adapter(llm), n=50)
    assert len(out) == len(sent) == 2 and c.pending() == 3   # unparsed items stay queued, no attempt recorded
    assert c.last_stop["status"] == "share_full"
    with pytest.raises(pb.ShareFull, match=pb.SHARE_FULL):
        llm("SYS", "x")                                      # the gate itself refuses (raced pre-check)
    assert len(sent) == 2


def test_acquire_waits_for_room(tmp_path):
    cfg = _cfg(tmp_path, parse_share_tasks_per_hour=1)
    b = pb.ParseBudget("task", cfg=cfg)
    clock = [1_000_000.0]
    b.reserve(now=clock[0])
    slept = []

    def sleep(s):
        slept.append(s); clock[0] += s
    assert b.acquire(wait=True, max_wait_s=7200, clock=lambda: clock[0], sleep=sleep)
    assert 3600 <= sum(slept) <= 3602                        # waited for the oldest call to leave the hour
    clock[0] += 1
    with pytest.raises(pb.ShareFull):
        b.acquire(wait=True, max_wait_s=10, clock=lambda: clock[0], sleep=sleep)


def test_shares_are_config_values():
    c = rc.resolve(None, environ={"WMTM_PARSE_SHARE_LIVE": "15", "WMTM_PARSE_SHARE_TASKS": "25"})
    assert c["parse_share_live_per_hour"] == 15 and c["parse_share_tasks_per_hour"] == 25
    d = rc.resolve(None, environ={})
    assert d["parse_share_live_per_hour"] == 10 and d["parse_share_tasks_per_hour"] == 10
    assert d["parse_role"] == "task"
    assert rc.resolve(None, environ={"WMTM_PARSE_ROLE": "bogus"})["parse_role"] == "task"


def test_mocked_rows_and_tail_reading(tmp_path):
    cfg = _cfg(tmp_path)
    p = tmp_path / "t" / "parse_log.jsonl"
    p.parent.mkdir()
    now = time.time()
    p.write_text(json.dumps({"ts": now, "mocked": True, "call_ids": []}) + "\n" + "{torn\n"
                 + json.dumps({"ts": now, "call_ids": []}) + "\n")
    b = pb.ParseBudget("task", cfg=cfg)
    b.register_log(str(p))
    assert b.used() == 0                                     # mocked / call-free rows are not gateway calls


def test_legacy_adapter_gateway_client_is_counted(tmp_path, monkeypatch):
    """The old direct client in semparse_adapter is gated too (no parse tool can call uncounted); fake HTTP only."""
    import io
    from wmtm import semparse_adapter as sa
    sent = []

    def fake_urlopen(req, timeout=None):
        sent.append(req.full_url)
        return io.BytesIO(json.dumps({"choices": [{"message": {"content": "ok"}}], "usage": {}}).encode())
    monkeypatch.setattr(sa.urllib.request, "urlopen", fake_urlopen)
    cfg = _cfg(tmp_path, parse_share_tasks_per_hour=2)
    llm = sa.gateway_llm("http://127.0.0.1:9/v1", model="m", key="k", budget=pb.ParseBudget("task", cfg=cfg))
    assert llm("s", "u") == "ok" and llm("s", "u") == "ok" and len(llm.call_ids) == 2
    with pytest.raises(pb.ShareFull):
        llm("s", "u")
    assert len(sent) == 2 and len(_rows(llm.budget.ledger)) == 2
    d = sa.gateway_llm("http://127.0.0.1:9/v1", model="m", key="k")      # no budget given: default task share
    assert d.budget.role == "task" and d("s", "u") == "ok" and len(_rows(d.budget.ledger)) == 1
