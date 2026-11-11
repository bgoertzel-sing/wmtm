"""t-2026-11-11 induction goal shape (synthetic data only)."""
from wmtm import pc_shadow as ps


def _rel(n_shared):
    rel = {("Member", "x%d" % i, "cat") for i in range(3)}
    rel |= {("Member", "x%d" % i, "pet") for i in range(n_shared)}
    rel |= {("Member", "y1", "dog"), ("Member", "y2", "fish")}
    return rel


def test_three_shared_instances_propose_goal():
    p = ps.induction_goal_pool(_rel(3), min_shared=3)
    assert ("Inheritance", "cat", "pet") in p and ("Inheritance", "pet", "cat") in p
    hops, chain = p[("Inheritance", "cat", "pet")]
    assert hops == 1 and len(chain) == 6


def test_one_shared_instance_control_no_goal():
    assert ps.induction_goal_pool(_rel(1), min_shared=3) == {}
    assert ("Inheritance", "cat", "pet") in ps.induction_goal_pool(_rel(1), min_shared=1)


def test_unrelated_classes_control_no_goal():
    p = ps.induction_goal_pool(_rel(3), min_shared=1)
    assert ("Inheritance", "dog", "fish") not in p and ("Inheritance", "fish", "dog") not in p


def test_asserted_and_skolem_skipped():
    rel = _rel(3) | {("Inheritance", "cat", "pet")}
    assert ("Inheritance", "cat", "pet") not in ps.induction_goal_pool(rel)
    rel = {("Member", "x%d" % i, c) for i in range(3) for c in ("sk_a__i1", "pet")}
    assert ps.induction_goal_pool(rel) == {}


def test_ranked_alongside_chain_goals():
    rel = _rel(3) | {("Inheritance", "pet", "animal")}
    pool = ps.goal_pool(rel)
    ps.induction_goal_pool(rel, pool=pool)
    r = dict(ps.rank_goals(pool, rel))
    assert "(Inheritance cat pet)" in r and "(Member x0 animal)" in r


def test_nwdef_alias_pair_skipped():
    rel = {("Member", "x%d" % i, c) for i in range(3) for c in ("result", "result__nw_b5881f6f23")}
    assert ps.induction_goal_pool(rel, min_shared=1) == {}
