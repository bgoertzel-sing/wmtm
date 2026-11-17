"""t-2026-11-17-wmtm-note-implication-goals-v2: note_impl_goals on synthetic atoms only (no note-derived content)."""
from wmtm import master_loader as ML

A = "__ep_note_20990101T000000Z"
B = "__ep_note_20990102T000000Z"


def _impl(lab, body):
    return ("atom", f"(: {lab} {body} (STV 1.0 0.9))")


def _fact(lab, body):
    return ("atom", f"(: {lab} {body} (STV 1.0 0.9))")


def test_one_step_own_note():
    ops = [_impl("s1_x1_implication" + A, f"(Implication (Member $x quilt{A}) (Member $x textile{A}))"),
           _fact("s1_m1" + A, f"(Member q1{A} quilt{A})")]
    goals, st = ML.note_impl_goals(ops, [], ["s1_x1_implication" + A])
    assert goals == {f"(Member q1{A} textile{A})": "nimpl:s1_x1_implication" + A}
    assert st["goals"] == 1 and st["cross_note"] == 0


def test_cross_note_binding_dropped():
    ops = [_impl("s1_x1_implication" + A, "(Implication (Member $x quilt) (Member $x textile))"),
           _fact("s1_m1" + B, f"(Member q1{B} quilt)")]
    goals, st = ML.note_impl_goals(ops, [], ["s1_x1_implication" + A])
    assert goals == {} and st["cross_note"] == 1


def test_named_individual_kept():
    ops = [_impl("s1_x1_implication" + A, "(Implication (Member $x quilt) (Member $x textile))"),
           _fact("s1_m1" + A, "(Member alice quilt)")]
    goals, _ = ML.note_impl_goals(ops, [], ["s1_x1_implication" + A])
    assert goals == {"(Member alice textile)": "nimpl:s1_x1_implication" + A}


def test_premise_missing_and_stated_conclusion():
    lab = "s1_x1_implication" + A
    ops = [_impl(lab, "(Implication (Member $x quilt) (Member $x textile))"),
           _fact("s1_m1" + A, "(Member bob quilt)"), _fact("s1_m2" + A, "(Member bob textile)")]
    goals, st = ML.note_impl_goals(ops, [], [lab])
    assert goals == {} and st["concl_stated"] == 1
    goals, st = ML.note_impl_goals(ops[:1], [], [lab])
    assert goals == {} and st["premise_missing"] == 1


def test_biimplication_both_directions():
    lab = "s1_x1_implication" + A
    ops = [_impl(lab, "(BiImplication (Member $x quilt) (Member $x textile))"),
           _fact("s1_m1" + A, "(Member p quilt)"), _fact("s1_m2" + A, "(Member r textile)")]
    goals, st = ML.note_impl_goals(ops, [], [lab])
    assert set(goals) == {"(Member p textile)", "(Member r quilt)"} and st["bi"] == 1


def test_seeded_rules_and_unlabelled_implications_ignored():
    rule = "(: r1 (Implication (Member $x quilt) (Member $x textile)) (STV 1.0 0.9))"
    ops = [("atom", rule), _fact("s1_m1" + A, "(Member q quilt)")]
    goals, st = ML.note_impl_goals(ops, [rule], ["r1"])
    assert goals == {} and st["note_impl"] == 0
    goals, st = ML.note_impl_goals(ops[1:] + [_impl("other", "(Implication (Member $x quilt) (Member $x cloth))")], [], [])
    assert goals == {} and st["note_impl"] == 0


def test_flags_off_by_default():
    from wmtm import runtime_config as rc
    r = rc.resolve()
    assert r["shadow_note_impl_goals"] is False and r["shadow_extra_rules_drop"] == ""
