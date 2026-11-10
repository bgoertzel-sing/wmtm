"""t-2026-11-10-wmtm-trivial-filter (GAP-5, S part): pc_admit.TRIVIAL_RULE on synthetic atoms.

Each trivial proof shape is refused and has a negative control that is admitted.  Classification reads the proof
term and the cited rule atoms only: the label names below are deliberately neutral or misleading."""
import json, os, time
import pytest
from wmtm import pc_admit as P
from wmtm.pc_shadow import narrow_symbol
from wmtm.candidate import InferenceCandidate
from wmtm.orchestrator import WMTMOrchestrator
from wmtm.store import WMTMStore

S = narrow_symbol(["Narrow", "commit", ["Member", "staged"]])          # named form of (Narrow commit (Member staged))
SMOD = narrow_symbol(["Narrow", "commit", ["Mod", "staged"]])
DEF = "(: r_def (Implication (Member $x %s) (Member $x commit)) (CTV (STV 1.0 0.99) (STV 0.0 0.0)))" % S
DEFMOD = "(: r_defm (Implication (Member $x %s) (Member $x commit)) (CTV (STV 1.0 0.99) (STV 0.0 0.0)))" % SMOD
ECHO = "(: r_echo (Implication (Member sk_c %s) (Member sk_c staged)) (STV 0.9 0.7))" % S
ECHOMOD = "(: r_echom (Implication (Member sk_c %s) (Member sk_c staged)) (STV 0.9 0.7))" % SMOD
OTHER = "(: r_other (Implication (Member sk_c %s) (Member sk_c pushed)) (STV 0.9 0.7))" % S     # not the restriction
PLAIN = "(: nwdef_tree__nw_0 (Implication (Member $x cat) (Member $x mammal)) (STV 0.9 0.9))"  # misleading label
Z = "(prior (STV 0.5 0.0))"


def rules(*atoms):
    return {a[3:].split()[0]: a for a in atoms}


def pf(term, goal):
    return "(: %s %s (STV 0.9 0.7))" % (term, goal)


# ------------------------------------------------------------------ shape 1: head-noun step over an asserted fact
def test_nwdef_head_noun_refused():
    assert P.trivial_reason(pf("(by r_def sp1)", "(Member a commit)"), rules(DEF)) == "nwdef_head_noun"


def test_nwdef_head_noun_over_revised_facts_refused():
    p = pf("(merge/revision (by r_def sp1) (by r_def sp2))", "(Member a commit)")
    assert P.trivial_reason(p, rules(DEF)) == "nwdef_head_noun"


def test_control_ordinary_rule_with_nwdef_like_label_admitted():
    assert P.trivial_reason(pf("(by nwdef_tree__nw_0 sp1)", "(Member a mammal)"), rules(PLAIN)) is None


# ------------------------------------------------------------------ shape 2: Narrow-restriction echo
def test_narrow_echo_refused_r1_shape():
    p = pf("(by r_echo (factored-revision sp33 (prior (STV 1.0 0.99)) (((inverted r_def with cpu %s) sp25))))" % Z,
           "(Member sk_c staged)")
    assert P.trivial_reason(p, rules(ECHO, DEF)) == "narrow_echo"


def test_narrow_echo_mod_restriction_refused():
    assert P.trivial_reason(pf("(by r_echom sp1)", "(Member sk_c staged)"), rules(ECHOMOD, DEFMOD)) == "narrow_echo"


def test_narrow_echo_weighted_inverted_nwdef_still_refused():
    p = pf("(by r_echo (factored-revision sp33 (prior (STV 1.0 0.99)) "
           "(((inverted r_def with cpu (prior (STV 0.9 0.0012))) sp25))))", "(Member sk_c staged)")
    assert P.trivial_reason(p, rules(ECHO, DEF)) == "narrow_echo"


def test_control_rule_concluding_other_class_admitted():
    assert P.trivial_reason(pf("(by r_other sp1)", "(Member sk_c pushed)"), rules(OTHER, DEF)) is None


def test_control_echo_rule_without_defining_rule_admitted():
    assert P.trivial_reason(pf("(by r_echo sp1)", "(Member sk_c staged)"), rules(ECHO)) is None


# ------------------------------------------------------------------ two-step / cross-rule / unknown: admitted
def test_two_step_chain_admitted():
    p = pf("(by r_other (by r_def sp1))", "(Member sk_c pushed)")
    assert P.trivial_reason(p, rules(OTHER, DEF)) is None


def test_two_trivial_steps_chained_admitted():
    p = pf("(by r_def (by r_echo sp1))", "(Member sk_c commit)")
    assert P.trivial_reason(p, rules(ECHO, DEF)) is None


def test_cross_rule_revision_admitted():
    p = pf("(merge/revision (by r_echo sp1) (by nwdef_tree__nw_0 sp2))", "(Member sk_c staged)")
    assert P.trivial_reason(p, rules(ECHO, DEF, PLAIN)) is None


def test_weighted_non_inverted_branch_admitted():
    p = pf("(by r_echo (factored-revision sp33 (prior (STV 1.0 0.99)) (((reported with cpu (prior (STV 0.9 0.5)))"
           " sp25))))", "(Member sk_c staged)")
    assert P.trivial_reason(p, rules(ECHO, DEF)) is None


def test_missing_rule_atoms_fail_open():
    assert P.trivial_reason(pf("(by r_def sp1)", "(Member a commit)"), {}) is None
    assert P.trivial_reason(pf("(by r_def sp1)", "(Member a commit)"), None) is None


def test_fact_only_proof_not_flagged():
    assert P.trivial_reason(pf("sp1", "(Member a commit)"), rules(DEF)) is None


def test_proof_rules_collects_cited_rule_and_its_premise_definition():
    atoms = ["(: sp1 (Member sk_c %s) (STV 1.0 0.99))" % S, ECHO, DEF, PLAIN]
    got = P.proof_rules(pf("(by r_echo sp1)", "(Member sk_c staged)"), atoms)
    assert set(got) == {"r_echo", "r_def"}


# ------------------------------------------------------------------ admission path: refused, logged, counted; flag
def _admit_doc(tmp_path, results):
    sd = tmp_path / "sh"; sd.mkdir()
    doc = {"ts": time.time(), "spec_ts": time.time(), "status": "ok", "canary_ok": True, "results": results}
    (sd / P.ADMIT_FILE).write_text(json.dumps(doc))
    return {"shadow_dir": str(sd), "reasoner_max_admit": 10}


def _res(goal, proof, rl):
    return {"goal": goal, "stv": [0.9, 0.7], "proof": proof, "sources": ["n1"], "facts": [], "rules": rl}


def test_load_candidates_refuses_logs_and_counts(tmp_path):
    triv = _res("(Member sk_c staged)", pf("(by r_echo sp1)", "(Member sk_c staged)"), rules(ECHO, DEF))
    real = _res("(Member sk_c pushed)", pf("(by r_other sp1)", "(Member sk_c pushed)"), rules(OTHER, DEF))
    cfg = _admit_doc(tmp_path, [triv, real])
    cands, info = P.load_candidates(cfg, None, live_ids=["n1"])
    assert [c.provenance["goal"] for c in cands] == ["(Member sk_c pushed)"]
    assert info["dropped"]["trivial"] == 1 and info["trivial_refused_n"] == 1 and info["trivial_filter"] is True
    assert info["trivial_refused"] == [{"rule": P.TRIVIAL_RULE, "reason": "narrow_echo",
                                        "goal": "(Member sk_c staged)", "steps": ["r_echo"]}]
    rec = P.log_admission(cfg, "cycle", info)
    assert rec["trivial_refused"][0]["reason"] == "narrow_echo"
    line = open(os.path.join(cfg["shadow_dir"], P.ADMIT_LOG)).read()
    assert "narrow_echo" in line


def test_flag_off_admits_trivial(tmp_path):
    triv = _res("(Member sk_c staged)", pf("(by r_echo sp1)", "(Member sk_c staged)"), rules(ECHO, DEF))
    cfg = dict(_admit_doc(tmp_path, [triv]), admit_trivial_filter=False)
    cands, info = P.load_candidates(cfg, None, live_ids=["n1"])
    assert len(cands) == 1 and "trivial" not in info["dropped"] and info["trivial_refused_n"] == 0
    assert info["trivial_filter"] is False


def test_flag_default_on():
    from wmtm import runtime_config as rc
    assert rc.SPEC["admit_trivial_filter"][2] is True and P.trivial_filter_on({}) is True


def _cand(goal, proof, rl):
    return InferenceCandidate(content=P.render(goal), confidence=0.7, derived_from=["n1"],
                              inference_type="pc_deduction", initial_sti=1.0,
                              provenance={"reasoner": "pettachainer", "goal": goal, "proof": proof, "rules": rl})


def test_orchestrator_guard_refuses_and_counts():
    o = WMTMOrchestrator(WMTMStore(capacity=50))
    o.store.admit("n1", "note", initial_sti=5.0)
    got = o._admit_derived([_cand("(Member sk_c staged)", pf("(by r_echo sp1)", "(Member sk_c staged)"), rules(ECHO, DEF)),
                            _cand("(Member sk_c pushed)", pf("(by r_other sp1)", "(Member sk_c pushed)"), rules(OTHER, DEF))])
    assert [i.provenance["goal"] for i in got] == ["(Member sk_c pushed)"]
    assert o.trivial_refused_n == 1 and o.trivial_refused[-1]["reason"] == "narrow_echo"


def test_admit_on_snapshot_honours_flag(tmp_path):
    triv = _res("(Member sk_c staged)", pf("(by r_echo sp1)", "(Member sk_c staged)"), rules(ECHO, DEF))
    for on, want in ((True, 0), (False, 1)):
        d = tmp_path / str(on); d.mkdir()
        cfg = dict(_admit_doc(d, [triv]), admit_trivial_filter=on)
        o = WMTMOrchestrator(WMTMStore(capacity=50), use_goalchainer=False)
        o.store.admit("n1", "note", initial_sti=5.0)
        snap = o.snapshot_state()
        info = P.admit_on_snapshot(snap, cfg)
        assert info["admitted"] == want, (on, info)
