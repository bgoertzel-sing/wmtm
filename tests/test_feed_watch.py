"""tools/feed_watch.py (L-03, t-2026-11-15-wmtm-feed-watch): OK / ALERT / ERROR on synthetic state.

The check must never say OK while items are queued, the budget is free and no run is recorded for 2 h."""
import importlib.util
import json
import os
import subprocess
import sys
import time

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("feed_watch", os.path.join(HERE, "..", "tools", "feed_watch.py"))
fw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fw)

NOW = 1_800_000_000.0
H = 3600.0
SECRET = "zz-sentinel queued note text"


def _w(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(json.dumps(r) + "\n" for r in rows)


class Bot:
    """A synthetic bot memory dir shaped like the live one (speaker_link -> spk1, live share in the root)."""

    def __init__(self, tmp_path, **flags):
        self.sd = str(tmp_path / "memory")
        self.root = os.path.join(self.sd, "_wmtm_shadow", "semparse_cache")
        self.d = os.path.join(self.root, "spk1")
        os.makedirs(self.d, exist_ok=True)
        self.flags = {"semparse_feed": True, "speaker_link": True, "parse_role": "live",
                      "parse_share_live_per_hour": 20, "parse_cap_per_hour": 20, "parse_live_dir": self.root}
        self.flags.update(flags)
        self.write_flags()
        self.status = str(tmp_path / "status")

    def write_flags(self):
        with open(os.path.join(self.sd, "_wmtm_flags.json"), "w") as fh:
            json.dump(self.flags, fh)

    def queue(self, n, cached=0, first_seen=NOW - 5 * H):
        q = {"h%03d" % i: {"item_id": "i%d" % i, "content": SECRET, "sti": 1.0, "first_seen": first_seen,
                           "attempts": 0, "chars": len(SECRET)} for i in range(n)}
        with open(os.path.join(self.d, "queue.json"), "w") as fh:
            json.dump(q, fh)
        _w(os.path.join(self.d, "cache.jsonl"), [{"hash": "h%03d" % i, "status": "ok", "atoms": []}
                                                 for i in range(cached)])

    def run_at(self, ts, end=None):
        _w(os.path.join(self.d, "worker_runs.jsonl"), [{"ts": ts - 300, "end_ts": end or ts, "status": "ok"}])

    def ledger(self, n, ts=NOW - 600):
        _w(os.path.join(self.root, "share_ledger.jsonl"),
           [{"ts": ts, "call_id": "c%d" % i, "role": "live"} for i in range(n)])

    def judge(self, **kw):
        return fw.judge(self.sd, now=kw.pop("now", NOW), **kw)

    def main(self, *extra):
        return fw.main(["--state-dir", self.sd, "--now", str(NOW), "--status-dir", self.status] + list(extra))


# ------------------------------------------------------------------ OK cases
def test_idle_empty_queue_is_ok(tmp_path):
    b = Bot(tmp_path); b.queue(0); b.run_at(NOW - 30 * H)
    r = b.judge()
    assert (r["verdict"], r["code"]) == ("OK", "idle")


def test_idle_everything_cached_is_ok(tmp_path):
    b = Bot(tmp_path); b.queue(3, cached=3); b.run_at(NOW - 30 * H)
    assert b.judge()["code"] == "idle"


def test_no_queue_file_is_idle(tmp_path):
    b = Bot(tmp_path)
    assert b.judge()["code"] == "idle"


def test_recent_run_is_ok(tmp_path):
    b = Bot(tmp_path); b.queue(4); b.run_at(NOW - 1 * H)
    assert (b.judge()["verdict"], b.judge()["code"]) == ("OK", "recent_run")


def test_budget_full_via_ledger_is_ok(tmp_path):
    b = Bot(tmp_path); b.queue(4); b.run_at(NOW - 5 * H); b.ledger(20)
    r = b.judge()
    assert (r["verdict"], r["code"]) == ("OK", "budget_full") and r["facts"]["share"]["used_last_hour"] == 20


def test_budget_counts_log_rows_without_call_ids_and_joins_ids(tmp_path):
    b = Bot(tmp_path); b.queue(4); b.run_at(NOW - 5 * H); b.ledger(10)
    rows = [{"ts": NOW - 100, "call_ids": ["c%d" % i]} for i in range(10)]          # joined: no double count
    rows += [{"ts": NOW - 100} for _ in range(9)] + [{"ts": NOW - 100, "mocked": True}]
    _w(os.path.join(b.root, "parse_log.jsonl"), rows)
    r = b.judge()
    assert r["facts"]["share"]["used_last_hour"] == 19 and r["verdict"] == "ALERT"   # 1 left: still free
    _w(os.path.join(b.root, "ctx1", "parse_log.jsonl"), [{"ts": NOW - 50}])
    assert b.judge()["code"] == "budget_full"


def test_own_cap_full_is_ok(tmp_path):
    b = Bot(tmp_path, parse_cap_per_hour=3); b.queue(4); b.run_at(NOW - 5 * H)
    _w(os.path.join(b.d, "parse_log.jsonl"), [{"ts": NOW - 10, "call_ids": []} for _ in range(3)])
    assert b.judge()["code"] == "budget_full"


def test_old_ledger_rows_do_not_hold_the_budget(tmp_path):
    b = Bot(tmp_path); b.queue(4); b.run_at(NOW - 5 * H); b.ledger(20, ts=NOW - 2 * H)
    assert b.judge()["verdict"] == "ALERT"


def test_feed_off_is_ok(tmp_path):
    b = Bot(tmp_path, semparse_feed=False); b.queue(4)
    assert (b.judge()["verdict"], b.judge()["code"]) == ("OK", "feed_off")


@pytest.fixture
def fake_worker():
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", "wmtm.workers.semparse_feed"])
    yield p
    p.kill(); p.wait()


def test_running_young_worker_is_ok(tmp_path, fake_worker):
    t = time.time()                                              # pidfile mtime is real time here
    b = Bot(tmp_path); b.queue(4, first_seen=t - 5 * H); b.run_at(t - 30 * H)
    pf = os.path.join(b.d, "worker.pid")
    open(pf, "w").write(str(fake_worker.pid))
    r = b.judge(now=t + 600)
    assert (r["verdict"], r["code"]) == ("OK", "running")
    r = b.judge(now=t + 3 * H)                                   # the same worker 3 h on: hung, not running
    assert r["verdict"] == "ALERT" and "hung" in r["reasons"][0]


def test_pid_of_some_other_process_is_not_a_worker(tmp_path):
    t = time.time()
    b = Bot(tmp_path); b.queue(4, first_seen=t - 5 * H); b.run_at(t - 30 * H)
    open(os.path.join(b.d, "worker.pid"), "w").write(str(os.getpid()))    # alive, but not a wmtm worker
    r = b.judge(now=t + 60)
    assert r["verdict"] == "ALERT" and r["facts"]["worker"]["alive"] is False


# ------------------------------------------------------------------ ALERT cases
def test_queued_free_no_run_2h_is_alert(tmp_path):
    b = Bot(tmp_path); b.queue(4, cached=1); b.run_at(NOW - 2 * H - 1)
    r = b.judge()
    assert (r["verdict"], r["code"]) == ("ALERT", "stalled")
    assert r["facts"]["pending"] == 3 and r["facts"]["budget_left"] == 20


def test_queued_free_never_ran_is_alert(tmp_path):
    b = Bot(tmp_path); b.queue(1)
    assert b.judge()["code"] == "stalled"


def test_last_run_found_in_rotated_file(tmp_path):
    b = Bot(tmp_path); b.queue(2)
    _w(os.path.join(b.d, "worker_runs.jsonl.1"), [{"ts": NOW - 1800, "end_ts": NOW - 1700}])
    assert b.judge()["code"] == "recent_run"


def test_stall_window_is_configurable(tmp_path):
    b = Bot(tmp_path); b.queue(2); b.run_at(NOW - 3 * H)
    assert b.judge(stall_s=4 * H)["verdict"] == "OK" and b.judge(stall_s=2 * H)["verdict"] == "ALERT"


def test_root_cache_used_without_speaker_link(tmp_path):
    b = Bot(tmp_path, speaker_link=False); b.queue(2)              # spk1 queue is not the active one
    assert b.judge()["code"] == "idle"
    with open(os.path.join(b.root, "queue.json"), "w") as fh:
        json.dump({"hx": {"first_seen": NOW - 9 * H}}, fh)
    assert b.judge()["code"] == "stalled"


def test_hook_error_streak_alerts_even_with_empty_queue(tmp_path):
    b = Bot(tmp_path); b.queue(0); b.run_at(NOW - 30 * H)
    _w(os.path.join(b.d, "launch_decisions.jsonl"),
       [{"ts": NOW - 4000, "decision": "nothing_pending"}] +
       [{"ts": NOW - 900 * i, "decision": "error", "error": "KeyError"} for i in (3, 2, 1)])
    r = b.judge()
    assert (r["verdict"], r["code"]) == ("ALERT", "hook_errors") and "KeyError" in r["reasons"][0]


def test_error_then_success_is_not_a_streak(tmp_path):
    b = Bot(tmp_path); b.queue(0); b.run_at(NOW - 30 * H)
    _w(os.path.join(b.d, "launch_decisions.jsonl"),
       [{"ts": NOW - 900 * i, "decision": "error", "error": "KeyError"} for i in (4, 3, 2)] +
       [{"ts": NOW - 60, "decision": "nothing_pending"}])
    assert b.judge()["code"] == "idle"


# ------------------------------------------------------------------ ERROR cases (never OK)
@pytest.mark.parametrize("change,code", [
    ({"parse_role": "task"}, "not_live_share"),
    ({"parse_role": None}, "not_live_share"),
    ({"parse_share_live_per_hour": 0}, "budget_never_free"),
    ({"parse_cap_per_hour": 0}, "budget_never_free"),
    ({"parse_share_live_per_hour": "lots"}, "bad_flag"),
])
def test_misconfigured_share_is_error(tmp_path, change, code):
    b = Bot(tmp_path); b.queue(0); b.flags.update(change); b.write_flags()
    r = b.judge()
    assert (r["verdict"], r["code"]) == ("ERROR", code)


def test_share_dir_elsewhere_is_error(tmp_path):
    b = Bot(tmp_path); b.queue(0)
    other = tmp_path / "other"; other.mkdir()
    b.flags["parse_live_dir"] = str(other); b.write_flags()
    assert b.judge()["code"] == "share_dir_mismatch"
    b.flags["parse_live_dir"] = str(tmp_path / "missing"); b.write_flags()
    assert b.judge()["code"] == "share_dir_missing"


def test_share_dir_unset_defaults_to_the_feed_root(tmp_path):
    b = Bot(tmp_path); b.queue(2); b.run_at(NOW - 3 * H)
    del b.flags["parse_live_dir"]; b.write_flags()
    assert b.judge()["code"] == "stalled"


@pytest.mark.parametrize("text", ["{not json", "[1, 2]", ""])
def test_bad_flags_file_is_error(tmp_path, text):
    b = Bot(tmp_path)
    open(os.path.join(b.sd, "_wmtm_flags.json"), "w").write(text)
    assert b.judge()["verdict"] == "ERROR"


def test_missing_flags_and_missing_cache_dir_are_errors(tmp_path):
    assert fw.judge(str(tmp_path / "nobot"), now=NOW)["code"] == "flags_unreadable"
    b = Bot(tmp_path, speaker_link=False, semparse_context=True)   # ctx1 does not exist
    assert b.judge()["code"] == "cache_dir_missing"


def test_corrupt_queue_is_error(tmp_path):
    b = Bot(tmp_path); b.run_at(NOW - 30 * H)
    open(os.path.join(b.d, "queue.json"), "w").write("{\"h1\": ")
    assert b.judge()["code"] == "queue_corrupt"


def test_future_ledger_rows_are_error(tmp_path):
    b = Bot(tmp_path); b.queue(2); b.ledger(20, ts=NOW + 5 * H)
    assert b.judge()["code"] == "future_rows"


def test_never_ok_when_queued_free_and_quiet(tmp_path):
    """The order's 'useless if': sweep the states that matter; queued + free + quiet 2 h is never OK."""
    for i, (n, cached, ledger, ran) in enumerate([(1, 0, 0, None), (5, 4, 19, 2.01), (50, 0, 0, 100),
                                                   (2, 0, 10, 2.5)]):
        b = Bot(tmp_path / str(i)); b.queue(n, cached=cached); b.ledger(ledger)
        if ran is not None:
            b.run_at(NOW - ran * H)
        assert b.judge()["verdict"] == "ALERT", (n, cached, ledger, ran)


# ------------------------------------------------------------------ CLI, exit codes, alert path, no note text
def test_exit_codes_and_status(tmp_path, capsys):
    b = Bot(tmp_path); b.queue(0)
    assert b.main() == 0
    b.queue(3)
    assert b.main() == 1
    b.flags["parse_role"] = "task"; b.write_flags()
    assert b.main() == 3
    last = json.load(open(os.path.join(b.status, "last.json")))
    assert last["verdict"] == "ERROR" and last["alert"] is None            # no --alert: dry run never files
    assert len(open(os.path.join(b.status, "history.jsonl")).readlines()) == 3


def _fake_hive(tmp_path):
    log = tmp_path / "proposals.jsonl"
    exe = tmp_path / "hive-task"
    exe.write_text("#!%s\nimport json, sys\nopen(%r, 'a').write(json.dumps(sys.argv[1:]) + '\\n')\nprint('OK: proposed')\n"
                   % (sys.executable, str(log)))
    exe.chmod(0o755)
    return str(exe), log


def test_alert_files_one_proposal_and_dedupes(tmp_path):
    exe, log = _fake_hive(tmp_path)
    b = Bot(tmp_path); b.queue(3); b.run_at(NOW - 3 * H)
    assert b.main("--alert", "--hive-task", exe) == 1
    (args,) = [json.loads(x) for x in open(log)]
    assert args[0] == "propose" and args[2].startswith("ALERT pop-os: parse feed stalled (")
    assert "For andy" in args[2]
    assert b.main("--alert", "--hive-task", exe) == 1                      # same finding: not re-filed
    assert len(open(log).readlines()) == 1
    b.queue(0)
    assert b.main("--alert", "--hive-task", exe) == 0                      # back to OK resets
    b.queue(3)
    assert b.main("--alert", "--hive-task", exe) == 1
    assert len(open(log).readlines()) == 2


def test_error_alert_and_test_label(tmp_path):
    exe, log = _fake_hive(tmp_path)
    b = Bot(tmp_path, parse_share_live_per_hour=0)
    assert b.main("--alert", "--hive-task", exe, "--test-label", "unit") == 3
    (args,) = [json.loads(x) for x in open(log)]
    assert args[2].startswith("TEST (unit)") and "ALERT pop-os: parse feed stalled?" in args[2]


def test_failed_proposal_is_retried_next_run(tmp_path):
    b = Bot(tmp_path); b.queue(3)
    assert b.main("--alert", "--hive-task", str(tmp_path / "no-such-hive-task")) == 1
    last = json.load(open(os.path.join(b.status, "last.json")))
    assert last["alert"]["rc"] != 0 and last["last_alert"] is None


def test_no_note_text_anywhere(tmp_path, capsys):
    exe, log = _fake_hive(tmp_path)
    b = Bot(tmp_path); b.queue(3); b.run_at(NOW - 3 * H)
    b.main("--alert", "--hive-task", exe, "--json")
    out = capsys.readouterr().out
    blobs = [out, open(log).read()] + [open(os.path.join(b.status, f)).read() for f in os.listdir(b.status)]
    assert not any(SECRET in x or "sentinel" in x for x in blobs)


def test_runs_as_a_script_without_wmtm_on_the_path(tmp_path):
    b = Bot(tmp_path); b.queue(2); b.run_at(NOW - 3 * H)
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    p = subprocess.run([sys.executable, "-S", "-I", os.path.join(HERE, "..", "tools", "feed_watch.py"),
                        "--state-dir", b.sd, "--now", str(NOW), "--status-dir", b.status],
                       capture_output=True, text=True, env=env, cwd=str(tmp_path))
    assert p.returncode == 1 and "ALERT" in p.stdout and "stalled" in p.stdout


def test_does_not_import_wmtm():
    src = open(os.path.join(HERE, "..", "tools", "feed_watch.py"), encoding="utf-8").read()
    imports = [ln.strip() for ln in src.splitlines() if ln.strip().startswith(("import ", "from "))]
    assert imports and not any("wmtm" in ln for ln in imports)
    assert "importlib" not in src and "__import__" not in src
