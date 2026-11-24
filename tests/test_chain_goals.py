"""t-2026-11-24-wmtm-r02-chaining: synthetic tests for master_loader.chain_goals (flag shadow_chain_k, default off)."""
from wmtm import master_loader as ML, runtime_config as rc

N1 = "__ep_note_20261124T000001Z"
N2 = "__ep_note_20261124T000002Z"


def A(name, term):
    return ("atom", "(: %s %s (STV 1.0 0.9))" % (name, term))


def R(name, prem, concl):
    return "(: %s (Implication %s %s) (STV 1.0 0.9))" % (name, prem, concl)


def run(facts, rules, k, note_src=None):
    ops = [("atom", r) for r in rules] + facts
    return ML.chain_goals(ops, rules, k=k, note_src=note_src)


def test_flag_default_off():
    assert rc.resolve().get("shadow_chain_k") in (0, None)


def test_chain_fires_rules_and_class_links():
    rules = [R("r1", "(P $x)", "(Q $x)"), R("r2", "(Q $x)", "(S $x)")]
    facts = [A("f1", "(P a%s)" % N1), A("m1", "(Member b%s Dog)" % N1),
             A("i1", "(Inheritance Dog Animal)"), A("i2", "(Inheritance Animal Thing)")]
    g, st = run(facts, rules, 2)
    assert g["(S a%s)" % N1] == "chain2:r2"
    assert "(Q a%s)" % N1 not in g                  # step 1 is rule_goals' job
    assert g["(Inheritance Dog Thing)"] == "chain1:chain_inh_trans"
    assert g["(Member b%s Animal)" % N1] == "chain1:chain_inh_member"
    assert g["(Member b%s Thing)" % N1].startswith("chain2:")
    g1, _ = run(facts, rules, 1)
    assert "(S a%s)" % N1 not in g1


def test_cycle_terminates():
    rules = [R("r1", "(P $x)", "(Q $x)"), R("r2", "(Q $x)", "(P $x)"),
             R("r3", "(Q $x)", "(S $x)")]
    facts = [A("f1", "(P a%s)" % N1), A("i1", "(Inheritance X Y)"), A("i2", "(Inheritance Y X)")]
    g, st = run(facts, rules, 10)
    assert st["steps"] <= 3 and not st["budget_hit"]
    assert set(st["per_step"].values()) <= {0, 1, 2}
    assert "(S a%s)" % N1 in g


def test_cross_note_does_not_chain_unless_shared():
    rules = [R("r1", "(P $x)", "(Q $x)"), R("r2", "(And (Q $x) (S $y))", "(T $x $y)")]
    facts = [A("f1", "(P a%s)" % N1), A("f2", "(S b%s)" % N2)]
    g, st = run(facts, rules, 3)
    assert not any(x.startswith("(T ") for x in g)
    assert st["cross_note_refused"] >= 1
    g2, _ = run(facts + [A("f3", "(S c)")], rules, 3)   # shared premise (no note suffix) may join one note
    assert "(T a%s c)" % N1 in g2
    assert "(T a%s b%s)" % (N1, N2) not in g2


def test_cap_counts():
    rules = [R("r1", "(P $x)", "(Q $x)"), R("r2", "(Q $x)", "(S $x)")]
    facts = [A("f%d" % i, "(P a%d%s)" % (i, N1)) for i in range(5)]
    g, st = ML.chain_goals([("atom", r) for r in rules] + facts, rules, k=2, max_per_note=2)
    assert len(g) == 2 and st["capped"] == 3


def test_cross_note_by_source_label_without_suffix():
    """A fact with no note suffix but stated in note 2 belongs to note 2: it must not join a note-1 chain."""
    rules = [R("r1", "(P $x)", "(Q $x)"), R("r2", "(And (Q $x) (S $y))", "(T $x $y)")]
    facts = [A("f1", "(P a%s)" % N1), A("f2", "(S bob)")]
    g, st = run(facts, rules, 3, note_src={"f2": "ep-note-20261124T000002Z"})
    assert "(T a%s bob)" % N1 not in g and st["cross_note_refused"] >= 1
    g2, _ = run(facts + [A("f3", "(S bob)")], rules, 3,
                note_src={"f2": "ep-note-20261124T000002Z", "f3": "ep-note-20261124T000001Z"})
    assert "(T a%s bob)" % N1 in g2                 # stated in both notes: shared premise
    g3, _ = run(facts, rules, 3)                    # no source given: free (definition-like)
    assert "(T a%s bob)" % N1 in g3


def test_no_coref_gate():
    rules = [R("r1", "(P $x)", "(Member $x K)"), R("cm", "(And (Coref $m $a) (Member $m $k))", "(Member $a $k)"),
             R("r2", "(Member $x K)", "(S $x)")]
    facts = [A("f1", "(P a%s)" % N1), A("c1", "(Coref a%s b%s)" % (N1, N1))]
    g, st = ML.chain_goals([("atom", r) for r in rules] + facts, rules, k=3)
    assert "(Member b%s K)" % N1 in g
    g2, st2 = ML.chain_goals([("atom", r) for r in rules] + facts, rules, k=3, no_coref=True)
    assert "(Member b%s K)" % N1 not in g2 and "(S a%s)" % N1 in g2 and st2["coref_gated"] >= 1
