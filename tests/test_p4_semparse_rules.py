"""P4: nested parser forms - Narrow class lowering (F7) and Implication rules in the shadow KB."""
from wmtm import pc_shadow

R1 = "(: r1 (Implication (Member $x pilot) (Member $x person)) (CTV (STV 0.95 0.9) (STV 0.0 0.0)))"
R2 = "(: r2 (Implication (And (Member $x pilot) (Member $x harbourish)) (Member $x sailor)) (CTV (STV 0.95 0.9) (STV 0.0 0.0)))"
RN = "(: r3 (Implication (Member $x (Narrow pilot (Mod h))) (Member $x p)) (STV 1.0 1.0))"


def test_narrow_lowered_to_base_class():
    fs = pc_shadow.semparse_facts(["(: f1 (Member sk_a (Narrow pilot (Mod harbour))) (STV 1.0 0.9))"])
    assert fs == [("Member", "sk_a", "pilot", 1.0, 0.9)]


def test_narrow_and_twin_deduped():
    fs = pc_shadow.semparse_facts(["(: f1 (Member sk_a (Narrow pilot (Mod harbour))) (STV 1.0 0.9))",
                                   "(: f2 (Member sk_a pilot) (STV 1.0 0.9))"])
    assert fs == [("Member", "sk_a", "pilot", 1.0, 0.9)]


def test_interpretation_wrapper_and_flat_unchanged():
    fs = pc_shadow.semparse_facts(['(Interpretation "x" (: f (Inheritance cat mammal) (STV 1.0 0.9)))'])
    assert fs == [("Inheritance", "cat", "mammal", 1.0, 0.9)]


def test_rules_kept_flat_member_only():
    rs = pc_shadow.semparse_rules([R1, R2, RN, R1])
    assert rs == [R1, R2]


def test_rules_ignore_facts_and_garbage():
    assert pc_shadow.semparse_rules(["(: f (Member a b) (STV 1 1))", "(broken", ""]) == []


def test_narrow_with_nonsymbol_base_not_lowered():
    assert pc_shadow.semparse_facts(["(: f (Member a (Narrow (X y) (Mod h))) (STV 1.0 0.9))"]) == []
