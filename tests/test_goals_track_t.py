"""Track T: (1) automated runs keep display-only message suggestions in latest.json; (2) re-ask counts only what
was rendered into a prompt block (asked.jsonl).  Synthetic only: made-up people, ids and notes."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wmtm import runtime_config as rc            # noqa: E402
from wmtm.goals import engine, actions           # noqa: E402
from wmtm import goal_prompt as gp               # noqa: E402

NOW = 1_800_000_000.0
D = 86400.0
MAP = {"9001": "quill", "9002": "wren", "9999": "botty"}
Q = "Open question for Quill: should the widget7 gadget be renamed to sprocket9?"
OK = {"status": "ok", "queries": []}


def _it(i, text, age_d=2.0):
    return {"id": "syn-%d" % i, "content": text, "sti": 1.0, "source_type": "recalled", "origin_ts": NOW - age_d * D}


def _cfg(tmp_path, **kw):
    (tmp_path / "completed").mkdir(exist_ok=True)
    return dict(rc.resolve(None, environ={}), goalchainer=True, runtime_dir=str(tmp_path / "rt"),
                goal_requests_dir=str(tmp_path / "completed"), semparse_dir=str(tmp_path / "none"),
                speaker_map=MAP, speaker_self="botty", **kw)


def _g(tmp_path, name):
    return tmp_path / "rt" / "goalchainer" / name


def _lines(p):
    return [json.loads(l) for l in open(p)] if p.exists() else []


# ── fix 1 ───────────────────────────────────────────────────────────────────────────────────────────────────────
def test_fix1_automated_run_keeps_display_only_message_suggestions(tmp_path):
    cfg = _cfg(tmp_path, goal_prompt=True)
    r = engine.run_shadow([_it(1, Q)], OK, cfg, source="automated", now=NOW)
    assert r["status"] == "ok" and r["autonomous"] is True and r["display_only"] >= 1
    # still never acted on / logged: no message action in proposals.jsonl
    assert not any(l["action"] in actions.MESSAGE_ACTIONS for l in _lines(_g(tmp_path, "proposals.jsonl")))
    lat = json.load(open(_g(tmp_path, "latest.json")))
    msg = [p for p in lat["proposals"] if p["action"] in actions.MESSAGE_ACTIONS]
    assert msg and all(p["display_only"] is True and p["who"] == "quill" and p["topic"] for p in msg)
    out = gp.render(cfg, now=NOW + 10, speaker="quill")
    assert out and "widget7" in out
    assert gp.render(cfg, now=NOW + 10, speaker="wren") is None


def test_fix1_display_only_stays_tied_to_run_time_and_failed_run_clears(tmp_path):
    cfg = _cfg(tmp_path, goal_prompt=True)
    engine.run_shadow([_it(1, Q)], OK, cfg, source="automated", now=NOW)
    assert gp.render(cfg, now=NOW + 900, speaker="quill")
    assert gp.render(cfg, now=NOW + 901, speaker="quill") is None          # fresh relative to the data's run
    engine.run_shadow([_it(1, Q)], {"status": "error"}, cfg, source="automated", now=NOW + 60)
    assert json.load(open(_g(tmp_path, "latest.json")))["proposals"] == []
    assert gp.render(cfg, now=NOW + 70, speaker="quill") is None


def test_fix1_cycle_run_unchanged_no_display_only_flag(tmp_path):
    cfg = _cfg(tmp_path)
    r = engine.run_shadow([_it(1, Q)], OK, cfg, source="cycle", now=NOW)
    assert r["logged"] >= 1 and "display_only" not in r
    lat = json.load(open(_g(tmp_path, "latest.json")))
    assert lat["proposals"] and not any(p.get("display_only") for p in lat["proposals"])


# ── fix 2 ───────────────────────────────────────────────────────────────────────────────────────────────────────
def test_fix2_logged_is_not_asked(tmp_path):
    cfg = _cfg(tmp_path, goal_repeat_s=60.0)
    r1 = engine.run_shadow([_it(1, Q)], OK, cfg, source="cycle", now=NOW)
    r2 = engine.run_shadow([_it(1, Q)], OK, cfg, source="cycle", now=NOW + 3600)
    assert r1["logged"] >= 1 and r2["history"] == 0 and r2["logged"] >= 1 and r2["suppressed"] == r1["suppressed"]
    assert not _g(tmp_path, "asked.jsonl").exists()


def test_fix2_rendered_counts_as_asked_and_blocks_reask(tmp_path):
    cfg = _cfg(tmp_path, goal_prompt=True, goal_repeat_s=60.0)
    engine.run_shadow([_it(1, Q)], OK, cfg, source="automated", now=NOW)
    assert gp.render(cfg, now=NOW + 5, speaker="quill")                     # record=False: preview, not asked
    assert not _g(tmp_path, "asked.jsonl").exists()
    assert gp.render(cfg, now=NOW + 5, speaker="quill", record=True)
    a = _lines(_g(tmp_path, "asked.jsonl"))
    assert a and all(x["who"] == "quill" and x["shown_at"] == NOW + 5 and x["topic"] and x["id"] for x in a)
    r = engine.run_shadow([_it(1, Q)], OK, cfg, source="automated", now=NOW + 3600)
    assert r["history"] >= 1 and r["display_only"] == 0                      # same person+topic within reask_s
    assert gp.render(cfg, now=NOW + 3605, speaker="quill") is None
    r = engine.run_shadow([_it(1, Q)], OK, cfg, source="automated", now=NOW + 3 * D + 60)
    assert r["history"] == 0 and r["display_only"] >= 1                       # reask window over


def test_fix2_goal_prompt_off_nothing_counts_as_asked(tmp_path):
    from wmtm import context as C
    cfg = _cfg(tmp_path)                                                      # goal_prompt off (default)
    engine.run_shadow([_it(1, Q)], OK, cfg, source="automated", now=NOW)
    assert gp.render(cfg, now=NOW + 5, speaker="quill", record=True) is None

    class It:
        source_type = "user"; content = "hi"; source_meta = {"user_id": 9001}

    class S:
        def get_active_set(self):
            return [It()]
    core = C._format_context_core
    C._format_context_core = lambda *a, **k: ("[WMTM ctx]", [])
    try:
        t, _ = C.format_context(S(), 1, cfg, None, request="hi")
    finally:
        C._format_context_core = core
    assert t == "[WMTM ctx]" and not _g(tmp_path, "asked.jsonl").exists()
    r = engine.run_shadow([_it(1, Q)], OK, cfg, source="automated", now=NOW + 3600)
    assert r["history"] == 0


def test_fix2_live_user_path_records(tmp_path):
    from wmtm import context as C
    cfg = _cfg(tmp_path, goal_prompt=True)
    import time
    engine.run_shadow([_it(1, Q)], OK, cfg, source="automated", now=time.time())

    class It:
        source_type = "user"; content = "hi"; source_meta = {"user_id": 9001}

    class S:
        def get_active_set(self):
            return [It()]
    core = C._format_context_core
    C._format_context_core = lambda *a, **k: ("[WMTM ctx]", [])
    try:
        t, _ = C.format_context(S(), 1, cfg, None, request="hi")
        t2, _ = C.format_context(S(), 1, cfg, None, request=None)           # automated turn: nothing recorded
    finally:
        C._format_context_core = core
    assert "Goal suggestions" in t and "Goal suggestions" not in (t2 or "")
    assert len({x["shown_at"] for x in _lines(_g(tmp_path, "asked.jsonl"))}) == 1


def test_asked_constant_matches_engine():
    assert gp.ASKED == engine.ASKED
