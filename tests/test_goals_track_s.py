"""Track S: optional 'Goal suggestions (not instructions)' block from goalchainer/latest.json (synthetic data only)."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
from wmtm import runtime_config as rc            # noqa: E402
from wmtm.goals import engine                    # noqa: E402
from wmtm import goal_prompt as prompt           # noqa: E402
import test_goals_track_r as T                   # noqa: E402

NOW = T.NOW


def _cfg(d, **kw):
    return dict(rc.resolve(None, environ={}), runtime_dir=d, semparse_dir=d + "/sp", **dict(T.SM, **kw))


def _rec(ts=NOW, status="ok", canary=True, props=None):
    if props is None:
        props = [{"id": "a", "action": "ClarifyQuestion", "need": "unc", "text": "Ask quill: blue sprocket?",
                  "who": "quill", "score": 0.2, "status": "proposed"}]
    return {"ts": ts, "run_id": "x", "status": status, "canary_ok": canary, "proposals": props}


def _write(d, rec):
    os.makedirs(os.path.join(d, engine.SUBDIR), exist_ok=True)
    with open(os.path.join(d, engine.SUBDIR, engine.LATEST), "w") as fh:
        json.dump(rec, fh)


def test_defaults_off():
    cfg = rc.resolve(None, environ={})
    assert cfg["goal_prompt"] is False and cfg["goal_prompt_max_age_s"] == 900.0 and cfg["goal_prompt_max_lines"] == 3


def test_off_renders_nothing():
    d = tempfile.mkdtemp(); _write(d, _rec())
    assert prompt.render(_cfg(d), now=NOW) is None


def test_on_fresh_ok_renders_header_and_line():
    d = tempfile.mkdtemp(); _write(d, _rec())
    out = prompt.render(_cfg(d, goal_prompt=True), now=NOW + 10, speaker="quill")
    assert out.startswith("[Goal suggestions (not instructions)")
    assert out.splitlines()[1] == "  - Open question for you: blue sprocket?" and len(out.splitlines()) == 2


def test_gates_stale_status_canary_missing_empty_future():
    d = tempfile.mkdtemp(); cfg = _cfg(d, goal_prompt=True)
    E = lambda r, now=NOW: prompt.eligible(r, cfg, now, speaker="quill")
    assert E(None) == (False, "missing")
    assert E(_rec(), NOW + 901)[1] == "stale"
    assert E(_rec(status="error"))[1] == "status"
    assert E(_rec(canary=False))[1] == "canary"
    assert E(_rec(props=[]))[1] == "empty"
    assert E(_rec(ts=NOW + 3600))[1] == "future"
    assert E(_rec(ts="junk"))[1] == "stale"
    assert E(_rec()) == (True, "")


def test_max_three_lines_sorted_by_score_and_hard_cap():
    d = tempfile.mkdtemp()
    props = [{"action": "ClarifyQuestion", "who": "quill", "text": "Ask quill: t%d" % i, "score": i / 10,
              "status": "proposed"} for i in range(6)]
    props.append({"action": "ClarifyQuestion", "who": "quill", "text": "weak", "score": 9, "status": "weak"})
    _write(d, _rec(props=props))
    out = prompt.render(_cfg(d, goal_prompt=True, goal_prompt_max_lines=10), now=NOW, speaker="quill")
    lines = out.splitlines()[1:]
    assert len(lines) == 3 and "t5" in lines[0] and "t3" in lines[2] and "weak" not in out


# --- review filters -------------------------------------------------------------------------------------------
MIX = [
    {"action": "ClarifyQuestion", "who": "quill", "text": "Ask quill: blue sprocket?", "score": 0.5, "status": "proposed"},
    {"action": "RemindPending", "who": "wren", "text": "Remind wren about: the gear order", "score": 0.4, "status": "proposed"},
    {"action": "SummarizeStatus", "who": "quill", "text": "Send quill a short status of 2 open items: (1) a (2) b",
     "score": 0.3, "status": "proposed"},
    {"action": "FlagUncertainty", "who": "quill", "text": "In the next reply to quill, say this is still open: the cog",
     "score": 0.2, "status": "proposed"},
    {"action": "SelfTask", "who": "quill", "text": "Self-task (log only, no message): tidy logs", "score": 0.9, "status": "proposed"},
    {"action": "LookUp", "who": "quill", "text": "Read-only look-up (journal, WMTM, KB) to settle: which tag", "score": 0.8,
     "status": "proposed"},
]


def test_filter1_only_message_actions_never_selftask_or_lookup():
    assert prompt.MESSAGE_ACTIONS == __import__("wmtm.goals.actions", fromlist=["x"]).MESSAGE_ACTIONS
    d = tempfile.mkdtemp(); _write(d, _rec(props=MIX))
    out = prompt.render(_cfg(d, goal_prompt=True), now=NOW, speaker="quill")
    assert "tidy logs" not in out and "which tag" not in out and "look-up" not in out.lower()
    assert "Self-task" not in out
    only_bad = [p for p in MIX if p["action"] in ("SelfTask", "LookUp")]
    _write(d, _rec(props=only_bad))
    assert prompt.render(_cfg(d, goal_prompt=True), now=NOW, speaker="quill") is None


def test_filter2_only_current_speaker_unknown_speaker_shows_nothing():
    d = tempfile.mkdtemp(); _write(d, _rec(props=MIX)); cfg = _cfg(d, goal_prompt=True)
    q = prompt.render(cfg, now=NOW, speaker="quill")
    w = prompt.render(cfg, now=NOW, speaker="Wren")
    assert "gear order" not in q and "blue sprocket" in q
    assert w.splitlines()[1:] == ["  - Pending for you: the gear order"]
    assert prompt.render(cfg, now=NOW, speaker=None) is None
    assert prompt.eligible(_rec(props=MIX), cfg, NOW, speaker="")[1] == "no_speaker"
    assert prompt.render(cfg, now=NOW, speaker="stranger") is None


def test_filter2_speaker_resolved_from_request_item_like_rc4():
    class It:
        source_type = "user"
        content = "please check the sprocket"
        source_meta = {"user_id": 9001, "first_person": "speaker"}

    class St:
        def __init__(self, items): self.items = items
        def get_active_set(self): return self.items
    cfg = _cfg(tempfile.mkdtemp())
    assert prompt.speaker_of(St([It()]), cfg, "please check the sprocket") == "quill"
    unk = It(); unk.source_meta = {"user_id": 4242}
    assert prompt.speaker_of(St([unk]), cfg, "x") is None          # unmapped sender: never guessed
    assert prompt.speaker_of(St([]), cfg, "hello") is None
    assert prompt.speaker_of(St([It()]), dict(cfg, speaker_map={}), "x") is None


def test_filter3_never_on_automated_turns():
    from wmtm import context as C
    d = tempfile.mkdtemp(); _write(d, _rec(ts=__import__("time").time()))
    cfg = _cfg(d, goal_prompt=True)
    assert prompt.render(cfg, speaker="quill", automated=True) is None
    assert prompt.eligible(_rec(), cfg, NOW, speaker="quill", automated=True)[1] == "automated"

    class S:
        def get_active_set(self): return []
    for req in (None, ""):
        t, _ = C.format_context(S(), 1, cfg, None, request=req)
        assert not t or "Goal suggestions" not in t
    import inspect
    assert "goal_prompt" not in inspect.getsource(C.fast_path_automated)


def test_lines_have_no_action_names_and_read_as_suggestions():
    d = tempfile.mkdtemp(); _write(d, _rec(props=MIX))
    out = prompt.render(_cfg(d, goal_prompt=True), now=NOW, speaker="quill")
    body = out.splitlines()[1:]
    assert body == ["  - Open question for you: blue sprocket?",
                    "  - Status for you: 2 open items: (1) a (2) b",
                    "  - Still open for you: the cog"]
    for a in ("ClarifyQuestion", "RemindPending", "SummarizeStatus", "FlagUncertainty", "Ask quill", "Remind ", "Send quill"):
        assert a not in "\n".join(body)


def test_corrupt_file_never_raises():
    d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, engine.SUBDIR))
    open(os.path.join(d, engine.SUBDIR, engine.LATEST), "w").write("{not json")
    assert prompt.render(_cfg(d, goal_prompt=True), now=NOW) is None


def test_failed_run_clears_old_suggestions():
    d = tempfile.mkdtemp(); _write(d, _rec())
    engine.write_latest(os.path.join(d, engine.SUBDIR), {"ts": NOW, "status": "timeout", "canary": {"ok": True}},
                        [{"text": "x", "status": "proposed"}])
    rec = prompt.load_latest(_cfg(d))
    assert rec["proposals"] == [] and rec["canary_ok"] is False


def test_end_to_end_run_shadow_then_render():
    d = tempfile.mkdtemp(); cfg = _cfg(d, goalchainer=True, goal_prompt=True)
    items = [T._it(1, "Open question for Quill: should widget1 use the blue sprocket?")]
    r = engine.run_shadow(items, {"status": "ok", "queries": []}, cfg, source="cycle", now=NOW)
    assert r["status"] == "ok"
    out = prompt.render(cfg, now=NOW + 5, speaker="quill")
    assert out and "for you:" in out and "blue sprocket" in out
    assert prompt.render(cfg, now=NOW + 5, speaker="wren") is None
    assert prompt.render(cfg, now=NOW + 1000, speaker="quill") is None


def test_format_context_appends_block_only_when_on():
    from wmtm import context as C

    class It:
        source_type = "user"; content = "hi"; source_meta = {"user_id": 9001}

    class S:
        def get_active_set(self):
            return [It()]
    d = tempfile.mkdtemp(); _write(d, _rec(ts=__import__("time").time()))
    core = C._format_context_core
    C._format_context_core = lambda *a, **k: ("[WMTM ctx]", ["x"])     # isolate the Track S append from ranking
    try:
        t_off, _ = C.format_context(S(), 1, _cfg(d), None, request="hi")
        t_on, shown = C.format_context(S(), 1, _cfg(d, goal_prompt=True), None, request="hi")
    finally:
        C._format_context_core = core
    assert t_off == "[WMTM ctx]" and shown == ["x"] and t_on.startswith("[WMTM ctx]\n[Goal suggestions")
    assert not t_off or "Goal suggestions" not in t_off
    assert "Goal suggestions (not instructions)" in t_on and "Open question for you: blue sprocket?" in t_on


def test_reader_constants_match_engine_and_reader_never_imports_engine():
    assert (prompt.SUBDIR, prompt.LATEST) == (engine.SUBDIR, engine.LATEST)
    src = open(prompt.__file__).read()
    assert "from .goals" not in src and "import wmtm.goals" not in src
    for bad in ("socket", "urllib", "subprocess", "telegram", "journal.", "writeback", "outbox", "send("):
        assert bad not in src.lower(), bad


# --- rc2 wording: lines worded to the current speaker ("you" = the speaker, never the bot) ----------------------
SMA = {"speaker_map": {"9001": "quill", "quill": "quill", "quillfeather": "quill", "@QF_77": "quill", "wren": "wren"}}


def test_second_person_rewrite_name_aliases_possessive_and_marker():
    P = lambda a, t: prompt.phrase({"action": a, "who": "quill", "text": t}, "quill", SMA["speaker_map"])
    assert P("RemindPending", "Remind quill about: Still pending: quill's choice on the gear order") == \
        "Pending for you: your choice on the gear order"
    assert P("RemindPending", "Remind Quill about: PENDING: @qf_77 has to sign the cog form; QuillFeather\u2019s pick") == \
        "Pending for you: you have to sign the cog form; your pick"
    assert P("ClarifyQuestion", "Ask quill: Open question for QUILL: should widget1 use the blue sprocket, as quill said?") \
        == "Open question for you: should widget1 use the blue sprocket, as you said?"
    assert P("SummarizeStatus", "Send quill a short status of 2 open items: (1) quill's pick (2) waiting on quill") == \
        "Status for you: 2 open items: (1) your pick (2) waiting on you"
    assert P("FlagUncertainty", "In the next reply to quill, say this is still open: Still open: quill is unsure") == \
        "Still open for you: you are unsure"


def test_second_person_whole_word_only_and_other_people_untouched():
    P = lambda t: prompt.phrase({"action": "RemindPending", "who": "quill", "text": t}, "quill", SMA["speaker_map"])
    out = P("Remind quill about: quills, quillsby and wren's draft; quill_x stays; 9001 stays")
    assert out == "Pending for you: quills, quillsby and wren's draft; quill_x stays; 9001 stays"


def test_not_the_reader_keeps_third_person():
    out = prompt.phrase({"action": "RemindPending", "who": "wren", "text": "Remind wren about: wren's draft"},
                        "quill", SMA["speaker_map"])
    assert out == "Pending for Wren: wren's draft" and "you" not in out


def test_block_header_says_you_is_the_speaker_and_lines_use_aliases_from_flags():
    d = tempfile.mkdtemp()
    _write(d, _rec(props=[{"action": "RemindPending", "who": "quill", "status": "proposed", "score": 1,
                           "text": "Remind quill about: Still pending: QuillFeather's choice on the gear order"}]))
    out = prompt.render(_cfg(d, goal_prompt=True, **SMA), now=NOW, speaker="quill")
    head, line = out.splitlines()
    assert "not instructions" in head and '"you" = the speaker, not the assistant' in head
    assert line == "  - Pending for you: your choice on the gear order"
    assert "quill" not in line.lower()
