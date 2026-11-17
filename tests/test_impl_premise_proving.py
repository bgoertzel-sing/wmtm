"""t-2026-11-17-wmtm-impl-premise-proving: note_impl_premise_goals on synthetic atoms only (v2: stopgaps removed, literal() same-note)."""
from wmtm import master_loader as ML

A = "__ep_note_20990101T000000Z"
B = "__ep_note_20990102T000000Z"


def _a(lab, body):
    return ("atom", f"(: {lab} {body} (STV 1.0 0.9))")


IMPL = "(Implication (And (Member $x thing) (Member $x acoustic)) (Member $x quiet))"


def test_premise_not_literal_builds_same_note_goal():
    lab = "s1_r1_implication" + A
    ops = [_a(lab, IMPL), _a("s2_c1_member" + A, f"(Member sk_lute_1{A} acoustic)")]
    goals, st = ML.note_impl_premise_goals(ops, [], [lab])
    assert goals == {f"(Member sk_lute_1{A} quiet)": "nimplp:" + lab}
    assert st["premise_not_literal"] == 1 and st["goals"] == 1


def test_never_binds_across_notes():
    lab = "s1_r1_implication" + A
    ops = [_a(lab, IMPL), _a("s2_c1_member" + B, f"(Member sk_lute_1{B} acoustic)"),
           _a("s3_c1_member" + B, "(Member alice acoustic)")]
    goals, st = ML.note_impl_premise_goals(ops, [], [lab])
    assert goals == {} and st["candidates"] == 0


def test_literal_premise_left_to_one_step_builder():
    lab = "s1_r1_implication" + A
    ops = [_a(lab, "(Implication (Member $x acoustic) (Member $x quiet))"),
           _a("s2_c1_member" + A, "(Member lute acoustic)")]
    goals, st = ML.note_impl_premise_goals(ops, [], [lab])
    assert goals == {} and st["premise_literal"] == 1


def test_unrelated_entities_are_not_candidates_and_cap():
    lab = "s1_r1_implication" + A
    ops = [_a(lab, IMPL), _a("s2_m" + A, "(Member rock hard)")]
    ops += [_a("s3_m%d" % i + A, "(Member e%d acoustic)" % i) for i in range(5)]
    goals, st = ML.note_impl_premise_goals(ops, [], [lab], max_cands=2)
    assert set(goals) == {"(Member e0 quiet)", "(Member e1 quiet)"} and st["capped"] == 3


def test_stated_conclusion_and_multi_var_skipped():
    lab = "s1_r1_implication" + A
    ops = [_a(lab, IMPL), _a("s2_m" + A, "(Member lute acoustic)"), _a("s3_m" + A, "(Member lute quiet)"),
           _a("s4_r" + A, "(Implication (And (Member $x thing) (Agent $e $x)) (Agent $e $y))")]
    goals, st = ML.note_impl_premise_goals(ops, [], [lab, "s4_r" + A])
    assert goals == {} and st["concl_stated"] == 1 and st["multi_var_concl"] == 1


def test_seeded_rules_ignored():
    rule = "(: r1 %s (STV 1.0 0.9))" % IMPL
    ops = [("atom", rule), _a("s2_m" + A, "(Member lute acoustic)")]
    goals, st = ML.note_impl_premise_goals(ops, [rule], ["r1"])
    assert goals == {} and st["note_impl"] == 0


def test_literal_premise_in_other_note_does_not_block():
    """v2: literal() reads only the implication's own note; a premise stated literally only in note B does not
    block note A's goal, and B's entity is never a candidate."""
    lab = "s1_r1_implication" + A
    ops = [_a(lab, IMPL), _a("s2_m" + A, f"(Member sk_lute_1{A} acoustic)"),
           _a("s3_t" + B, f"(Member sk_harp_1{B} thing)"), _a("s4_m" + B, f"(Member sk_harp_1{B} acoustic)")]
    goals, st = ML.note_impl_premise_goals(ops, [], [lab])
    assert goals == {f"(Member sk_lute_1{A} quiet)": "nimplp:" + lab}
    assert st["premise_literal"] == 0 and st["premise_not_literal"] == 1 and st["candidates"] == 1


def test_literal_premise_in_own_note_still_left_to_one_step_builder():
    lab = "s1_r1_implication" + A
    ops = [_a(lab, IMPL), _a("s2_t" + A, f"(Member sk_lute_1{A} thing)"), _a("s3_m" + A, f"(Member sk_lute_1{A} acoustic)"),
           _a("s4_m" + B, f"(Member sk_harp_1{B} acoustic)")]
    goals, st = ML.note_impl_premise_goals(ops, [], [lab])
    assert goals == {} and st["premise_literal"] == 1


def test_no_stopgap_code():
    import wmtm.runtime_config as rc
    assert not hasattr(ML, "lowering_stopgaps") and "shadow_lowering_stopgaps" not in rc.SPEC


def test_flags_off_by_default():
    from wmtm import runtime_config as rc
    r = rc.resolve()
    assert r["shadow_note_impl_premise"] is False
