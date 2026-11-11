"""t-2026-11-11 induction goal shape (synthetic data only)."""
from wmtm import pc_shadow as ps


def _rel(n_shared):
    rel = {("Member", "x%d" % i, "cat") for i in range(3)}
    rel |= {("Member", "x%d" % i, "pet") for i in range(n_shared)}
    rel |= {("Member", "y1", "dog"), ("Member", "y2", "fish")}
    return rel


def test_three_shared_instances_propose_goal():
    p = ps.induction_goal_pool(_rel(3), min_shared=3)
    assert ("Inheritance", "cat", "pet") in p and ("Inheritance", "pet", "cat") not in p   # rev2: one direction
    hops, chain = p[("Inheritance", "cat", "pet")]
    assert hops == 1 and len(chain) == 6


def test_one_shared_instance_control_no_goal():
    assert ps.induction_goal_pool(_rel(1), min_shared=3) == {}
    p1 = ps.induction_goal_pool(_rel(1), min_shared=1)   # rev2: pet (1 member, shared) -> cat, one direction
    assert ("Inheritance", "pet", "cat") in p1 and ("Inheritance", "cat", "pet") not in p1


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


def test_one_direction_per_pair_by_coverage():
    rel = {("Member", "x%d" % i, "cat") for i in range(3)} | {("Member", "x%d" % i, "animal") for i in range(6)}
    p = ps.induction_goal_pool(rel, min_shared=3)
    assert ("Inheritance", "cat", "animal") in p and ("Inheritance", "animal", "cat") not in p


# --- rev2 (review 1 finding 4): the build_snapshot flag path, on and off ---
def _ind_store(monkeypatch):
    from wmtm.store import WMTMStore
    atoms = ["(: f%d (Member x%d cat) (STV 1.0 0.99))" % (i, i) for i in range(3)] + \
            ["(: g%d (Member x%d pet) (STV 1.0 0.99))" % (i, i) for i in range(3)]
    st = WMTMStore(); st.admit("item_ind", "note ind", source_type="recalled", initial_sti=1.0)
    monkeypatch.setattr(ps, "_cache_lookup", lambda items, *a, **k: {it.id: list(atoms) for it in items})
    return st


def test_build_snapshot_flag_on_proposes_induction_goal(monkeypatch):
    from wmtm import runtime_config as rc
    cfg = dict(rc.resolve()); cfg.update(shadow_induction=True, shadow_induction_min=3, shadow_max_goals=20)
    spec = ps.build_snapshot(_ind_store(monkeypatch), cycle=1, cfg=cfg)
    ind = [g for g in spec["goals"] if g.startswith("(Inheritance")]
    assert len(ind) == 1 and ind[0] in ("(Inheritance cat pet)", "(Inheritance pet cat)")
    chain = spec["goal_meta"][ind[0]]["chain"]
    assert len([c for c in chain if "Member" in str(c)]) == 6


def test_build_snapshot_flag_off_no_induction_goal(monkeypatch):
    from wmtm import runtime_config as rc
    cfg = dict(rc.resolve()); cfg.update(shadow_induction=False, shadow_max_goals=20)
    spec = ps.build_snapshot(_ind_store(monkeypatch), cycle=1, cfg=cfg)
    assert not [g for g in spec["goals"] if g.startswith("(Inheritance")]


# --- rev2 (review 1 finding 2): fold proofs take premise ids from the goal's chain, not goal-symbol matching ---
def test_fold_proof_sources_and_facts_from_chain():
    from wmtm import pc_admit as pa
    g = "(Inheritance cat pet)"
    chain = ["(Member x%d cat)" % i for i in range(3)] + ["(Member x%d pet)" % i for i in range(3)]
    spec = {"goal_meta": {g: {"chain": chain}},
            "fact_src": [("Member", "x%d" % i, "cat", "c%d" % i) for i in range(3)] +
                        [("Member", "x%d" % i, "pet", "p%d" % i) for i in range(3)] +
                        [("Member", "y", "pet", "other")]}
    proof = "(implication-instance-fold cpu)"
    assert sorted(pa.sources_for(g, proof, spec)) == ["c0", "c1", "c2", "p0", "p1", "p2"]
    assert pa.proof_facts(g, proof, spec) == sorted(chain)


# --- rev3 (review 2 finding 2): engine fold strength vs design §9.1b "strength = weighted average" ---
# Checks the committed engine answers (probe_rev3, PeTTaChainer b6aacc68 / PeTTa 3681b9b) against a reference
# of ImplicationInstanceAcc (pln_formulas truth_values.metta:243): s = sum(m_i * c_ai * c_bi * s_bi) / sum(m_i * c_ai * c_bi).
import os as _os, re as _re
_P3 = _os.path.join(_os.path.dirname(__file__), "..", "reports", "t-2026-11-11-wmtm-induction", "evidence", "probe_rev3")


def _probe(name):
    src = open(_os.path.join(_P3, name + ".metta")).read()
    facts = {}
    for inst, cls, s, c in _re.findall(r"\(Member (\w+) (\w+)\) \(STV ([0-9.]+) ([0-9.]+)\)", src):
        facts[(inst, cls)] = (float(s), float(c))
    ans = open(_os.path.join(_P3, name + ".answer.txt")).read()
    s, c = _re.search(r"\(Inheritance A B\) \(STV ([0-9.e-]+) ([0-9.e-]+)\)", ans).groups()
    return facts, float(s), float(c)


def _weighted_average(facts):
    num = den = 0.0
    for (i, cls), (m, mc) in facts.items():
        if cls != "A" or (i, "B") not in facts:
            continue
        bs, bc = facts[(i, "B")]
        w = m * mc * bc
        num += w * bs; den += w
    return num / den


def test_engine_fold_strength_is_mass_weighted_average():
    facts, s, c = _probe("f_weighted_fold")
    assert len([k for k in facts if k[1] == "A"]) == 3          # 3 instances
    ref = _weighted_average(facts)
    assert abs(s - ref) < 1e-9                                   # 0.5913..., not the plain mean 0.5333
    assert abs(s - (1.0 + 0.2 + 0.4) / 3) > 0.05
    assert 0.0 < c < 0.01                                        # low confidence: 3 instances only


def test_engine_fold_one_instance_control():
    facts, s, c = _probe("g_one_instance")
    assert s == 1.0 and c < _probe("f_weighted_fold")[2]          # one instance: weaker than three, restates it
