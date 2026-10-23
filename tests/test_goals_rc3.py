"""v0.6.0-rc3: (a) display-only suggestions logged to goalchainer/display.jsonl for review (deduped, size-rotated,
never read by re-ask or anything actionable); (b) asked.jsonl size-rotated without losing the re-ask window.
Synthetic only: made-up people, ids and notes."""
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


# ── (a) display.jsonl ───────────────────────────────────────────────────────────────────────────────────────────
def test_display_log_written_by_automated_run_with_proposal_structure(tmp_path):
    cfg = _cfg(tmp_path)                                                      # goal_prompt off: still logged
    r = engine.run_shadow([_it(1, Q)], OK, cfg, source="automated", now=NOW)
    disp = _lines(_g(tmp_path, "display.jsonl"))
    assert r["display_only"] >= 1 and r["display_logged"] == len(disp) >= 1
    for x in disp:
        assert x["display_only"] is True and x["run_id"] == r["run_id"] and x["ts"] == NOW
        assert x["source"] == "automated" and x["who"] == "quill" and x["topic"]
        assert x["action"] in actions.MESSAGE_ACTIONS
        assert set(engine.FIELDS) <= set(x) and "effects" in x
    props = _lines(_g(tmp_path, "proposals.jsonl"))
    assert not any(p.get("display_only") or p["action"] in actions.MESSAGE_ACTIONS for p in props)
    assert {p["id"] for p in props}.isdisjoint({x["id"] for x in disp})
    assert not _g(tmp_path, "asked.jsonl").exists()


def test_display_log_dedupes_within_window_then_relogs(tmp_path):
    # rc2: the display dedupe window is max(goal_repeat_s, goal_reask_s) and works per (person, topic cluster)
    cfg = _cfg(tmp_path, goal_repeat_s=6 * 3600.0, goal_reask_s=6 * 3600.0)
    engine.run_shadow([_it(1, Q)], OK, cfg, source="automated", now=NOW)
    n1 = len(_lines(_g(tmp_path, "display.jsonl")))
    r = engine.run_shadow([_it(1, Q)], OK, cfg, source="automated", now=NOW + 3600)
    assert r["display_only"] >= 1 and r["display_logged"] == 0
    assert len(_lines(_g(tmp_path, "display.jsonl"))) == n1
    r = engine.run_shadow([_it(1, Q)], OK, cfg, source="automated", now=NOW + 6 * 3600 + 1)
    assert r["display_logged"] == n1 and len(_lines(_g(tmp_path, "display.jsonl"))) == 2 * n1


def test_display_log_new_text_logged_inside_window(tmp_path):
    cfg = _cfg(tmp_path)
    engine.run_shadow([_it(1, Q)], OK, cfg, source="automated", now=NOW)
    n1 = len(_lines(_g(tmp_path, "display.jsonl")))
    q2 = "Open question for Quill: should the cog3 part ship before the gizmo4 review?"
    r = engine.run_shadow([_it(1, Q), _it(2, q2)], OK, cfg, source="automated", now=NOW + 60)
    assert r["display_logged"] >= 1 and len(_lines(_g(tmp_path, "display.jsonl"))) > n1


def test_display_log_not_written_by_cycle_runs(tmp_path):
    cfg = _cfg(tmp_path)
    r = engine.run_shadow([_it(1, Q)], OK, cfg, source="cycle", now=NOW)
    assert r["logged"] >= 1 and "display_logged" not in r
    assert not _g(tmp_path, "display.jsonl").exists()


def test_display_log_never_counts_as_asked(tmp_path):
    cfg = _cfg(tmp_path)
    for k in range(3):
        r = engine.run_shadow([_it(1, Q)], OK, cfg, source="automated", now=NOW + k * 7 * 3600)
        assert r["history"] == 0 and r["display_only"] >= 1
    assert _lines(_g(tmp_path, "display.jsonl"))


def test_display_log_size_rotates(tmp_path):
    cfg = _cfg(tmp_path, jsonl_max_bytes=200, goal_reask_s=6 * 3600.0)
    engine.run_shadow([_it(1, Q)], OK, cfg, source="automated", now=NOW)
    engine.run_shadow([_it(1, Q)], OK, cfg, source="automated", now=NOW + 7 * 3600)
    p = _g(tmp_path, "display.jsonl")
    assert os.path.exists(str(p) + ".1") and p.exists()


# ── (b) asked.jsonl rotation ────────────────────────────────────────────────────────────────────────────────────
def _asked(tmp_path, entries):
    d = _g(tmp_path, ""); os.makedirs(str(d), exist_ok=True)
    with open(_g(tmp_path, "asked.jsonl"), "w") as fh:
        for ts, who in entries:
            fh.write(json.dumps({"ts": ts, "shown_at": ts, "id": "syn-x", "who": who, "topic": ["widget7"],
                                 "action": "ClarifyQuestion", "pad": "x" * 100}) + "\n")


def test_asked_rotation_keeps_reask_window(tmp_path):
    cfg = _cfg(tmp_path, jsonl_max_bytes=500)
    _asked(tmp_path, [(NOW - 5 * D, "wren")] * 4 + [(NOW - 1 * D, "quill")])
    gp.record_shown(cfg, [{"id": "syn-y", "who": "wren", "topic": ["cog3"], "action": "RemindPending"}], "wren",
                    now=NOW)
    p = _g(tmp_path, "asked.jsonl")
    old = _lines(type(p)(str(p) + ".1"))
    kept = _lines(p)
    assert len(old) == 5                                                      # full history moved aside
    assert [x["who"] for x in kept] == ["quill", "wren"]                      # in-window entry + the new one
    assert all(NOW - x["ts"] < 3 * D for x in kept)
    _, hist = engine._recent(str(_g(tmp_path, "proposals.jsonl")), NOW + 10, 60.0, 3 * D, str(p))
    assert {h["who"] for h in hist} == {"quill", "wren"}


def test_asked_rotation_then_reask_still_suppressed(tmp_path):
    cfg = _cfg(tmp_path, goal_prompt=True, goal_repeat_s=60.0, jsonl_max_bytes=300)
    engine.run_shadow([_it(1, Q)], OK, cfg, source="automated", now=NOW)
    _asked(tmp_path, [(NOW - 10 * D, "wren")] * 5)                           # old filler pushes it over the cap
    assert gp.render(cfg, now=NOW + 5, speaker="quill", record=True)
    assert gp.render(cfg, now=NOW + 6, speaker="quill", record=True)           # this append triggers rotation
    p = _g(tmp_path, "asked.jsonl")
    assert os.path.exists(str(p) + ".1")
    assert all(x["who"] == "quill" for x in _lines(p)) and _lines(p)
    r = engine.run_shadow([_it(1, Q)], OK, cfg, source="automated", now=NOW + 3600)
    assert r["history"] >= 1 and r["display_only"] == 0


def test_asked_no_rotation_under_cap(tmp_path):
    cfg = _cfg(tmp_path)
    _asked(tmp_path, [(NOW - 10 * D, "wren")])
    gp.record_shown(cfg, [{"id": "syn-y", "who": "wren", "topic": ["cog3"], "action": "RemindPending"}], "wren",
                    now=NOW)
    p = _g(tmp_path, "asked.jsonl")
    assert len(_lines(p)) == 2 and not os.path.exists(str(p) + ".1")


def test_display_constant_and_prompt_never_reads_display():
    src = open(gp.__file__).read()
    assert "display.jsonl" not in src and engine.DISPLAY == "display.jsonl"
    assert "DISPLAY" not in engine._recent.__code__.co_names
