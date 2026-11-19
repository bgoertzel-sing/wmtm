"""Synthetic-only tests for wmtm/clerk/adapter.py (no note content)."""
from wmtm.clerk import adapter as A


def heads(atoms):
    return [a.split()[2].lstrip('(') for a in atoms]


def test_individual_one_arg_is_member():
    at, um = A.translate(["(astronaut robert-1)"], "t")
    assert um == [] and "(Member robert_1 astronaut)" in at[0]


def test_class_one_arg_is_inheritance():
    at, _ = A.translate(["(caffeinated coffee-drinker)"], "t")
    assert "(Inheritance coffee_drinker caffeinated)" in at[0]


def test_exists_skolem_and_split():
    at, _ = A.translate(["(exists ($1) (and (run $1) (agent $1 bob-2)))"], "t")
    assert heads(at) == ["Member", "Evaluation"]
    assert "(Member sk_run_1 run)" in at[0]


def test_forall_implies_keeps_var():
    at, _ = A.translate(["(forall ($1) (implies (dog $1) (animal $1)))"], "t")
    assert at[0].startswith("(: b_l0_1 (Implication (Member $x1 dog) (Member $x1 animal))")
    assert at[0].endswith(A.RULE_TV + ")")


def test_nested_arg_asserts_nothing():
    at, _ = A.translate(["(result run-1 (ok canary))"], "t")
    assert at == ["(: b_l0_1 (Evaluation result (List run_1 (ok canary))) (STV 1.0 0.99))"]


def test_unmapped_logged_not_loaded():
    at, um = A.translate(["(because (a x-1) (b y-1))", "(will (go x-1))"], "t")
    assert at == [] and [r for r, _ in um] == ["because", "one-arg-compound:will"]


def test_called_equal():
    at, _ = A.translate(['(called task-1 "T")', "(equal a-1 b-1)"], "t")
    assert heads(at) == ["Name", "Similarity"]
