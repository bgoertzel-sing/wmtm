"""t-2026-11-24-wmtm-s5-ops: synthetic tests for scripts/check_live_flags_drift.py and scripts/check_live_triggers.py."""
import importlib.util, json, os, time

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, "..", "scripts", name + ".py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


D = _load("check_live_flags_drift")
T = _load("check_live_triggers")


def test_repo_flags_sha():
    import hashlib
    raw = open(os.path.join(HERE, "..", "config", "live-flags.json"), "rb").read()
    assert hashlib.sha256(raw).hexdigest().startswith("f9e59f74")


def test_drift_same_and_drift(tmp_path):
    a = tmp_path / "a.json"; b = tmp_path / "b.json"
    a.write_text('{"x": 1, "y": 2}'); b.write_text('{"x": 1, "y": 2}')
    assert D.compare(str(a), str(b))[0] == 0
    b.write_text('{"x": 1, "y": 3, "z": 0}')
    rc, out = D.compare(str(a), str(b))
    assert rc == 1 and out["only_repo"] == ["z"] and out["value_differs"] == ["y"]
    b.write_text('{"y": 2, "x": 1}')
    rc, out = D.compare(str(a), str(b))
    assert rc == 1 and "note" in out
    assert D.compare(str(a), str(tmp_path / "missing.json"))[0] == 2


def _repos(tmp_path, shadow, admit=(), workers=(), parse=()):
    M = tmp_path / "memory" / "_wmtm_shadow"; P = M / "pc_shadow"; S = M / "semparse_cache" / "sent1"
    P.mkdir(parents=True); S.mkdir(parents=True)
    w = lambda p, rs: p.write_text("".join(json.dumps(r) + "\n" for r in rs))
    w(P / "shadow.jsonl", shadow); w(P / "admit_log.jsonl", admit); w(S / "worker_runs.jsonl", workers)
    w(S / "parse_log.jsonl", parse); (P / "admit.json").write_text("")
    (tmp_path / "memory" / "_wmtm_flags.json").write_text("{}")
    return str(tmp_path)


def _ok(t, **kw):
    r = {"start_ts": t, "status": "ok", "canary": {"ok": True}, "add_fail": 0, "pred_fail": 0, "timeouts": 0, "skipped_budget": 0}
    r.update(kw); return r


def test_idle_states_do_not_fire(tmp_path):
    t = time.time() - 3600
    R = _repos(tmp_path, [_ok(t + i) for i in range(5)],
               admit=[{"ts": t, "status": "ok", "admitted": 5}, {"ts": t + 1, "status": "ok", "admitted": 0}],
               workers=[{"ts": t, "status": "share_full", "err": None}, {"ts": t + 1, "status": "cap_full", "err": None}],
               parse=[{"ts": t + i, "status": "ok", "hash": "ab429cd", "total_tokens": 4290} for i in range(5)])
    out = T.replay(R, t - 10, time.time())
    assert out["fired"] == [] and out["detail"]["admit_full_cap_rows_not_trigger"] == 1


def test_real_faults_fire(tmp_path):
    t = time.time() - 3600
    sh = [_ok(t), _ok(t + 1, status="warm_fail"), _ok(t + 2, status="warm_fail"), _ok(t + 3, add_fail=1),
          _ok(t + 4, timeouts=1), _ok(t + 5, skipped_budget=2)]
    R = _repos(tmp_path, sh, admit=[{"ts": t, "status": "ok", "admitted": 6}],
               parse=[{"ts": t + i, "status": "err", "http_status": 429} for i in range(3)])
    tr = T.replay(R, t - 10, time.time())["triggers"]
    assert tr["T2_shadow_failure"] == 1 and tr["T3_canary"] == 1 and tr["T4_timeouts_budget"] == 1
    assert tr["T5_admission_quality"] == 1 and tr["T6_http_429"] == 1


def test_t6_fires_on_live_parse_log_shape(tmp_path):
    # the live code writes string status + truncated error text, no integer http field
    t = time.time() - 3600
    R = _repos(tmp_path, [_ok(t)], admit=[],
               parse=[{"ts": t + i, "status": "err", "error": "Error code: 429 - rate_limit_error"} for i in range(3)])
    out = T.replay(R, t - 10, time.time())
    assert out["triggers"]["T6_http_429"] == 1 and out["detail"]["http_429_rows"] == 3


def test_t6_ignores_ok_rows_and_non_limit_errors(tmp_path):
    t = time.time() - 20000   # the t + 9000 row must fall inside the replay window
    pl = [{"ts": t, "status": "ok", "error": "429"}, {"ts": t + 1, "status": "err", "error": "timeout"},
          {"ts": t + 2, "status": "err", "error": "Error 429"}, {"ts": t + 9000, "status": "err", "error": "quota exceeded"}]
    R = _repos(tmp_path, [_ok(t)], admit=[], parse=pl)
    out = T.replay(R, t - 10, time.time())
    assert out["triggers"]["T6_http_429"] == 0 and out["detail"]["http_429_rows"] == 2
