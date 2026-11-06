"""P4 rev3: parser Implication rules propose goals (real atoms from cached parse of note 20261028T190214Z)."""
from wmtm import pc_shadow as ps

FACT = ("Member", "hive_t_2026_10_28_goalchainer_v2_status", "branch__nw_50b94ee13a")
RULES = [
    "(: i_ep_note_20261028T190214Z__n7_implication (Implication (Member hive_t_2026_10_28_goalchainer_v2_status branch__nw_50b94ee13a) (Member hive_t_2026_10_28_goalchainer_v2_status local)) (STV 0.9 0.7))",
    "(: nwdef_branch__nw_50b94ee13a (Implication (Member $x branch__nw_50b94ee13a) (Member $x branch)) (CTV (STV 1.0 0.99) (STV 0.0 0.0)))",
]

def test_parsed_rule_proposes_goal():
    pool = ps.rule_goal_pool({FACT}, RULES, 3)
    assert ("Member", FACT[1], "local") in pool and ("Member", FACT[1], "branch") in pool
    hops, chain = pool[("Member", FACT[1], "local")]
    assert hops == 1 and chain[0] == FACT and chain[-1][0] == "Rule"

def test_and_premise_and_two_hops():
    rules = ["(: r1 (Implication (And (Member $x a) (Member $x b)) (Member $x c)) (STV 1.0 0.9))",
             "(: r2 (Implication (Member $x c) (Member $x d)) (STV 1.0 0.9))"]
    pool = ps.rule_goal_pool({("Member", "bob", "a"), ("Member", "bob", "b")}, rules, 3)
    assert pool[("Member", "bob", "c")][0] == 1 and pool[("Member", "bob", "d")][0] == 2
    assert ps.rule_goal_pool({("Member", "bob", "a")}, rules, 3) == {}

def test_function_term_consequent_skipped():
    rules = ["(: r (Implication (Member $y skip) (Member (sk_depend__n $y) depend)) (STV 0.9 0.7))"]
    assert ps.rule_goal_pool({("Member", "s", "skip")}, rules, 3) == {}
