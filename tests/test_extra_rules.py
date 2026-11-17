"""t-2026-11-17-wmtm-extra-rules: wmtm/rules/extra_rules.pettachainer-master.metta on synthetic facts only
(no note-derived content).  Goal building (master_loader.rule_goals) with and without the extra rules."""
from wmtm import master_loader as ML

L = "(: f%d %s (STV 1.0 0.99))"


def _ops(facts):
    return [("atom", L % (i, f)) for i, f in enumerate(facts)]


def _goals(facts, extra=True):
    rules = ML.extra_rules() if extra else []
    ops = [("atom", r) for r in rules] + _ops(facts)
    return ML.rule_goals(ops, rules, compute=extra, scoped={ML._node(r)[1] for r in rules})


def test_file_parses_and_ids_unique():
    rs = ML.extra_rules()
    ids = [ML._node(r)[1] for r in rs]
    assert len(rs) == 8 and len(set(ids)) == 8 and all(i.startswith("xr_") for i in ids)
    assert all(ML._node(r)[2][0] == "Implication" for r in rs)


def test_hour_order():
    g, per = _goals(["(Time e1 t1)", "(Hour t1 5)", "(Time e2 t2)", "(Hour t2 11)"])
    assert "(Before e1 e2)" in g and "(Before e2 e1)" not in g
    assert per.get("xr_hour_order") == 1


def test_minute_order_same_hour_only():
    g, _ = _goals(["(Time e1 t1)", "(Hour t1 5)", "(Minute t1 4)", "(Time e2 t2)", "(Hour t2 5)", "(Minute t2 52)"])
    assert g.get("(Before e1 e2)") == "xr_minute_order" and "(Before e2 e1)" not in g


def test_supersedes_not_current_both_frames():
    g, _ = _goals(["(Member s1 supersede)", "(Patient s1 n1)", "(Member s2 supersede)", "(Theme s2 n2)"])
    assert g["(Not (Current n1))"] == "xr_supersedes_not_current_ap"
    assert g["(Not (Current n2))"] == "xr_supersedes_not_current_bt"


def test_contradicts_not():
    g, _ = _goals(["(Member c1 contradict)", "(Theme c1 n1)", "(Member c2 contradict)", "(Patient c2 n2)"])
    assert "(Not (Valid n1))" in g and "(Not (Valid n2))" in g


def test_directive_inherit():
    g, _ = _goals(["(Directive (Member p1 post))", "(Member t1 task)"])
    assert g["(Applies (Member p1 post) t1)"] == "xr_directive_inherit"


def test_close_closes_needs_past():
    g, _ = _goals(["(Member c1 close)", "(Patient c1 t1)", "(Past c1)"])
    assert g.get("(Member t1 closed)") == "xr_close_closes"
    g2, _ = _goals(["(Member c1 close)", "(Patient c1 t1)"])          # not past
    assert "(Member t1 closed)" not in g2
    g3, _ = _goals(["(Member p1 pass)", "(Agent p1 r1)", "(Member r1 review)", "(Past p1)"])   # pass alone closes nothing
    assert g3 == {}


def test_negative_controls():
    g, _ = _goals(["(Time e1 t1)", "(Hour t1 11)", "(Time e2 t2)", "(Hour t2 11)",
                   "(Member s1 replace)", "(Patient s1 n1)", "(Member x1 task)"])
    assert g == {}


def test_flag_off_unchanged():
    facts = ["(Time e1 t1)", "(Hour t1 5)", "(Time e2 t2)", "(Hour t2 11)", "(Member s1 supersede)", "(Patient s1 n1)"]
    g, per = _goals(facts, extra=False)
    assert g == {} and per == {}


def test_compute_only_numbers():
    p = ["Compute", "<", ["$a", "$b"], "->", "true"]
    assert ML._compute_ok(p, {"$a": "5", "$b": "11"})
    assert not ML._compute_ok(p, {"$a": "11", "$b": "5"})
    assert not ML._compute_ok(p, {"$a": "october", "$b": "5"})
    assert not ML._compute_ok(p, {"$a": "5"})


def test_scoped_one_note_only():
    a, b = "__ep_note_20261101T000000Z", "__ep_note_20261102T000000Z"
    g, _ = _goals(["(Directive d1%s)" % a, "(Member t1%s task)" % b])          # cross-note: refused
    assert g == {}
    g2, _ = _goals(["(Directive d1%s)" % a, "(Member t1%s task)" % a])         # same note: kept
    assert g2.get("(Applies d1%s t1%s)" % (a, a)) == "xr_directive_inherit"
    g3, _ = _goals(["(Directive d1%s)" % a, "(Member named_task task)"])       # named individual: no suffix
    assert "(Applies d1%s named_task)" % a in g3


def test_compute_not_applied_to_unscoped_rules():
    seeded = "(: s_year (Implication (And (Year $a $y1) (Year $b $y2) (Compute < ($y1 $y2) -> true)) (Before $a $b)) (CTV (STV 1.0 0.9) (STV 0.0 0.001)))"
    ops = [("atom", seeded)] + _ops(["(Year a 2020)", "(Year b 2021)"])
    g, _ = ML.rule_goals(ops, [seeded], compute=True, scoped={"xr_hour_order"})
    # Compute premise of a seeded rule is never evaluated: no head match for Compute -> no goals, same as flag off
    g0, _ = ML.rule_goals(ops, [seeded], compute=False)
    assert g == g0
