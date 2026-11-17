"""t-2026-11-17-wmtm-extra-rules-v2: wmtm/rules/extra_rules.pettachainer-master.metta on synthetic facts only
(no note-derived content).  Goal building (master_loader.rule_goals) with and without the extra rules."""
from wmtm import master_loader as ML

L = "(: f%d %s (STV 1.0 0.99))"
IDS = {"xr_supersedes_not_current_ap", "xr_supersedes_not_current_bt", "xr_contradicts_not_ap", "xr_contradicts_not_bt"}


def _ops(facts):
    return [("atom", L % (i, f)) for i, f in enumerate(facts)]


def _goals(facts, extra=True):
    rules = ML.extra_rules() if extra else []
    ops = [("atom", r) for r in rules] + _ops(facts)
    return ML.rule_goals(ops, rules, scoped={ML._node(r)[1] for r in rules})


def test_file_parses_and_ids_exact():
    rs = ML.extra_rules()
    ids = [ML._node(r)[1] for r in rs]
    assert len(rs) == 4 and set(ids) == IDS
    assert all(ML._node(r)[2][0] == "Implication" for r in rs)


def test_dropped_rules_absent():
    text = open(ML.EXTRA_RULES, encoding="utf-8").read()
    for gone in ("xr_directive_inherit", "xr_close_closes", "xr_hour_order", "xr_minute_order", "Compute"):
        assert gone not in text


def test_supersedes_not_current_both_frames():
    g, _ = _goals(["(Member s1 supersede)", "(Patient s1 n1)", "(Member s2 supersede)", "(Theme s2 n2)"])
    assert g["(Not (Current n1))"] == "xr_supersedes_not_current_ap"
    assert g["(Not (Current n2))"] == "xr_supersedes_not_current_bt"


def test_contradicts_not():
    g, _ = _goals(["(Member c1 contradict)", "(Theme c1 n1)", "(Member c2 contradict)", "(Patient c2 n2)"])
    assert g["(Not (Valid n1))"] == "xr_contradicts_not_bt"
    assert g["(Not (Valid n2))"] == "xr_contradicts_not_ap"


def test_negative_controls():
    g, _ = _goals(["(Time e1 t1)", "(Hour t1 5)", "(Time e2 t2)", "(Hour t2 11)",
                   "(Member s1 replace)", "(Patient s1 n1)", "(Member x1 task)", "(Directive (Member p1 post))",
                   "(Member c1 close)", "(Patient c1 t1)", "(Past c1)"])
    assert g == {}


def test_flag_off_unchanged():
    facts = ["(Member s1 supersede)", "(Patient s1 n1)", "(Member c1 contradict)", "(Theme c1 n2)"]
    g, per = _goals(facts, extra=False)
    assert g == {} and per == {}


def test_scoped_one_note_only():
    a, b = "__ep_note_20261101T000000Z", "__ep_note_20261102T000000Z"
    g, _ = _goals(["(Member s1%s supersede)" % a, "(Patient s1%s n1%s)" % (a, b)])          # cross-note: refused
    assert g == {}
    g2, _ = _goals(["(Member s1%s supersede)" % a, "(Patient s1%s n1%s)" % (a, a)])         # same note: kept
    assert g2.get("(Not (Current n1%s))" % a) == "xr_supersedes_not_current_ap"
    g3, _ = _goals(["(Member s1%s supersede)" % a, "(Patient s1%s named_doc)" % a])         # named individual: no suffix
    assert "(Not (Current named_doc))" in g3


def test_scoping_not_applied_to_unscoped_rules():
    a, b = "__ep_note_20261101T000000Z", "__ep_note_20261102T000000Z"
    seeded = "(: s_x (Implication (And (Member $s supersede) (Patient $s $y)) (Old $y)) (CTV (STV 1.0 0.9) (STV 0.0 0.001)))"
    ops = [("atom", seeded)] + _ops(["(Member s1%s supersede)" % a, "(Patient s1%s n1%s)" % (a, b)])
    g, _ = ML.rule_goals(ops, [seeded], scoped=IDS)
    g0, _ = ML.rule_goals(ops, [seeded])
    assert g == g0 and g == {"(Old n1%s)" % b: "s_x"}
