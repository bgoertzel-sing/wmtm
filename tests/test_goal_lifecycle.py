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
    notes = [_note("n1", T0, "Still open: once t-2026-10-28-widget-docs closes, delete branch hive/w-backup."),
             _note("n2", T0 + D, "Oct21 05:52 CLOSED t-2026-10-28-widget-docs. It passed review.")]
    lc = L.Lifecycle(notes)
    v = lc.observe(P(SELF + "Still open: once t-2026-10-28-widget-docs closes, delete branch hive/w-backup.",
                     T0 + 2 * D, ["ep-note-n1"]))
    assert v["state"] == "satisfied" and "ep-note-n2" in v["reason"] and "names task" in v["reason"]


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
