"""v0.7.0rc2 (Track V): closure from older replies and later journal notes, item age cap, (person, topic cluster)
dedupe, text quality and live-flag contradictions.  Synthetic only: made-up people, ids, chats and notes."""
import json
import os
import stat

from wmtm import goal_prompt as gp
from wmtm import runtime_config as rc
from wmtm.goals import actions, engine, needs, notes
from wmtm.goals import requests as greq

NOW = 1_800_000_000.0
D = 86400.0
MAP = {"9001": "quill", "quill_q": "quill", "9002": "wren", "wren_x": "wren", "9999": "botty"}
SM = {"speaker_map": MAP, "speaker_self": "botty"}
OK = {"status": "ok", "queries": []}
MSG = actions.MESSAGE_ACTIONS


def _it(i, text, age_d=2.0, sti=1.0):
    return {"id": "syn-%d" % i, "content": text, "sti": sti, "source_type": "recalled", "origin_ts": NOW - age_d * D}


def _req(d, name, prompt, source, mtime):
    p = d / name
    p.write_text(json.dumps({"schema_version": 1, "identity": "Botty", "request_id": name[:-5], "prompt": prompt,
                             "prompt_sha256": "0" * 64, "source": source}))
    os.utime(p, (mtime, mtime))
    return p


def _cfg(tmp_path, **kw):
    chan = tmp_path / "completed"
    chan.mkdir(exist_ok=True)
    return dict(SM, goalchainer=True, runtime_dir=str(tmp_path / "rt"), goal_requests_dir=str(chan),
                semparse_dir=str(tmp_path / "none"), goal_journal_path=str(tmp_path / "j" / "journal.metta"), **kw)


def _journal(tmp_path, notes_):
    d = tmp_path / "j"; d.mkdir(exist_ok=True)
    with open(d / "journal.metta", "a", encoding="utf-8") as fh:
        for cid, text in notes_:
            safe = text.replace("\\", "\\\\").replace('"', '\\"')
            fh.write(";;; BEGIN MemoryCluster %s\n(MemoryCluster %s)\n(EventNote ev-%s \"%s\")\n;;; END MemoryCluster %s\n"
                     % (cid, cid, cid, safe, cid))


def _stamp(ts):
    import time
    return time.strftime("ep-note-%Y%m%dT%H%M%SZ", time.gmtime(ts))


def _props(tmp_path, name="proposals.jsonl"):
    p = tmp_path / "rt" / "goalchainer" / name
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


def _msgs(res, who=None):
    return [p for p in res["all_proposed"] if p["action"] in MSG and (who is None or p["who"] == who)]


# ── 1. stale "still open" items ─────────────────────────────────────────────────────────────────────────────────
CHOICE = "Still open: Quill's choice on the GizMo bracket (move past r7, or backport the shim)."


def test_reply_older_than_the_default_window_is_found(tmp_path):
    """The item is 20 d old: the reply 19 d ago is outside goal_requests_days (14) but inside the grown window."""
    cfg = _cfg(tmp_path, goal_max_item_age_days=60)
    _req(tmp_path / "completed", "a" * 64 + ".json", "[reply to your message 5] please just upgrade the gizmo bracket",
         {"chat_id": -5, "message_id": 6, "update_id": 1, "user_id": 9001}, NOW - 19 * D)
    assert greq.window_days(cfg, NOW - 20 * D, NOW) == 21.0
    assert greq.window_days(cfg, NOW - 200 * D, NOW) == 45.0 and greq.window_days(cfg, NOW - D, NOW) == 14.0
    run = engine.run_shadow([_it(1, CHOICE, age_d=20)], OK, cfg, source="cycle", now=NOW)
    assert run["status"] == "ok" and run["requests"]["with_sender"] == 1 and run["requests"]["days"] == 21.0
    assert not [p for p in _props(tmp_path) if p["action"] in MSG]
    # with the rc1 14-day window the reply is invisible and the stale reminder comes back
    st = {}
    assert greq.load(cfg, NOW, st) == [] and st["files"] == 0


def test_unattributed_group_reply_closes_only_when_on_topic(tmp_path):
    cfg = _cfg(tmp_path)
    items = [_it(1, CHOICE, age_d=3)]
    _req(tmp_path / "completed", "b" * 64 + ".json", "[reply to your message 5] please just upgrade gizmo",
         {"chat_id": -5, "message_id": 6, "update_id": 1}, NOW - 2 * D)            # group, sender not recorded
    reqs = greq.load(cfg, NOW, {}, days=14)
    assert [r["who"] for r in reqs] == [None] and reqs[0]["reply"]
    tr = []
    r = engine.propose(items, dict(cfg, goal_requests=reqs), {"autonomous": False}, now=NOW, trace=tr)
    assert not _msgs(r, "quill") and any(w == "closed_by_unattributed_reply" for _, _, w in tr)
    r = engine.propose(items, dict(cfg, goal_requests=reqs, goal_close_unattributed=False), {"autonomous": False},
                       now=NOW)
    assert _msgs(r, "quill")                                                       # flag off: no closure
    off = [dict(reqs[0], keys=["weather", "lunch"], moot=[])]
    assert _msgs(engine.propose(items, dict(cfg, goal_requests=off), {"autonomous": False}, now=NOW), "quill")
    assert greq.load(dict(cfg, goal_close_unattributed=False), NOW, {}, days=14) == []


def test_addressee_reply_matches_paraphrase_by_stem():
    items = [_it(1, "Still open: merging the Gizmo9 branch to trunk needs Quill's OK.", age_d=3)]
    reqs = [{"ts": NOW - D, "who": "quill", **needs.request_digest("fine, merge to trunk now")}]
    r = engine.propose(items, dict(SM, goal_requests=reqs), {"autonomous": False}, now=NOW)
    assert not _msgs(r, "quill")


def test_decision_reply_just_before_a_stale_restatement_closes():
    """The addressee said "ok, merge it" at T; the bot's note 7 h later still says it needs the OK."""
    items = [_it(1, "Still open: merging the Gizmo branch to trunk needs Quill's OK.", age_d=2)]
    yes = needs.request_digest("[reply to your message 4] ok, merge it to trunk; what is cog3 for?")
    assert yes["dec"]
    for who in ("quill", None):
        reqs = [dict(ts=NOW - 2 * D - 7 * 3600, who=who, **yes)]
        assert not _msgs(engine.propose(items, dict(SM, goal_requests=reqs), {"autonomous": False}, now=NOW))
    old = [dict(ts=NOW - 4 * D, who="quill", **yes)]                  # outside the 24 h grace: still open
    assert _msgs(engine.propose(items, dict(SM, goal_requests=old), {"autonomous": False}, now=NOW), "quill")
    long_ = needs.request_digest("[reply to your message 4] yes but first: " + " ".join(
        "topic%d" % i for i in range(20)) + " merge")
    assert _msgs(engine.propose(items, dict(SM, goal_requests=[dict(ts=NOW - 2 * D - 7 * 3600, who=None, **long_)]),
                                {"autonomous": False}, now=NOW), "quill")       # long message, one shared word
    q = [dict(ts=NOW - 2 * D - 7 * 3600, who="quill", **needs.request_digest("[reply to your message 4] merge what?"))]
    assert _msgs(engine.propose(items, dict(SM, goal_requests=q), {"autonomous": False}, now=NOW), "quill")


def test_later_journal_note_closes_item_outside_the_active_set(tmp_path):
    cfg = _cfg(tmp_path)
    items = [_it(1, CHOICE, age_d=3)]
    assert _msgs(engine.propose(items, cfg, {"autonomous": False}, now=NOW), "quill")
    _journal(tmp_path, [(_stamp(NOW - 2.5 * D), "Unrelated: the cog3 lunch list is ready."),
                        (_stamp(NOW - 2 * D), "Quill's 'just upgrade gizmo' request was settled this "
                                              "morning; nothing is pending there.")])
    run = engine.run_shadow(items, OK, cfg, source="cycle", now=NOW)
    assert run["status"] == "ok" and run["requests"]["journal"]["journal"] == "ok"
    assert not [p for p in _props(tmp_path) if p["action"] in MSG]
    ip = tmp_path / "rt" / "goalchainer" / notes.INDEX
    raw = ip.read_text()
    assert "settled this" not in raw and "lunch" not in raw                       # digests only
    assert stat.S_IMODE(os.stat(ip).st_mode) == 0o600
    idx = json.loads(raw)
    assert [n[0] for n in idx["notes"]] == [_stamp(NOW - 2 * D)]                   # notes without evidence: not kept


def test_owner_decision_needs_a_specific_anchor(tmp_path):
    item = [_it(1, "Blocked on Quill: should CogLib provide src/cog.metta, or should we drop the import?", age_d=3)]
    generic = [(_stamp(NOW - 2 * D - i * 60), "RESOLVED: the CogLib item %d is closed." % i) for i in range(6)]
    _journal(tmp_path, generic + [(_stamp(NOW - D), "Answered Quill: wrote a long summary of CogLib.")])
    r = engine.propose(item, dict(_cfg(tmp_path), goal_notes=notes.load(_cfg(tmp_path), NOW, {})),
                       {"autonomous": False}, now=NOW)
    assert _msgs(r, "quill")                       # CogLib is in most closure notes: not this item's topic


def test_journal_index_is_incremental_and_waits_for_a_complete_note(tmp_path):
    cfg = _cfg(tmp_path)
    _journal(tmp_path, [(_stamp(NOW - 2 * D), "RESOLVED: the widget5 rename is done.")])
    st = {}
    assert len(notes.load(cfg, NOW, st)) == 1 and st["added"] == 1
    p = tmp_path / "j" / "journal.metta"
    with open(p, "a", encoding="utf-8") as fh:                                     # a note still being written
        fh.write('(EventNote ev-%s "The sprocket2 order is done.\n' % _stamp(NOW - D))
    st = {}
    assert len(notes.load(cfg, NOW, st)) == 1 and st["added"] == 0
    with open(p, "a", encoding="utf-8") as fh:
        fh.write('Second line of it.")\n')
    st = {}
    out = notes.load(cfg, NOW, st)
    assert len(out) == 2 and st["added"] == 1
    st = {}
    assert notes.load(cfg, NOW + 60 * D, st) == [] and st["notes"] == 0            # older than goal_history_max_days
    assert notes.load(dict(cfg, goal_journal_closure=False), NOW, st) == [] and st["journal"] == "off"


def test_restatement_after_the_reply_keeps_the_item_open():
    items = [_it(1, CHOICE, age_d=3), _it(2, "Still waiting on Quill's choice on the GizMo bracket shim.", age_d=1)]
    reqs = [{"ts": NOW - 2 * D, "who": "quill", **needs.request_digest("[reply to your message 3] gizmo later")}]
    r = engine.propose(items, dict(SM, goal_requests=reqs), {"autonomous": False}, now=NOW + 1.5 * D)
    assert _msgs(r, "quill")


# ── 2. age cap ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_no_reminder_about_items_older_than_the_cap():
    q = "Open question for Quill: should the widget7 gadget be renamed to sprocket9?"
    tr = []
    r = engine.propose([_it(1, q, age_d=8), _it(2, CHOICE, age_d=9)], SM, {"autonomous": False}, now=NOW, trace=tr)
    assert not _msgs(r) and any(w.startswith("rc2_item_older_than_7d") for _, _, w in tr)
    assert _msgs(engine.propose([_it(1, q, age_d=8)], dict(SM, goal_max_item_age_days=10), {"autonomous": False},
                                now=NOW))
    # a newer note re-raising it moves the item's age
    r = engine.propose([_it(1, q, age_d=8), _it(3, "Open question for Quill: is the widget7 gadget rename to "
                                                   "sprocket9 still wanted?", age_d=2)], SM, {"autonomous": False},
                       now=NOW)
    assert _msgs(r, "quill")


# ── 3. paraphrase duplicates ────────────────────────────────────────────────────────────────────────────────────
PARA = ["Still open: Quill's choice on Gizmo9 zwrite (move past r7, or backport the patch).",
        "Status unchanged: waiting on Quill's zwrite decision for Gizmo9 (a: upgrade, or b: backport the fix)."]


def test_paraphrases_are_one_cluster_and_one_signal():
    a, b = needs.keys(PARA[0]), needs.keys(PARA[1])
    assert needs.cluster_match(a, b)
    assert not needs.cluster_match(a, needs.keys("Still open: Quill's lunch order for the cog3 offsite."))
    assert needs.cluster_match(needs.keys("Still waiting on Quill's src/widget answer."),
                               needs.keys("should CogLib provide src/widget.metta, or drop the import?"))
    est = needs.estimate([_it(1, PARA[0], age_d=3), _it(2, PARA[1], age_d=2)], NOW, engine.settings(SM))
    assert len([s for s in est["comp"]["signals"] if s["who"] == "quill"]) == 1
    assert needs.stem("merging") == needs.stem("merge") == needs.stem("merged")
    # a shared generic anchor alone ("WMTM" / "wmtm") is not a topic
    assert not needs.cluster_match(needs.keys("Blocked: should WMTM ship src/cog.metta, or drop it?"),
                                   needs.keys("answered (12): wrote a short summary of WMTM."))
    # names are not topic terms: two unrelated items of one person are two signals
    est = needs.estimate([_it(1, "Still open: Quill's Gizmo lunch order.", age_d=3),
                          _it(2, "Still open: Quill's Gizmo bracket review.", age_d=2)], NOW, engine.settings(SM))
    assert all("quill" not in s["ckeys"] for s in est["comp"]["signals"])


def test_moot_word_as_an_option_is_not_a_closure():
    d = needs.sentence_digest("It did not settle whether CogLib should keep or drop the src/cog import.")
    assert d is None or not d["moot"]
    assert needs.sentence_digest("The src/cog import is gone now.")["moot"]


def test_display_log_dedupes_paraphrase_under_new_id(tmp_path):
    cfg = _cfg(tmp_path)
    engine.run_shadow([_it(1, PARA[0], age_d=3)], OK, cfg, source="automated", now=NOW)
    d1 = _props(tmp_path, "display.jsonl")
    assert len(d1) == 1 and d1[0]["who"] == "quill"
    r = engine.run_shadow([_it(2, PARA[1], age_d=3)], OK, cfg, source="automated", now=NOW + 7 * 3600)
    assert r["display_only"] == 1 and r["display_logged"] == 0                     # new id, same (person, cluster)
    r = engine.run_shadow([_it(2, PARA[1], age_d=3)], OK, cfg, source="automated", now=NOW + 3.1 * D)
    assert r["display_logged"] == 1                                                # after goal_reask_s


def test_proposals_repeat_and_latest_by_cluster(tmp_path):
    cfg = _cfg(tmp_path)
    engine.run_shadow([_it(1, PARA[0], age_d=3)], OK, cfg, source="cycle", now=NOW)
    n = len([p for p in _props(tmp_path) if p["action"] in MSG])
    assert n == 1
    engine.run_shadow([_it(2, PARA[1], age_d=3)], OK, cfg, source="cycle", now=NOW + 3600)
    assert len([p for p in _props(tmp_path) if p["action"] in MSG]) == 1           # paraphrase not re-logged
    p0 = {"who": "quill", "action": "RemindPending", "topic": sorted(needs.keys(PARA[0]))}
    p1 = {"who": "quill", "action": "ClarifyQuestion", "topic": sorted(needs.keys(PARA[1]))}
    p2 = {"who": "wren", "action": "RemindPending", "topic": sorted(needs.keys(PARA[1]))}
    assert engine.dedupe_cluster([p0, p1, p2]) == [p0, p2]
    d = tmp_path / "lt"; d.mkdir()
    engine.write_latest(str(d), {"status": "ok", "canary": {"ok": True}}, [dict(p0, id="x"), dict(p1, id="y")])
    assert [p["id"] for p in json.loads((d / engine.LATEST).read_text())["proposals"]] == ["x"]
    assert gp.distinct_topics([p0, p1]) == [p0]


def test_reask_blocked_for_a_paraphrase_under_a_new_id(tmp_path):
    cfg = _cfg(tmp_path)
    engine.run_shadow([_it(1, PARA[0], age_d=3)], OK, cfg, source="cycle", now=NOW)
    shown = [p for p in _props(tmp_path) if p["action"] in MSG]
    gp.record_shown(cfg, shown, "quill", now=NOW + 60)
    r = engine.propose([_it(2, PARA[1], age_d=3)], cfg, {"autonomous": False, "history": [
        {"ts": NOW + 60, "who": "quill", "topic": shown[0]["topic"], "action": shown[0]["action"]}]}, now=NOW + 7 * 3600)
    assert not _msgs(r, "quill")


# ── 4. text quality ─────────────────────────────────────────────────────────────────────────────────────────────
def test_aliases_resolved_and_own_wait_clause_dropped():
    note = "Still pending: offers to draft a Gizmo9 adapter sketch and docs/COG_NOTES.md, waiting on quill_q."
    r = engine.propose([_it(1, note, age_d=2)], SM, {"autonomous": False}, now=NOW)
    m = _msgs(r, "quill")
    assert m and "quill_q" not in m[0]["text"] and "waiting on" not in m[0]["text"]
    assert m[0]["text"].endswith("docs/COG_NOTES.md.")
    line = gp.phrase(m[0], "quill", MAP)
    assert line.startswith("Pending for you:") and "quill" not in line.lower()
    assert needs.canon_text("ping @wren_x and Wren_X", needs.alias_map(MAP)) == "ping wren and wren"


def test_bundles_split_into_one_item_each():
    s = ("Still open: merging the Gizmo9 branch needs Quill's OK, and Quill hasn't answered on src/cog yet.")
    cs = [c for c, _ in needs.candidates_of(s, needs.people_patterns(MAP), "botty", "quill")]
    assert [c["text"] for c in cs] == ["Still open: merging the Gizmo9 branch needs Quill's OK.",
                                       "Still open: Quill hasn't answered on src/cog yet."]
    s = "Still open: the sprocket2 rotation; the gadget4 cache trim; widget1 cleanup."
    assert len([c for c, _ in needs.candidates_of(s) if c]) == 3
    # a single ";" continues the same item; a single item with an internal "and" is not split
    s = "PENDING: the widget4 summary. The cog3/ dir was missing at 11:02; the last cycle was 10:48."
    assert len(needs.candidates_of(s)) == 1
    s = "Still pending: Quill's choice on widget3 and sprocket8 sizes."
    assert len(needs.candidates_of(s, needs.people_patterns(MAP))) == 1


def test_fragments_are_dropped_not_cut():
    for s in ("It is still open: no later note says the cog3 run finished.", "Still open: nothing new from the gadget4 thread.",
              "Still pending: and then the widget2 check."):
        c, why = needs.candidate(s, needs.people_patterns(MAP), "botty", "quill")
        assert c is None and why == "fragment", s
    c, _ = needs.candidate("LINK: earlier note. Still open: Quill's choice on the widget2 frame.",
                           needs.people_patterns(MAP), "botty", "quill")
    assert c and c["text"].startswith("Still open:")


# ── 5. contradiction with live state ────────────────────────────────────────────────────────────────────────────
def test_item_about_a_flag_already_set_is_closed():
    n = "Open question for Quill: should we turn speaker_link on for the gizmo9 bot?"
    tr = []
    r = engine.propose([_it(1, n)], dict(SM, speaker_link=True), {"autonomous": False}, now=NOW, trace=tr)
    assert not _msgs(r) and any(w == "closed_flag_already_set_speaker_link" for _, _, w in tr)
    assert _msgs(engine.propose([_it(1, n)], dict(SM, speaker_link=False), {"autonomous": False}, now=NOW))
    assert needs.flag_contradiction("whether to switch goal_prompt off", {"goal_prompt": False}) == "goal_prompt"
    assert needs.flag_contradiction("whether to switch goal_prompt off", {"goal_prompt": True}) is None
    assert needs.flag_contradiction("goal_prompt on or off?", {"goal_prompt": True}) is None   # ambiguous
    assert "speaker_link" in engine.live_flags(rc.resolve(None, environ={}))


# ── index files are 0600 whatever the umask / directory ACL ─────────────────────────────────────────────────────
def test_index_files_mode_600_under_permissive_umask(tmp_path):
    cfg = _cfg(tmp_path)
    _req(tmp_path / "completed", "c" * 64 + ".json", "widget7 check", {"chat_id": 9001, "message_id": 1,
                                                                        "update_id": 1}, NOW - D)
    _journal(tmp_path, [(_stamp(NOW - D), "RESOLVED: the widget5 rename is done.")])
    old = os.umask(0)
    try:
        greq.load(cfg, NOW, {})
        notes.load(cfg, NOW, {})
        g = tmp_path / "rt" / "goalchainer"
        for f in (greq.INDEX, notes.INDEX):
            os.chmod(g / f, 0o666)                       # an existing index with a wider mode is replaced at 600
        _req(tmp_path / "completed", "d" * 64 + ".json", "widget8 check", {"chat_id": 9001, "message_id": 2,
                                                                            "update_id": 2}, NOW - D)
        _journal(tmp_path, [(_stamp(NOW - 0.5 * D), "DECIDED: the sprocket2 order is settled.")])
        greq.load(cfg, NOW, {})
        notes.load(cfg, NOW, {})
    finally:
        os.umask(old)
    for f in (greq.INDEX, notes.INDEX):
        assert stat.S_IMODE(os.stat(g / f).st_mode) == 0o600, f


def test_new_flags_defaults():
    cfg = rc.resolve(None, environ={})
    assert cfg["goal_history_max_days"] == 45.0 and cfg["goal_close_unattributed"] is True
    assert cfg["goal_journal_closure"] is True and cfg["goal_journal_path"] == ""
    assert cfg["goal_max_item_age_days"] == 7.0 and cfg["goal_topic_overlap"] == 0.4
    assert notes.journal_path({"state_dir": "/x/mem"}) in ("/x/mem/_journal/journal.metta",
                                                           os.path.join(os.environ.get("JOURNAL_DIR", "-"),
                                                                        "journal.metta"))


def test_v2_workdir_private_under_umask_0(tmp_path):
    from wmtm.goals import v2
    old = os.umask(0)
    try:
        engine.run_shadow([_it(1, CHOICE, age_d=3)], OK, _cfg(tmp_path), source="cycle", now=NOW)
        wd = tmp_path / "wd"
        try:
            v2.client({"series": []}, engine.v2_cfg(_cfg(tmp_path)), str(wd))
        except v2.V2Error:
            pass
        assert stat.S_IMODE(os.stat(wd).st_mode) == 0o700
    finally:
        os.umask(old)
