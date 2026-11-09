"""t-2026-11-10-wmtm-normaliser: one test per mapped shape (M1-M5) with a negative control, plus guards for
the three forbidden readings (F1 GroupOf->PartOf bridge, F2 modifier-as-property, F3 kind-of from witnesses)
and the count invariant (every statement counted exactly once; unrecognised never silently dropped).
Synthetic atoms only."""
from wmtm import parse_normalise as N, pc_shadow as P

NW = ["Narrow", "pilot", ["Mod", "harbour"]]
SYM = P.narrow_symbol(NW)
NWDEF = "(: nwdef_%s (Implication (Member $x %s) (Member $x pilot)) (CTV (STV 1.0 0.99) (STV 0.0 0.0)))" % (SYM, SYM)


def _n(atoms, nid="n1"):
    return N.normalise_atoms(atoms, nid)


def _total(rep):
    return sum(rep["mapped"].values()) + sum(rep["known_unused"].values()) + sum(rep["unrecognised"].values())


# M1 Interpretation wrapper
def test_m1_interpretation_unwrapped():
    out, rep = _n(['(Interpretation "x" (: f (Member a b) (STV 1.0 0.9)))'])
    assert out == ["(: f (Member a b) (STV 1.0 0.9))"] and rep["rewrites"]["M1_interpretation"] == 1


def test_m1_negative_bad_wrapper_counted_unrecognised():
    out, rep = _n(['(Interpretation "x")'])
    assert rep["mapped"] == {} and sum(rep["unrecognised"].values()) == 1 and out == ['(Interpretation "x")']


# M2 Narrow anywhere
def test_m2_narrow_as_member_class():
    out, rep = _n(["(: f (Member sk_a__i_n1 (Narrow pilot (Mod harbour))) (STV 1.0 0.9))"])
    assert out[0] == "(: f (Member sk_a__i_n1 %s) (STV 1.0 0.9))" % SYM and NWDEF in out


def test_m2_narrow_as_inheritance_argument():
    out, rep = _n(["(: f (Inheritance (Narrow pilot (Mod harbour)) person) (STV 1.0 0.9))"])
    assert out[0] == "(: f (Inheritance %s person) (STV 1.0 0.9))" % SYM and NWDEF in out
    assert P.semparse_facts(out) == [("Inheritance", SYM, "person", 1.0, 0.9)]


def test_m2_narrow_in_rule_antecedent_and_consequent():
    r = "(: r (Implication (Member $x (Narrow pilot (Mod harbour))) (Member $x (Narrow pilot (Mod harbour)))) (STV 1.0 1.0))"
    out, rep = _n([r])
    assert out[0] == "(: r (Implication (Member $x %s) (Member $x %s)) (STV 1.0 1.0))" % (SYM, SYM)
    assert rep["mapped"]["rule"] == 1


def test_m2_nested_narrow_defines_each_level():
    out, rep = _n(["(: f (Member a (Narrow (Narrow pilot (Mod harbour)) (Mod night))) (STV 1.0 0.9))"])
    assert NWDEF in out and rep["nwdef"] == 2


def test_m2_negative_narrow_with_nonsymbol_base_not_named():
    a = "(: f (Member a (Narrow (X y) (Mod h))) (STV 1.0 0.9))"
    out, rep = _n([a])
    assert out == [a] and rep["nwdef"] == 0 and sum(rep["unrecognised"].values()) == 1


def test_m2_negative_narrow_inside_unmapped_statement_gets_no_nwdef():
    a = "(: g (GroupOf sk_g__i_n1 (Narrow pilot (Mod harbour))) (STV 1.0 0.9))"
    out, rep = _n([a])
    assert out == [a] and rep["nwdef"] == 0 and rep["unrecognised"]["(GroupOf sk (Narrow S (Mod ..)))"] == 1


# M3 legacy flat Inheritance
def test_m3_flat_inheritance_passes_through():
    a = "(: f (Inheritance cat mammal) (STV 1.0 0.9))"
    out, rep = _n([a])
    assert out == [a] and rep["mapped"]["fact:Inheritance"] == 1


def test_m3_negative_inheritance_with_string_not_mapped():
    a = '(: f (Inheritance cat "mammal") (STV 1.0 0.9))'
    out, rep = _n([a])
    assert out == [a] and rep["mapped"] == {} and sum(rep["unrecognised"].values()) == 1


# M4 legacy Premises/Conclusions
def test_m4_premises_conclusions_to_and_one_rule_per_conclusion():
    r = "(: r (Implication (Premises (Member $x a) (Member $x b)) (Conclusions (Member $x c) (Member $x d))) (STV 1.0 0.9))"
    out, rep = _n([r])
    assert out == ["(: r_c1 (Implication (And (Member $x a) (Member $x b)) (Member $x c)) (STV 1.0 0.9))",
                   "(: r_c2 (Implication (And (Member $x a) (Member $x b)) (Member $x d)) (STV 1.0 0.9))"]
    assert rep["mapped"]["rule"] == 2 and len(P._parse_rules(out)) == 2


def test_m4_negative_conclusion_not_binary_counted():
    r = "(: r (Implication (Premises (Member $x a)) (Conclusions (Not (Member $x c)))) (STV 1.0 0.9))"
    out, rep = _n([r])
    assert rep["mapped"] == {} and sum(rep["unrecognised"].values()) == 1


# M5 catalog-mode facts and rules
def test_m5_catalog_member_and_rule_mapped_unchanged():
    a = ["(: f (Member sk_c__i_n1 config) (STV 1.0 0.9))",
         "(: r (Implication (Member $x config) (Member $x file)) (STV 1.0 0.9))"]
    out, rep = _n(a)
    assert out == a and rep["mapped"] == {"fact:Member": 1, "rule": 1}


def test_m5_negative_event_role_unrecognised_by_note():
    out, rep = _n(["(: e (Patient sk_e__i_n7 sk_x__i_n7) (STV 1.0 0.9))"], "n7")
    assert rep["unrecognised_by_note"]["n7"] == {"(Patient sk sk)": 1} and rep["mapped"] == {}


def test_known_unused_counted_not_unrecognised():
    out, rep = _n(['(: l (Name sk_a__i_n1 "Ann") (STV 1.0 0.9))', "(: t (Past sk_e__i_n1) (STV 1.0 0.9))"])
    assert rep["known_unused"] == {"Name": 1, "Past": 1} and rep["unrecognised"] == {}


# Forbidden readings
def test_f1_no_groupof_partof_bridge():
    a = ["(: g (GroupOf sk_g__i_n1 pilot) (STV 1.0 0.9))", "(: m (Member sk_a__i_n1 pilot) (STV 1.0 0.9))",
         "(: r (Implication (PartOf $x sk_g__i_n1) (Member $x crew)) (STV 1.0 0.9))"]
    out, rep = _n(a)
    assert not any("(PartOf sk_" in o for o in out)                       # no PartOf fact invented
    assert rep["unrecognised"]["(GroupOf sk S)"] == 1
    rel = {(h, x, y) for (h, x, y, _s, _c) in P.semparse_facts(out)}
    assert P.rule_goal_pool(rel, [o for o in out if "Implication" in o]) == {}


def test_f2_modifier_never_a_property():
    out, _ = _n(["(: f (Member sk_s__i_n1 (Narrow suite (Mod test))) (STV 1.0 0.9))"])
    assert not any("(Member $x test)" in o or "(Member sk_s__i_n1 test)" in o for o in out)
    nw = P.narrow_symbol(["Narrow", "suite", ["Mod", "test"]])
    assert [o for o in out if o.startswith("(: nwdef_")] == [
        "(: nwdef_%s (Implication (Member $x %s) (Member $x suite)) (CTV (STV 1.0 0.99) (STV 0.0 0.0)))" % (nw, nw)]


def test_f3_no_kind_of_from_witness():
    out, _ = _n(["(: f (Member sk_config_1__i_n1 config) (STV 1.0 0.9))",
                 "(: g (Member sk_config_1__i_n1 file) (STV 1.0 0.9))"])
    assert not any("Inheritance" in o for o in out)


def test_output_never_adds_facts_only_nwdef_rules():
    a = ["(: f (Member sk_a__i_n1 (Narrow pilot (Mod harbour))) (STV 1.0 0.9))", "(: e (Agent sk_e sk_a) (STV 1 1))"]
    out, _ = _n(a)
    assert len(out) == len(a) + 1 and out[-1].startswith("(: nwdef_")


def test_every_statement_counted_once_and_unrecognised_kept():
    a = ["(: f (Member a b) (STV 1 1))", "(: g (GroupOf sk_g c) (STV 1 1))", "(broken",
         '(: l (Name sk_a "A") (STV 1 1))', "(Directive (Not x))"]
    out, rep = _n(a)
    assert _total(rep) == 5 and sum(rep["unrecognised"].values()) == 3
    assert "(: g (GroupOf sk_g c) (STV 1 1))" in out


def test_report_json_has_no_text():
    _, rep = _n(['(: l (Name sk_a__i_n1 "Secret Text") (STV 1 1))', '(: q (Quote sk_a "Secret Text") (STV 1 1))'])
    import json
    assert "Secret" not in json.dumps(N.report_json(rep))
