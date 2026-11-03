"""Goal lifecycle rules (wmtm/goals/lifecycle.py): stable IDs, near-duplicate merging, open/satisfied/superseded/stale.
Synthetic texts only (no real memories)."""
import calendar
import time

from wmtm.goals import lifecycle as L

D = 86400.0
T0 = float(calendar.timegm(time.strptime("2026-10-20T00:00", "%Y-%m-%dT%H:%M")))


def P(text, ts, items, who="self", action="SelfTask", pid="e1"):
    return {"text": text, "ts": ts, "items": items, "who": who, "action": action, "id": pid}


def G(text, who="self", action="SelfTask"):
    return {"who": who, "action": action, "terms": L.terms(text)}


SELF = "Self-task (log only, no message): "


def test_body_strips_wrapper_and_open_markers():
    assert L.body(SELF + "Still open: PENDING: widget cache rotation.") == "widget cache rotation."
    assert L.body("Remind quill about: Still waiting on quill's answer.").startswith("quill's answer")


def test_near_duplicate_pair_merges():
    a = G(SELF + "Still open: LTM compression of the Oct4/Oct5 pin lines before the promotion.")
    b = G(SELF + "PENDING: LTM compression of the Oct4/Oct5 pin lines before promotion")
    ok, why = L.same_goal(a, b)
    assert ok, why


def test_different_object_must_not_merge():
    # same person, same action, same verbs, different anchored object
    a = G("Remind quill about: Still waiting on quill's src/widget answer.", "quill", "RemindPending")
    b = G("Remind quill about: Still waiting on quill's src/gadget answer.", "quill", "RemindPending")
    ok, why = L.same_goal(a, b)
    assert not ok and "anchors" in why


def test_low_overlap_must_not_merge_and_person_matters():
    a = G(SELF + "Still open: asked.jsonl rotation.")
    b = G(SELF + "Still open: asked.jsonl rotation and the widget cache cleanup with backups pruned.")
    assert not L.same_goal(a, b)[0]
    c = G(SELF + "Still open: asked.jsonl rotation.", who="quill")
    assert L.same_goal(a, c) == (False, "different person")


def test_goal_id_is_stable_and_order_free():
    t = L.terms(SELF + "Still open: asked.jsonl rotation.")
    assert L.goal_id("self", "SelfTask", t) == L.goal_id("self", "SelfTask", set(sorted(t, reverse=True)))
    assert L.goal_id("self", "SelfTask", t) != L.goal_id("quill", "SelfTask", t)


def _note(i, ts, text):
    return ("ep-note-%s" % i, ts, text)


def test_duplicates_dropped_and_same_gid():
    lc = L.Lifecycle([_note("n1", T0, "x")])
    v1 = lc.observe(P(SELF + "Still open: widget cache rotation.", T0 + 10, ["ep-note-n1"], pid="a"))
    v2 = lc.observe(P(SELF + "PENDING: widget cache rotation", T0 + 20, ["ep-note-n1"], pid="b"))
    v3 = lc.observe(P(SELF + "Still open: widget cache rotation.", T0 + 30, ["ep-note-n1"], pid="a"))
    assert v1["keep"] and not v2["keep"] and not v3["keep"]
    assert v1["gid"] == v2["gid"] == v3["gid"]
    assert v2["reason"].startswith("near-duplicate") and v3["reason"].startswith("duplicate")


def test_satisfied_by_task_id():
    notes = [_note("n1", T0, "Still open: write the widget docs for t-2026-10-28-widget-docs."),
             _note("n2", T0 + D, "Oct21 05:52 CLOSED t-2026-10-28-widget-docs. It passed review.")]
    v = L.Lifecycle(notes).observe(P(SELF + "Still open: write the widget docs for t-2026-10-28-widget-docs.",
                                     T0 + 2 * D, ["ep-note-n1"]))
    assert v["state"] == "satisfied" and "ep-note-n2" in v["reason"] and "names task" in v["reason"]


def test_closing_a_prerequisite_does_not_satisfy_the_follow_up():
    # review 1, point 2: "once t-x closes, delete branch Y" is not done when t-x closes
    goal = SELF + "Still open: once t-2026-10-28-widget-docs closes, delete branch hive/w-backup."
    notes = [_note("n1", T0, goal), _note("n2", T0 + D, "Oct21 05:52 CLOSED t-2026-10-28-widget-docs. It passed review.")]
    lc = L.Lifecycle(notes)
    assert lc.observe(P(goal, T0 + 2 * D, ["ep-note-n1"]))["state"] == "open"
    notes.append(_note("n3", T0 + 2.5 * D, "Branch hive/w-backup deleted after the widget-docs close."))
    v = L.Lifecycle(notes).observe(P(goal, T0 + 3 * D, ["ep-note-n1"]))
    assert v["state"] == "satisfied" and "ep-note-n3" in v["reason"]


def test_satisfied_by_closing_sentence_terms():
    notes = [_note("n1", T0, "Still open: widget cache rotation for gadget logs."),
             _note("n2", T0 + D, "The widget cache rotation for gadget logs is done.")]
    v = L.Lifecycle(notes).observe(P(SELF + "Still open: widget cache rotation for gadget logs.", T0 + 2 * D,
                                     ["ep-note-n1"]))
    assert v["state"] == "satisfied"


def test_not_satisfied_by_negated_open_or_earlier_or_label_sentences():
    goal = SELF + "Still open: widget cache rotation for gadget logs."
    for txt in ("The widget cache rotation for gadget logs is not done.",
                "Still open: widget cache rotation for gadget logs, then it is done.",
                "LESSON: widget cache rotation for gadget logs was closed too early last time."):
        lc = L.Lifecycle([_note("n1", T0, goal), _note("n2", T0 + D, txt)])
        assert lc.observe(P(goal, T0 + 2 * D, ["ep-note-n1"]))["state"] == "open", txt
    # a closure note OLDER than the goal's source note does not count
    lc = L.Lifecycle([_note("n0", T0 - D, "The widget cache rotation for gadget logs is done."), _note("n1", T0, goal)])
    assert lc.observe(P(goal, T0 + D, ["ep-note-n1"]))["state"] == "open"
    # nor does a note written after the proposal (no look-ahead)
    lc = L.Lifecycle([_note("n1", T0, goal), _note("n2", T0 + 3 * D, "The widget cache rotation for gadget logs is done.")])
    assert lc.observe(P(goal, T0 + D, ["ep-note-n1"]))["state"] == "open"


def test_enrichment_cluster_is_not_evidence():
    goal = SELF + "Still open: widget cache rotation for gadget logs."
    enr = "(MemoryCluster wmtm-enrich-ep-note-x) (EventNote ev-x \"The widget cache rotation for gadget logs is done.\")"
    lc = L.Lifecycle([_note("n1", T0, goal), _note("n2", T0 + D, enr)])
    assert lc.observe(P(goal, T0 + 2 * D, ["ep-note-n1"]))["state"] == "open"


def test_superseded_by_split_item():
    multi = SELF + "Still open: widget cache rotation; gadget docs rewrite; sprocket pin compression before promotion."
    parts = [SELF + "Still open: widget cache rotation.", SELF + "Still open: gadget docs rewrite.",
             SELF + "Still open: sprocket pin compression before promotion."]
    lc = L.Lifecycle([_note("n1", T0, multi)] + [_note("n%d" % (k + 2), T0 + D, t) for k, t in enumerate(parts)])
    v1 = lc.observe(P(multi, T0 + D / 2, ["ep-note-n1"], pid="m"))
    vs = [lc.observe(P(t, T0 + 2 * D, ["ep-note-n%d" % (k + 2)], pid="p%d" % k)) for k, t in enumerate(parts)]
    assert v1["keep"] and all(v["keep"] for v in vs)
    st, why = lc.state_at(lc.goals[0], T0 + 2 * D + 1)
    assert st == "superseded" and "split" in why


def test_one_split_item_does_not_retire_the_others():
    multi = SELF + "Still open: widget cache rotation; gadget docs rewrite; sprocket pin compression before promotion."
    part = SELF + "Still open: sprocket pin compression before promotion."
    lc = L.Lifecycle([_note("n1", T0, multi), _note("n2", T0 + D, part)])
    lc.observe(P(multi, T0 + D / 2, ["ep-note-n1"], pid="m"))
    lc.observe(P(part, T0 + 2 * D, ["ep-note-n2"], pid="p"))
    assert lc.state_at(lc.goals[0], T0 + 2 * D + 1)[0] == "open"


def test_stale_without_later_topic_note_and_not_stale_with_one():
    goal = SELF + "Still open: widget cache rotation for gadget logs."
    lc = L.Lifecycle([_note("n1", T0, goal)])
    v = lc.observe(P(goal, T0 + (L.STALE_DAYS + 1) * D, ["ep-note-n1"]))
    assert v["state"] == "stale" and not v["keep"]
    lc = L.Lifecycle([_note("n1", T0, goal), _note("n2", T0 + 5 * D, "Working on widget cache rotation for gadget logs.")])
    assert lc.observe(P(goal, T0 + (L.STALE_DAYS + 1) * D, ["ep-note-n1"]))["state"] == "open"


def test_commit_subject_counts_as_closure_source():
    goal = SELF + "Still open: widget cache rotation for gadget logs."
    lc = L.Lifecycle([_note("n1", T0, goal), ("commit:abc1234", T0 + D, "widget cache rotation for gadget logs: fixed")])
    assert lc.observe(P(goal, T0 + 2 * D, ["ep-note-n1"]))["state"] == "satisfied"


def test_multi_item_goal_needs_every_item_closed():
    goal = SELF + "Still open: widget cache rotation for gadget logs; sprocket docs rewrite for gizmo pages; flange pin compression of old lines."
    one = "The flange pin compression of old lines is done."
    lc = L.Lifecycle([_note("n1", T0, goal), _note("n2", T0 + D, one)])
    assert lc.observe(P(goal, T0 + 2 * D, ["ep-note-n1"]))["state"] == "open"
    lc = L.Lifecycle([_note("n1", T0, goal), _note("n2", T0 + D, one),
                      _note("n3", T0 + D, "The widget cache rotation for gadget logs is done."),
                      _note("n4", T0 + D, "The sprocket docs rewrite for gizmo pages is done.")])
    v = lc.observe(P(goal, T0 + 2 * D, ["ep-note-n1"]))
    assert v["state"] == "satisfied" and "all 3 items" in v["reason"]


def test_different_anchors_never_supersede():
    # review 1, point 1: src/widget vs src/gadget must not merge AND must not retire each other
    a = "Remind quill about: Still waiting on quill's src/widget answer about the cache layout."
    b = "Remind quill about: Still waiting on quill's src/gadget answer about the cache layout."
    lc = L.Lifecycle([_note("n1", T0, a), _note("n2", T0 + D, b)])
    va = lc.observe(P(a, T0 + D / 2, ["ep-note-n1"], "quill", "RemindPending", "a"))
    vb = lc.observe(P(b, T0 + 2 * D, ["ep-note-n2"], "quill", "RemindPending", "b"))
    assert va["keep"] and vb["keep"] and va["gid"] != vb["gid"]
    assert lc.state_at(lc.goals[0], T0 + 2 * D + 1)[0] == "open"


def test_different_action_never_supersedes():
    a = G(SELF + "Still open: widget cache rotation for gadget logs.")
    b = G("Remind quill about: widget cache rotation for gadget logs.", "self", "RemindPending")
    a.update(gid="a", src_ts=T0, first_ts=T0); b.update(gid="b", src_ts=T0 + D, first_ts=T0 + D)
    assert L.supersedes(b, a) == ""


def test_merged_repeat_from_newer_note_moves_source_forward():
    # review 1, point 3: an old closure must not satisfy a goal re-raised by a newer "still open" note
    goal = SELF + "Still open: widget cache rotation for gadget logs."
    notes = [_note("n1", T0, goal), _note("n2", T0 + D, "The widget cache rotation for gadget logs is done."),
             _note("n3", T0 + 2 * D, goal)]
    lc = L.Lifecycle(notes)
    lc.observe(P(goal, T0 + D / 2, ["ep-note-n1"], pid="a"))
    v = lc.observe(P(goal, T0 + 3 * D, ["ep-note-n3"], pid="b"))
    assert v["state"] == "open" and lc.goals[0]["src_ts"] == T0 + 2 * D


def test_replay_final_states_use_window_end():
    # review 1, point 4: a closure after the last proposal but inside the window counts
    import os, sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
    import goal_lifecycle_replay as R
    goal = SELF + "Still open: widget cache rotation for gadget logs."
    notes = [_note("n1", 100.0, goal), _note("n2", 200.0, "The widget cache rotation for gadget logs is done.")]
    rows, goals = R.replay([P(goal, 110.0, ["ep-note-n1"])], notes, since=None, until=300.0)
    assert rows[0]["keep"] and goals[0]["state"] == "satisfied"


def test_prerequisite_task_id_words_are_not_evidence():
    # the words inside the prerequisite's id (widget, docs) must not let its CLOSED sentence satisfy the follow-up
    goal = SELF + "Still open: once t-2026-10-28-widget-docs closes, switch sprocket back to main and delete hive/w-backup."
    notes = [_note("n1", T0, goal),
             _note("n2", T0 + D, "Oct21 05:52 CLOSED t-2026-10-28-widget-docs. The widget docs passed review and are done.")]
    assert L.Lifecycle(notes).observe(P(goal, T0 + 2 * D, ["ep-note-n1"]))["state"] == "open"


def test_numbers_and_direction_keep_requests_apart():
    # review 2, point 1
    a = G(SELF + "Still open: increase widget cache retention to 30 days.")
    b = G(SELF + "Still open: increase widget cache retention to 90 days.")
    assert not L.same_goal(a, b)[0]
    c = G(SELF + "Still open: move files from src/widget to src/gadget.")
    d = G(SELF + "Still open: move files from src/gadget to src/widget.")
    assert not L.same_goal(c, d)[0]
    e = G(SELF + "Still open: rename cache -> store.")
    f = G(SELF + "Still open: rename store -> cache.")
    assert not L.same_goal(e, f)[0]
    lc = L.Lifecycle([_note("n1", T0, "x")])
    v1 = lc.observe(P(SELF + "Still open: increase widget cache retention to 30 days.", T0 + 10, ["ep-note-n1"], pid="a"))
    v2 = lc.observe(P(SELF + "Still open: increase widget cache retention to 90 days.", T0 + 20, ["ep-note-n1"], pid="b"))
    assert v1["keep"] and v2["keep"] and v1["gid"] != v2["gid"]
    # the same request still merges
    assert L.same_goal(a, G(SELF + "PENDING: increase widget cache retention to 30 days"))[0]


def test_closure_of_a_different_object_does_not_satisfy():
    # review 2, point 2
    goal = SELF + "Still open: rotate the cache logs for src/widget."
    for txt in ("The cache logs for src/gadget were rotated and are done.",):
        lc = L.Lifecycle([_note("n1", T0, goal), _note("n2", T0 + D, txt)])
        assert lc.observe(P(goal, T0 + 2 * D, ["ep-note-n1"]))["state"] == "open", txt
    lc = L.Lifecycle([_note("n1", T0, goal), _note("n2", T0 + D, "The cache logs for src/widget were rotated and are done.")])
    assert lc.observe(P(goal, T0 + 2 * D, ["ep-note-n1"]))["state"] == "satisfied"
    g30 = SELF + "Still open: set widget cache retention to 30 days."
    lc = L.Lifecycle([_note("n1", T0, g30), _note("n2", T0 + D, "Widget cache retention set to 90 days, done.")])
    assert lc.observe(P(g30, T0 + 2 * D, ["ep-note-n1"]))["state"] == "open"


def test_verb_direction_without_from_keeps_requests_apart():
    a = G(SELF + "Still open: rename widget to gadget in the docs.")
    b = G(SELF + "Still open: rename gadget to widget in the docs.")
    assert not L.same_goal(a, b)[0]
    assert L.same_goal(a, G(SELF + "PENDING: rename widget to gadget in the docs"))[0]


def test_merge_direction_and_before_after_keep_requests_apart():
    a = G(SELF + "Still open: merge hive/a into main.")
    b = G(SELF + "Still open: merge main into hive/a.")
    assert not L.same_goal(a, b)[0]
    c = G(SELF + "Still open: widget cache rotation before promotion.")
    d = G(SELF + "Still open: widget cache rotation after promotion.")
    assert not L.same_goal(c, d)[0]
    assert L.same_goal(c, G(SELF + "PENDING: widget cache rotation before promotion"))[0]


def test_negated_request_is_a_different_goal():
    # review 3, point 1
    a = G(SELF + "Still open: increase widget cache retention to 30 days.")
    b = G(SELF + "Still open: do not increase widget cache retention to 30 days.")
    assert not L.same_goal(a, b)[0]
    lc = L.Lifecycle([_note("n1", T0, "x")])
    v1 = lc.observe(P("Increase widget cache retention to 30 days.", T0 + 10, ["ep-note-n1"], pid="a"))
    v2 = lc.observe(P("Do not increase widget cache retention to 30 days.", T0 + 20, ["ep-note-n1"], pid="b"))
    assert v1["keep"] and v2["keep"] and v1["gid"] != v2["gid"]


def test_shared_entity_does_not_hide_conflicting_paths():
    # review 3, point 2
    goal = SELF + "Rotate the LTM cache logs for src/widget."
    lc = L.Lifecycle([_note("n1", T0, goal), _note("n2", T0 + D, "The LTM cache logs for src/gadget were rotated and are done.")])
    assert lc.observe(P(goal, T0 + 2 * D, ["ep-note-n1"]))["state"] == "open"
    lc = L.Lifecycle([_note("n1", T0, goal), _note("n2", T0 + D, "The LTM cache logs for src/widget were rotated and are done.")])
    assert lc.observe(P(goal, T0 + 2 * D, ["ep-note-n1"]))["state"] == "satisfied"


def test_negated_goal_is_not_closed_by_the_positive_action():
    goal = SELF + "Do not increase widget cache retention to 30 days."
    lc = L.Lifecycle([_note("n1", T0, goal), _note("n2", T0 + D, "Widget cache retention increased to 30 days, done.")])
    assert lc.observe(P(goal, T0 + 2 * D, ["ep-note-n1"]))["state"] == "open"
    lc = L.Lifecycle([_note("n1", T0, goal),
                      _note("n2", T0 + D, "Decided: we will not increase widget cache retention to 30 days; done.")])
    assert lc.observe(P(goal, T0 + 2 * D, ["ep-note-n1"]))["state"] == "satisfied"


def test_reversed_move_does_not_close_the_original():
    goal = SELF + "Move files from src/widget to src/gadget."
    lc = L.Lifecycle([_note("n1", T0, goal), _note("n2", T0 + D, "Moved files from src/gadget to src/widget, done.")])
    assert lc.observe(P(goal, T0 + 2 * D, ["ep-note-n1"]))["state"] == "open"


def test_scoped_negation_is_not_masked_by_another_negation():
    # review 4, point 1
    a = G(SELF + "Still open: increase widget cache retention to 30 days without downtime.")
    b = G(SELF + "Still open: do not increase widget cache retention to 30 days without downtime.")
    assert not L.same_goal(a, b)[0]
    lc = L.Lifecycle([_note("n1", T0, "x")])
    v1 = lc.observe(P("Increase widget cache retention to 30 days without downtime", T0 + 10, ["ep-note-n1"], pid="a"))
    v2 = lc.observe(P("Do not increase widget cache retention to 30 days without downtime", T0 + 20, ["ep-note-n1"], pid="b"))
    assert v1["keep"] and v2["keep"] and v1["gid"] != v2["gid"]
    assert L.same_goal(a, G(SELF + "PENDING: increase widget cache retention to 30 days without downtime"))[0]


def test_decision_against_an_action_does_not_satisfy_it():
    # review 4, point 2
    goal = SELF + "Increase widget cache retention to 30 days."
    lc = L.Lifecycle([_note("n1", T0, goal),
                      _note("n2", T0 + D, "Decided: we will not increase widget cache retention to 30 days; done.")])
    assert lc.observe(P(goal, T0 + 2 * D, ["ep-note-n1"]))["state"] == "open"
    lc = L.Lifecycle([_note("n1", T0, goal), _note("n2", T0 + D, "Widget cache retention was increased to 30 days and is done.")])
    assert lc.observe(P(goal, T0 + 2 * D, ["ep-note-n1"]))["state"] == "satisfied"


def test_pending_not_yet_is_not_a_prohibition():
    a = G(SELF + "Still open: merging to master needs Ben's OK, and Ben hasn't answered on src/context yet.")
    assert not any(x.startswith("@neg") for x in a["terms"])
    b = G(SELF + "Still open: do not merge to master before Ben's OK.")
    assert any(x.startswith("@neg") for x in b["terms"])


def test_yet_does_not_excuse_a_prohibition_or_decision():
    # review 5
    lc = L.Lifecycle([_note("n1", T0, "x")])
    v1 = lc.observe(P("Increase widget cache retention to 30 days", T0 + 10, ["ep-note-n1"], pid="a"))
    v2 = lc.observe(P("Do not increase widget cache retention to 30 days yet", T0 + 20, ["ep-note-n1"], pid="b"))
    assert v1["keep"] and v2["keep"] and v1["gid"] != v2["gid"]
    goal = SELF + "Increase widget cache retention to 30 days."
    lc = L.Lifecycle([_note("n1", T0, goal),
                      _note("n2", T0 + D, "DONE: We will not increase widget cache retention to 30 days yet.")])
    assert lc.observe(P(goal, T0 + 2 * D, ["ep-note-n1"]))["state"] == "open"
    for t in ["Still open: don't merge hive/a yet.", "Still open: we won't merge hive/a yet.",
              "Still open: never merge hive/a yet.", "Still open: must not merge hive/a yet."]:
        assert any(x.startswith("@neg") for x in G(SELF + t)["terms"]), t
    for t in ["Still open: Ben hasn't answered on src/context yet.", "Still open: src/context is not merged yet."]:
        assert not any(x.startswith("@neg") for x in G(SELF + t)["terms"]), t


def test_opposite_operations_are_different_goals():
    # review 6, point 1
    lc = L.Lifecycle([_note("n1", T0, "x")])
    v1 = lc.observe(P("Increase widget cache retention for expired production records to 30 days", T0 + 10, ["ep-note-n1"], pid="a"))
    v2 = lc.observe(P("Decrease widget cache retention for expired production records to 30 days", T0 + 20, ["ep-note-n1"], pid="b"))
    assert v1["keep"] and v2["keep"] and v1["gid"] != v2["gid"]
    goal = SELF + "Increase widget cache retention for expired production records to 30 days."
    lc = L.Lifecycle([_note("n1", T0, goal), _note("n2", T0 + D,
                      "Widget cache retention for expired production records was decreased to 30 days and is done.")])
    assert lc.observe(P(goal, T0 + 2 * D, ["ep-note-n1"]))["state"] == "open"


def test_not_yet_merged_does_not_satisfy():
    # review 6, point 2
    goal = SELF + "Merge widget cache changes into production."
    lc = L.Lifecycle([_note("n1", T0, goal), _note("n2", T0 + D, "Widget cache changes are not yet merged into production.")])
    assert lc.observe(P(goal, T0 + 2 * D, ["ep-note-n1"]))["state"] == "open"
    lc = L.Lifecycle([_note("n1", T0, goal), _note("n2", T0 + D, "Widget cache changes were merged into production.")])
    assert lc.observe(P(goal, T0 + 2 * D, ["ep-note-n1"]))["state"] == "satisfied"


# review 6: the adversarial probe set, kept as a fixture so every later rule change is checked against all of it
_PS = "Self-task (log only, no message): Still open: "
_PS2 = "Self-task (log only, no message): "
M=[('increase widget cache retention to 30 days','do not increase widget cache retention to 30 days',False),
 ('increase widget cache retention to 30 days','do not increase widget cache retention to 30 days yet',False),
 ('increase widget cache retention to 30 days',"don't increase widget cache retention to 30 days yet",False),
 ('increase widget cache retention to 30 days',"we will not increase widget cache retention to 30 days yet",False),
 ('increase widget cache retention to 30 days',"never increase widget cache retention to 30 days yet",False),
 ('increase widget cache retention to 30 days',"not yet: increase widget cache retention to 30 days",False),
 ('increase widget cache retention for expired production records to 30 days','decrease widget cache retention for expired production records to 30 days',False),
 ('raise widget cache retention for expired production records to 30 days','lower widget cache retention for expired production records to 30 days',False),
 ('extend widget cache retention for expired production records','shorten widget cache retention for expired production records',False),
 ('upgrade the widget cache library','downgrade the widget cache library',False),
 ('install the widget cache plugin','uninstall the widget cache plugin',False),
 ('lock the widget cache table','unlock the widget cache table',False),
 ('include widget cache records in the export','exclude widget cache records in the export',False),
 ('increase widget cache retention without downtime','decrease widget cache retention without downtime',False),
 ('do not increase widget cache retention','do not decrease widget cache retention',False),
 ('increase widget cache retention to 30 days without downtime','do not increase widget cache retention to 30 days without downtime',False),
 ('increase widget retention without downtime','increase widget retention with downtime',False),
 ('stop the widget cache job without alerting','stop the widget cache job',False),
 ('enable the widget cache flag','disable the widget cache flag',False),('add tests for widget cache','remove tests for widget cache',False),
 ('merge hive/a into main','merge main into hive/a',False),('widget cache rotation before promotion','widget cache rotation after promotion',False),
 ('rotate LTM logs for src/widget','rotate LTM logs for src/gadget',False),('retention to 30 days','retention to 30.5 days',False),
 ('never delete widget logs','delete widget logs',False),
 ('increase widget cache retention to 30 days','PENDING: increase widget cache retention to 30 days',True),
 ('increase widget cache retention to 30 days','increase the widget cache retention to 30 days',True),
 ('do not increase widget cache retention to 30 days',"don't increase widget cache retention to 30 days",True),
 ("merge to master; Ben hasn't answered on src/context yet","merge to master; Ben has not answered on src/context yet",True)]
C=[('Increase widget cache retention to 30 days.','Decided: we will not increase widget cache retention to 30 days; done.','open'),
 ('Increase widget cache retention to 30 days.','DONE: We will not increase widget cache retention to 30 days yet.','open'),
 ('Increase widget cache retention to 30 days.',"DONE: we won't increase widget cache retention to 30 days yet.",'open'),
 ('Increase widget cache retention to 30 days.','Widget cache retention was increased to 30 days and is done.','satisfied'),
 ('Increase widget cache retention to 30 days.','Widget cache retention was decreased to 30 days and is done.','open'),
 ('Increase widget cache retention for expired production records to 30 days.','Widget cache retention for expired production records was decreased to 30 days and is done.','open'),
 ('Increase widget cache retention for expired production records to 30 days.','Widget cache retention for expired production records was increased to 30 days and is done.','satisfied'),
 ('Do not increase widget cache retention to 30 days.','Widget cache retention was increased to 30 days and is done.','open'),
 ('Do not increase widget cache retention to 30 days.','Decided: we will not increase widget cache retention to 30 days; done.','satisfied'),
 ('Do not increase widget cache retention to 30 days yet.','DONE: we will not increase widget cache retention to 30 days yet.','satisfied'),
 ('Increase widget cache retention to 30 days without downtime.','Widget cache retention was increased to 30 days without downtime and is done.','satisfied'),
 ('Increase widget cache retention to 30 days without downtime.','Decided: we will not increase widget cache retention to 30 days without downtime; done.','open'),
 ('Merge widget cache changes into production.','Widget cache changes are not yet merged into production.','open'),
 ('Merge widget cache changes into production.','Widget cache changes were not merged into production.','open'),
 ('Merge widget cache changes into production.','Widget cache changes have never been merged into production.','open'),
 ('Merge widget cache changes into production.',"Widget cache changes aren't merged into production yet.",'open'),
 ('Merge widget cache changes into production.','Widget cache changes were merged into production.','satisfied'),
 ('Merge widget cache changes into production.','Widget cache changes were not tested before, but now they are merged into production.','satisfied'),
 ('Remove the stale widget cache backups.','The stale widget cache backups were removed.','satisfied'),
 ('Rotate the LTM cache logs for src/widget.','The LTM cache logs for src/gadget were rotated and are done.','open'),
 ('Rotate the LTM cache logs for src/widget.','The LTM cache logs for src/widget were rotated and are done.','satisfied'),
 ('Set widget cache retention to 30 days.','Widget cache retention set to 90 days, done.','open'),
 ('Move files from src/widget to src/gadget.','Moved files from src/gadget to src/widget, done.','open'),
 ('Rotate the cache logs for src/widget.','The cache logs for src/widget were not rotated yet.','open')]
C += [('Disable the widget cache flag.','The widget cache flag was enabled and is done.','open'),
 ('Remove the stale widget cache backups.','The stale widget cache backups were not removed.','open'),
 ('Do not remove the stale widget cache backups.','The stale widget cache backups were removed.','open')]
M += [('remove the stale widget cache backups','do not remove the stale widget cache backups',False),
 ('start the widget cache job','stop the widget cache job',False)]


def _pg(t):
    return {"text": _PS + t, "terms": L.terms(_PS + t), "who": "self", "action": "SelfTask"}


def test_adversarial_merge_probes():
    bad = [(a, b) for a, b, want in M if L.same_goal(_pg(a), _pg(b))[0] != want]
    assert not bad, bad


def test_adversarial_closure_probes():
    D_, T_ = 86400.0, 1.7e9
    bad = []
    for g, n, want in C:
        lc = L.Lifecycle([("ep-note-n1", T_, _PS2 + g), ("ep-note-n2", T_ + D_, n)])
        st = lc.observe({"text": _PS2 + g, "ts": T_ + 2 * D_, "items": ["ep-note-n1"], "who": "self",
                         "action": "SelfTask", "id": "x"})["state"]
        if st != want:
            bad.append((g, n, st))
    assert not bad, bad
