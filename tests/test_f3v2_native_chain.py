"""F3 v2 (t-2026-11-08-wmtm-f3-ab-v2): no wmtm-side rules; engine-native Member/Inheritance chaining.
Repro of andy's kbA/kbD/kbH/kbI (upstream/pettachainer/r9_specializes_bdae8d7e.metta)."""
import os, re
import pytest
from wmtm import pc_admit, pc_shadow, runtime_config as rc

_CFG = rc.resolve()
HAVE_PC = os.path.isdir(os.path.join(_CFG["petta_dir"], "python")) and os.path.isdir(os.path.join(_CFG["pettachainer_dir"], "pettachainer"))
_SRC = os.path.join(os.path.dirname(pc_admit.__file__), "workers")


def test_no_wmtm_rules_loaded():
    s = open(os.path.join(_SRC, "pc_shadow.py")).read()
    assert re.search(r"^RULES = \[\]$", s, re.M)
    for f in ("pc_shadow.py", "semparse_feed.py"):
        code = "\n".join(l for l in open(os.path.join(_SRC, f)).read().splitlines() if not l.lstrip().startswith("#"))
        assert "(: mem_inh" not in code and "(: inh_trans" not in code and "(: imp_trans" not in code, f


def test_implies_not_transitive():
    assert pc_shadow.TRANSITIVE == ("Inheritance",)


@pytest.mark.parametrize("proof,want", [
    ("(: sp504 (Inheritance cat animal) (STV 0.9 0.9))", False),
    ("(: (merge/revision sp1 sp2) (Implies rain slippery) (STV 1 0.99))", False),
    ("(: (by cg cf) (Member grace person) (STV 1.0 0.98))", True),
    ("(: (conditioned sp2 (merge/revision (by sp0 (given true)) (by sp1 (given true))) (merge/revision (by sp0 (given false)) (by sp1 (given false)))) (Member tom mammal) (STV 0.88 0.83))", True),
    ("(: (merge/revision (conditional-implication (by sp3 (merge/revision (by sp0 (ctx proof 1)) (by sp1 (ctx proof 1))))) (implication-instance-fold cpu)) (Inheritance cat animal) (STV 0.852 0.11))", True),
    ("(imp_trans sp2 sp3)", True),                                          # legacy shadow docs still admitted
    ("(: (by i_ep_x__a1_implication_c1 sp3) (Member a b) (STV 1 1))", True),
])
def test_is_derivation(proof, want):
    assert pc_admit.is_derivation(proof) is want


def test_negative_control_old_regex_drops_native_derivation():
    """The pre-F3v2 check (rule names only) would drop a native engine derivation as 'asserted'."""
    native = "(: (by cg cf) (Member grace person) (STV 1.0 0.98))"
    assert not (pc_admit._RULE.search(native) or pc_admit._PARSER_RULE.search(native))
    assert pc_admit.is_derivation(native)


def _engine():
    import sys
    sys.path.insert(0, os.path.join(_CFG["petta_dir"], "python")); sys.path.insert(0, _CFG["pettachainer_dir"])
    os.environ["PETTA_PATH"] = _CFG["petta_dir"]
    from pettachainer.pettachainer import PeTTaChainer
    return PeTTaChainer


def _conf(PC, atoms, goal):
    h = PC()
    for s in atoms:
        h.add_atom(s)
    r = h.query("(: $prf %s $tv)" % goal, steps=30, timeout_sec=0)
    assert r, goal
    return float(re.search(r"\(STV ([\d.e-]+) ([\d.e-]+)\)\)\s*$", str(r[0])).group(2))


A = ["(: a1 (Inheritance harbour_pilot pilot) (STV 1.0 0.99))", "(: a2 (Inheritance pilot licensed) (STV 0.9 0.7))"]
IT = ["(: inh_trans (Implication (And (Inheritance $a $b) (Inheritance $b $c)) (Inheritance $a $c)) (STV 1.0 0.99))"]
G = ["(: cf (Member grace pilot) (STV 1.0 0.99))", "(: cg (Inheritance pilot person) (STV 1.0 0.99))"]


@pytest.mark.skipif(not HAVE_PC, reason="vendored PeTTa / PeTTaChainer not present")
def test_repro_native_beats_wmtm_rule_and_canary_without_rules():
    PC = _engine()
    native = _conf(PC, A, "(Inheritance harbour_pilot licensed)")         # kbH
    with_rule = _conf(PC, A + IT, "(Inheritance harbour_pilot licensed)")  # kbI (negative control: the old rule hurts)
    assert native >= 0.5 and with_rule < 0.2 and native > with_rule
    assert _conf(PC, G, "(Member grace person)") > 0.9                     # canary, no mem_inh
    h = PC()
    for s in G:
        h.add_atom(s)
    assert not h.query("(: $prf (Member grace robot) $tv)", steps=30, timeout_sec=0)


# F3 v3 (review 1 finding 4 / order C): a factored revision of asserted facts is not a new conclusion.
@pytest.mark.parametrize("proof,want", [
    ("(: (factored-revision sp1 sp2) (Inheritance a b) (STV 0.9 0.8))", False),
    ("(: (factored-revision sp1 (prior (STV 0.99 0.99)) sp2) (Member a b) (STV 0.9 0.8))", False),
    ("(: (factored-revision (merge/revision sp1 sp2) sp3) (Member a b) (STV 0.9 0.8))", False),
    # negative controls: a factored revision that wraps a real derivation is still admitted
    ("(: (factored-revision sp1 (by r1 sp2)) (Member a b) (STV 0.9 0.8))", True),
    ("(: (factored-revision (inh_trans sp1 sp2) sp3) (Inheritance a c) (STV 0.9 0.8))", True),
])
def test_factored_revision_of_asserted_not_admitted(proof, want):
    assert pc_admit.is_derivation(proof) is want


KB_F = ["(: f1 (Member b1 cls_a) (STV 1.0 0.99))", "(: r1 (Implication (Member b1 cls_a) (Member b1 acl_d)) (STV 0.9 0.7))"]
KB_R = ["(: mem_inh (Implication (And (Member $x $a) (Inheritance $a $b)) (Member $x $b)) (STV 1.0 0.99))"] + IT


def _stv(PC, atoms, goal):
    h = PC()
    for s in atoms:
        h.add_atom(s)
    r = h.query("(: $prf %s $tv)" % goal, steps=30, timeout_sec=0)
    assert r, goal
    m = re.search(r"\(STV ([\d.e-]+) ([\d.e-]+)\)\)\s*$", str(r[0]))
    return str(r[0]), float(m.group(1)), float(m.group(2))


@pytest.mark.skipif(not HAVE_PC, reason="vendored PeTTa / PeTTaChainer not present")
def test_repro_kbA_kbD_values():
    """andy's r9 repro: kbA (no wmtm rules) proves (by r1 f1) at (0.9, 0.7);
    kbD (mem_inh + inh_trans put back) specializes down to (0.977, 0.018)."""
    PC = _engine()
    pa, sa, ca = _stv(PC, KB_F, "(Member b1 acl_d)")
    assert "(by r1 f1)" in pa and "mem_inh" not in pa
    assert sa == pytest.approx(0.9, abs=1e-6) and ca == pytest.approx(0.7, abs=1e-6)
    pd, sd, cd = _stv(PC, KB_R + KB_F, "(Member b1 acl_d)")
    assert "specializes" in pd and "mem_inh" in pd
    assert sd == pytest.approx(0.97660, abs=1e-4) and cd == pytest.approx(0.01793, abs=1e-4)


@pytest.mark.skipif(not HAVE_PC, reason="vendored PeTTa / PeTTaChainer not present")
def test_repro_kbH_kbI_values():
    PC = _engine()
    _, sh, ch = _stv(PC, A, "(Inheritance harbour_pilot licensed)")
    assert sh == pytest.approx(0.9, abs=1e-6) and ch == pytest.approx(0.7, abs=1e-2)


# F3 v3 review 1 finding 1: the engine-shaped proof term B returns for an already-asserted fact (ITEM_B, all 5 runs).
# is_derivation currently returns True on it ((by nwdef_.. sp) restatements and 'reported with cpu' count as steps);
# whether that should count is an open design question (REPORT follow-up).  The real safeguard is goal selection:
# an asserted triple is never a goal, so this answer is never asked for and never admitted.
ENGINE_REVISION = ("(: (factored-revision (merge/revision (merge/revision (by nwdef_branch__nw_af7c55181b sp121) "
                   "(by nwdef_branch__nw_a33c0de6a2 sp120)) (by nwdef_branch__nw_50b94ee13a sp119)) "
                   "(prior (STV 1.0 0.9930341767667782)) (((reported with cpu (prior (STV 0.5 0.0))) sp118))) "
                   "(Member hive_t_2026_10_28_goalchainer_v2_status branch) (STV 1.0 0.99))")


def test_engine_shaped_revision_documented_as_admitted():
    assert pc_admit.is_derivation(ENGINE_REVISION) is True   # documents current behaviour; see design follow-up


def test_asserted_fact_is_never_a_goal():
    rel = {("Member", "t1", "branch"), ("Inheritance", "branch", "ref"), ("Member", "t1", "ref"),
           ("Member", "t2", "branch")}
    goals = pc_shadow.build_goals(rel)
    assert "(Member t1 ref)" not in goals and "(Member t2 ref)" in goals
    pool = pc_shadow.goal_pool(rel)
    assert ("Member", "t1", "ref") not in pool and ("Member", "t2", "ref") in pool
