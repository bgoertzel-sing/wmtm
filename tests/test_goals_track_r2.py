"""Track R2: one synthetic test group per fix (1 resolved, 2 explicit whole sentences, 3 addressees/kinds, 4 timing).
Made-up people (quill, wren, botty) and ids only; no real memories."""
from wmtm.goals import engine, needs, actions

NOW = 1_800_000_000.0
D = 86400.0
SM = {"speaker_map": {"quill": "quill", "9001": "quill", "wren": "wren", "9002": "wren"}, "speaker_self": "botty"}


def _it(i, text, age_d=1.0, sti=1.0):
    return {"id": "syn-%d" % i, "content": text, "sti": sti, "source_type": "recalled", "origin_ts": NOW - age_d * D}


def _cfg(**kw):
    return dict(SM, **kw)


def _texts(r):
    return [p["text"] for p in r["all_proposed"]]


# ---- fix 1: resolved / superseded detection -------------------------------------------------------------------
def test_fix1_later_decision_note_closes_question():
    items = [_it(1, "Open question for Quill: should the widget1 sprocket bracket be blue or red?", age_d=3),
             _it(2, "DECISION from Quill: the widget1 sprocket bracket is blue.", age_d=2)]
    r = engine.propose(items, _cfg(), now=NOW)
    assert not any("widget1" in t for t in _texts(r))


def test_fix1_same_day_resolution_closes_item():
    items = [_it(1, "PENDING: Quill to review the gadget5 sprocket report.", age_d=0.5),
             _it(2, "RESOLVED: Quill reviewed the gadget5 sprocket report.", age_d=0.3)]
    assert engine.propose(items, _cfg(), now=NOW)["all_proposed"] == []


def test_fix1_negated_resolution_word_does_not_close():
    items = [_it(1, "Open question for Quill: should the widget1 sprocket bracket be blue or red?", age_d=3),
             _it(2, "Quill has not answered on the widget1 sprocket bracket yet.", age_d=2)]
    r = engine.propose(items, _cfg(), now=NOW)
    assert any("widget1" in t for t in _texts(r))


def test_fix1_addressee_reply_closes_question():
    items = [_it(1, "Open question for Quill: should the widget1 sprocket bracket be blue or red?", age_d=3)]
    reqs = [{"ts": NOW - 2 * D, "who": "quill", "text": "[reply to your message 5] blue for the widget1 bracket"}]
    assert not _texts(engine.propose(items, _cfg(goal_requests=reqs), now=NOW))
    other = [{"ts": NOW - 2 * D, "who": "wren", "text": "blue for the widget1 bracket"}]
    assert any("widget1" in t for t in _texts(engine.propose(items, _cfg(goal_requests=other), now=NOW)))


def test_fix1_status_checked_at_proposal_date():
    items = [_it(1, "Open question for Quill: should the widget1 sprocket bracket be blue or red?", age_d=3),
             _it(2, "DECISION from Quill: the widget1 sprocket bracket is blue.", age_d=1)]
    before = engine.propose(items, _cfg(), now=NOW - 2 * D)        # the decision is in the future at this date
    assert any("widget1" in t for t in _texts(before))
    assert not any("widget1" in t for t in _texts(engine.propose(items, _cfg(), now=NOW)))


def test_fix1_newer_note_supersedes_older_wording():
    items = [_it(1, "Still waiting on Quill for the gadget7 sprocket count (two options).", age_d=4),
             _it(2, "Still waiting on Quill for the gadget7 sprocket count, now only the red option.", age_d=2)]
    est = needs.estimate(items, NOW, engine.settings(_cfg()))
    sig = est["comp"]["signals"]
    assert len(sig) == 1 and "red option" in sig[0]["text"] and sig[0]["items"] == ["syn-1", "syn-2"]


# ---- fix 2: explicit markers only, whole sentences ------------------------------------------------------------
def test_fix2_only_explicit_markers():
    for s in ("that file never existed in gadget history, so it is not a regression.",
              "The widget6 canary failed on the second sprocket run.",
              "LINK: the sprocket note connects to the widget note.",
              "It did not answer whether widget9 should move?"):
        assert needs.classify(s) is None, s
    assert needs.classify("Open question for Quill: should widget1 move to the red bracket?") == "question"
    assert needs.classify("Blocked on Wren: which sprocket goes on gadget3?") == "question"
    assert needs.classify("PENDING: Wren to send the gadget3 drawing.") == "pending"


def test_fix2_whole_sentence_kept():
    long_q = ("Open question for Quill: should the widget1 sprocket bracket move from the blue rail to the red rail "
              "before the gadget2 rebuild, or after the gadget2 rebuild once the new sprocket counts are in?")
    r = engine.propose([_it(1, long_q, age_d=2)], _cfg(), now=NOW)
    ask = [p for p in r["all_proposed"] if p["action"] == "ClarifyQuestion"][0]
    assert ask["text"].endswith("once the new sprocket counts are in?")


def test_fix2_summary_max_three_deduped_full_sentences():
    items = [_it(i, t, age_d=2) for i, t in enumerate([
        "Open question for Quill: should widget1 use the blue sprocket bracket?",
        "Open question for Quill: should widget1 use the blue sprocket bracket or the red one?",   # same topic
        "Still waiting on Wren for the gadget2 drawing revision.",
        "Blocked on Quill: should gadget3 ship with the long axle option?",
        "PENDING: Wren to confirm the gadget4 paint colour choice."])]
    r = engine.propose(items, _cfg(), {"requester": "quill"}, now=NOW)
    summ = [p for p in r["all_proposed"] if p["action"] == "SummarizeStatus"]
    assert summ and len(summ[0]["signals"]) <= 3
    txt = summ[0]["text"]
    assert txt.count("widget1") == 1 and "|" not in txt
    for s in summ[0]["signals"]:
        assert s["text"] in txt                     # whole sentences, not truncated


# ---- fix 3: addressees and kinds ------------------------------------------------------------------------------
def test_fix3_addressee_resolved_never_user():
    items = [_it(1, "The chain is still waiting on the user for the gadget8 colour.", age_d=2)]
    reqs = [{"ts": NOW - 3 * D, "who": "wren", "text": "help with gadget8"}]
    r = engine.propose(items, _cfg(goal_requests=reqs), now=NOW)
    assert r["all_proposed"] and all(p["who"] == "wren" for p in r["all_proposed"])
    r2 = engine.propose(items, _cfg(), now=NOW)                 # no request history: unresolvable -> dropped
    assert all(p["who"] not in ("user", None) for p in r2["all_proposed"])
    assert not any(p["action"] in actions.MESSAGE_ACTIONS for p in r2["all_proposed"])


def test_fix3_no_double_name():
    items = [_it(1, "Open question for Quill: should widget1 use the blue sprocket bracket?", age_d=2)]
    sm = {"speaker_map": {"quill": "quill", "qpen": "quill"}}
    r = engine.propose(items, sm, now=NOW)
    ask = [p for p in r["all_proposed"] if p["action"] == "ClarifyQuestion"][0]
    assert ask["text"].startswith("Ask quill: should widget1")


def test_fix3_own_todo_is_selftask():
    items = [_it(1, "Next step, still pending: diff the widget1 files against the gadget2 branch.", age_d=2),
             _it(2, "The widget5 report was NOT delivered because the send was rejected.", age_d=2)]
    r = engine.propose(items, _cfg(), now=NOW)
    assert {p["action"] for p in r["all_proposed"]} == {"SelfTask"}
    for p in r["all_proposed"]:
        assert "message" not in p["effects"] and p["who"] == needs.SELF
    bad = dict(r["all_proposed"][0], action="RemindPending")
    assert engine.check_proposal(bad) == "message without a resolved addressee"


def test_fix3_lookup_only_for_factual_gaps():
    choice = [_it(1, "Open question for Quill: should widget1 use the blue sprocket branch or the red one?", age_d=2)]
    fact = [_it(1, "Open question for Quill: which branch holds the widget1 sprocket fix?", age_d=2)]
    assert "LookUp" not in {c["action"] for c in engine.propose(choice, _cfg(), now=NOW)["candidates"]}
    assert "LookUp" in {c["action"] for c in engine.propose(fact, _cfg(), now=NOW)["candidates"]}


# ---- fix 4: timing --------------------------------------------------------------------------------------------
def test_fix4_no_remind_before_one_day():
    young = [_it(1, "Still waiting on Wren for the gadget2 drawing revision.", age_d=0.2)]
    old = [_it(1, "Still waiting on Wren for the gadget2 drawing revision.", age_d=1.5)]
    assert "RemindPending" not in {p["action"] for p in engine.propose(young, _cfg(), now=NOW)["all_proposed"]}
    assert "RemindPending" in {p["action"] for p in engine.propose(old, _cfg(), now=NOW)["all_proposed"]}


def test_fix4_remind_clock_restarts_on_addressee_contact():
    old = [_it(1, "Still waiting on Wren for the gadget2 drawing revision.", age_d=3)]
    reqs = [{"ts": NOW - 0.3 * D, "who": "wren", "text": "unrelated hello about lunch"}]
    r = engine.propose(old, _cfg(goal_requests=reqs), now=NOW)
    assert "RemindPending" not in {p["action"] for p in r["all_proposed"]}


def test_fix4_no_reask_within_three_days_unless_new():
    # (age 2 d: at NOW + 3.5 d the item is 5.5 d old, inside the rc2 7-day age cap)
    items = [_it(1, "Open question for Quill: should widget1 use the blue sprocket bracket?", age_d=2)]
    first = engine.propose(items, _cfg(), now=NOW)
    ask = [p for p in first["all_proposed"] if p["action"] == "ClarifyQuestion"][0]
    hist = [{"ts": NOW, "who": "quill", "topic": ask["topic"], "action": ask["action"]}]
    again = engine.propose(items, _cfg(), {"history": hist}, now=NOW + 1 * D)
    assert not any(p["who"] == "quill" and "widget1" in p["text"] for p in again["all_proposed"])
    later = engine.propose(items, _cfg(), {"history": hist}, now=NOW + 3.5 * D)
    assert any("widget1" in p["text"] for p in later["all_proposed"])
    new = items + [_it(2, "Open question for Quill: should widget1 use the blue sprocket bracket now that "
                          "the gadget9 chassis arrived with thinner mounting holes?", age_d=-0.5)]
    upd = engine.propose(new, _cfg(), {"history": hist}, now=NOW + 1 * D)
    assert any("gadget9" in p["text"] for p in upd["all_proposed"])


# ---- R2.1 fix 1: one proposal per (person, topic) across action types, same day included ------------------------
def test_r21_same_topic_dedupe_across_action_types():
    items = [_it(1, "Open question for Quill: which branch holds the widget1 sprocket fix?", age_d=2)]
    r = engine.propose(items, _cfg(), now=NOW)
    to_quill = [p for p in r["all_proposed"] if p["who"] == "quill" and p["action"] in actions.DEDUPE_ACTIONS]
    assert len(to_quill) == 1
    assert to_quill[0]["score"] == max(c["score"] for c in r["candidates"]
                                       if c["who"] == "quill" and c["action"] in actions.DEDUPE_ACTIONS
                                       and c["status"] in ("proposed", "dup"))
    assert any(why.startswith("r21_same_topic_as_") for _, why in r["suppressed"])


def test_r21_dedupe_keeps_different_people_and_topics():
    items = [_it(1, "Open question for Quill: should widget1 use the blue sprocket bracket?", age_d=2),
             _it(2, "Open question for Wren: should gadget2 ship with the long axle option?", age_d=2)]
    r = engine.propose(items, _cfg(), now=NOW)
    who = sorted(p["who"] for p in r["all_proposed"] if p["action"] in actions.DEDUPE_ACTIONS)
    assert who == ["quill", "wren"]


# ---- R2.1 fix 2: summary timing per item, names, own promises ----------------------------------------------------
def test_r21_summary_drops_fresh_items():
    items = [_it(1, "Open question for Quill: should widget1 use the blue sprocket bracket?", age_d=2),
             _it(2, "Still waiting on Quill for the gadget2 drawing revision.", age_d=2),
             _it(3, "Blocked on Quill: should gadget3 ship with the long axle option?", age_d=0.01)]
    r = engine.propose(items, _cfg(), {"requester": "quill"}, now=NOW)
    summ = [p for p in r["all_proposed"] if p["action"] == "SummarizeStatus"]
    assert summ and "gadget3" not in summ[0]["text"]
    assert any(why == "r21_summary_item_too_fresh" for _, why in r["suppressed"])


def test_r21_the_user_replaced_with_name():
    items = [_it(1, "Still waiting on Wren: the user has to pick the gadget8 colour.", age_d=2)]
    r = engine.propose(items, _cfg(), now=NOW)
    assert r["all_proposed"]
    for p in r["all_proposed"]:
        assert "the user" not in p["text"].lower()
    assert any("wren has to pick" in p["text"] for p in r["all_proposed"])


def test_r21_own_promise_kept_out_of_status():
    items = [_it(1, "Still waiting on Quill for the gadget2 drawing revision, and I said I'll join the gadget9 "
                    "review thread.", age_d=2),
             _it(2, "Blocked on Quill: should gadget3 ship with the long axle option?", age_d=2)]
    r = engine.propose(items, _cfg(), {"requester": "quill"}, now=NOW)
    for p in r["all_proposed"]:
        if "message" in p["effects"]:
            assert "I said I'll" not in p["text"] and "gadget9" not in p["text"]
    assert any(p["action"] == "SelfTask" and "gadget9" in p["text"] for p in r["all_proposed"])
