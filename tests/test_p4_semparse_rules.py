"""P4: nested parser forms - Narrow classes named by deterministic symbols plus defining rules
(STOPGAP(upstream: F7)), and Implication/Equivalence rules in the shadow KB."""
from wmtm import pc_shadow

R1 = "(: r1 (Implication (Member $x pilot) (Member $x person)) (CTV (STV 0.95 0.9) (STV 0.0 0.0)))"
R2 = "(: r2 (Implication (And (Member $x pilot) (Member $x harbourish)) (Member $x sailor)) (CTV (STV 0.95 0.9) (STV 0.0 0.0)))"
RN = "(: r3 (Implication (Member $x (Narrow pilot (Mod harbour))) (Member $x p)) (STV 1.0 1.0))"
FN = "(: f1 (Member sk_a (Narrow pilot (Mod harbour))) (STV 1.0 0.9))"
SYM = pc_shadow.narrow_symbol(["Narrow", "pilot", ["Mod", "harbour"]])


def test_narrow_symbol_deterministic_and_restriction_sensitive():
    a = pc_shadow.narrow_symbol(["Narrow", "pilot", ["Mod", "harbour"]])
    b = pc_shadow.narrow_symbol(["Narrow", "pilot", ["Mod", "harbour"]])
    c = pc_shadow.narrow_symbol(["Narrow", "pilot", ["Mod", "river"]])
    assert a == b and a != c and a.startswith("pilot__nw_")


def test_narrow_fact_named_not_lowered():
    d = {}
    fs = pc_shadow.semparse_facts([FN], d)
    assert fs == [("Member", "sk_a", SYM, 1.0, 0.9)]
    assert d == {SYM: "pilot"}


def test_defining_rule_emitted_for_fact_class():
    d = {}
    pc_shadow.semparse_facts([FN], d)
    rs = pc_shadow.semparse_rules([FN], d)
    assert rs == ["(: nwdef_%s (Implication (Member $x %s) (Member $x pilot)) (CTV (STV 1.0 0.99) (STV 0.0 0.0)))" % (SYM, SYM)]


def test_narrow_rule_rewritten_with_symbol():
    rs = pc_shadow.semparse_rules([RN])
    assert rs[0] == "(: r3 (Implication (Member $x %s) (Member $x p)) (STV 1.0 1.0))" % SYM
    assert any(r.startswith("(: nwdef_%s " % SYM) for r in rs)


def test_nested_narrow_chain_defines_each_level():
    d = {}
    fs = pc_shadow.semparse_facts(["(: f (Member a (Narrow (Narrow pilot (Mod harbour)) (Mod night))) (STV 1.0 0.9))"], d)
    assert len(fs) == 1 and len(d) == 2 and SYM in d and d[SYM] == "pilot" and d[fs[0][2]] == SYM


def test_interpretation_wrapper_and_flat_unchanged():
    fs = pc_shadow.semparse_facts(['(Interpretation "x" (: f (Inheritance cat mammal) (STV 1.0 0.9)))'])
    assert fs == [("Inheritance", "cat", "mammal", 1.0, 0.9)]


def test_flat_rules_kept_and_deduped():
    rs = pc_shadow.semparse_rules([R1, R2, R1])
    assert rs == [R1, R2]


def test_rules_ignore_facts_and_garbage():
    assert pc_shadow.semparse_rules(["(: f (Member a b) (STV 1 1))", "(broken", ""]) == []


def test_narrow_with_nonsymbol_base_not_named():
    assert pc_shadow.semparse_facts(["(: f (Member a (Narrow (X y) (Mod h))) (STV 1.0 0.9))"]) == []
