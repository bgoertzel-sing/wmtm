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


# ------------------------------------------------------------------ followup-v2 finding 2: nwdef by EXACT shape
R1 = "(: r1 (Implication (Member $x pilot) (Member $x person)) (CTV (STV 0.95 0.9) (STV 0.0 0.0)))"  # p4 parser rule
NWDEF_REAL = "(: nwdef_%s (Implication (Member $x %s) (Member $x commit)) (CTV (STV 1.0 0.99) (STV 0.0 0.0)))" % (S, S)


def test_parser_class_rule_r1_admitted():
    # a real parser class rule (tests/test_p4_semparse_rules.py r1) is a CTV Member implication but NOT nwdef
    assert P.trivial_reason(pf("(by r1 sp1)", "(Member sk_a person)"), rules(R1)) is None
    assert P.trivial_reason(pf("(merge/revision (by r1 sp1) (by r1 sp2))", "(Member sk_a person)"), rules(R1)) is None


def test_parser_rule_r1_admitted_through_load_candidates(tmp_path):
    r = _res("(Member sk_a person)", pf("(by r1 sp1)", "(Member sk_a person)"), rules(R1))
    cands, info = P.load_candidates(_admit_doc(tmp_path, [r]), None, live_ids=["n1"])
    assert len(cands) == 1 and info["trivial_refused_n"] == 0


def test_narrow_defining_rules_output_is_nwdef_shape():
    from wmtm.pc_shadow import narrow_defining_rules
    (atom,) = narrow_defining_rules({S: "commit"})
    assert P.trivial_reason(pf("(by nwdef_%s sp1)" % S, "(Member a commit)"), rules(atom)) == "nwdef_head_noun"
    assert atom == NWDEF_REAL


@pytest.mark.parametrize("atom", [
    # each differs from the exact nwdef shape in one place -> not a defining rule -> admitted
    "(: d (Implication (Member $x %s) (Member $x commit)) (CTV (STV 0.95 0.9) (STV 0.0 0.0)))" % S,   # tv
    "(: d (Implication (Member $x %s) (Member $x commit)) (STV 1.0 0.99))" % S,                       # not CTV
    "(: d (Implication (Member $x %s) (Member $x pushed)) (CTV (STV 1.0 0.99) (STV 0.0 0.0)))" % S,   # base != B
    "(: d (Implication (Member sk_c %s) (Member sk_c commit)) (CTV (STV 1.0 0.99) (STV 0.0 0.0)))" % S,  # ground
    "(: d (Implication (Member $x commit__nw_xyz) (Member $x commit)) (CTV (STV 1.0 0.99) (STV 0.0 0.0)))",  # bad hash
])
def test_near_nwdef_shapes_admitted(atom):
    assert P.trivial_reason(pf("(by d sp1)", "(Member a commit)"), rules(atom)) is None


def test_echo_needs_exact_nwdef_for_base():
    # the echo rule's base comes only from an exact defining rule; a parser rule over S does not supply it
    fake = "(: r_fake (Implication (Member $x %s) (Member $x commit)) (CTV (STV 0.95 0.9) (STV 0.0 0.0)))" % S
    assert P.trivial_reason(pf("(by r_echo sp1)", "(Member sk_c staged)"), rules(ECHO, fake)) is None


# ------------------------------------------------------------------ followup-v2 finding 4: guard refusals are logged
def test_guard_refusals_reach_admit_log(tmp_path):
    sd = tmp_path / "sh"; sd.mkdir()
    cfg = {"shadow_dir": str(sd)}
    o = WMTMOrchestrator(WMTMStore(capacity=50), use_goalchainer=False)
    o.store.admit("n1", "note", initial_sti=5.0)
    info = {"run": "r1", "dropped": {"asserted": 0}}
    items, info = o.admit_pc_candidates(
        [_cand("(Member sk_c staged)", pf("(by r_echo sp1)", "(Member sk_c staged)"), rules(ECHO, DEF)),
         _cand("(Member sk_c pushed)", pf("(by r_other sp1)", "(Member sk_c pushed)"), rules(OTHER, DEF))], info)
    assert info["admitted"] == 1 and info["trivial_refused_guard_n"] == 1 and info["dropped"]["trivial"] == 1
    rec = P.log_admission(cfg, "cycle", info)
    assert rec["trivial_refused"][0]["by"] == "guard" and rec["trivial_refused"][0]["reason"] == "narrow_echo"
    line = json.loads((sd / P.ADMIT_LOG).read_text().splitlines()[-1])
    assert line["trivial_refused"][0]["rule"] == P.TRIVIAL_RULE


def test_no_guard_refusal_leaves_info_shape(tmp_path):
    o = WMTMOrchestrator(WMTMStore(capacity=50), use_goalchainer=False)
    o.store.admit("n1", "note", initial_sti=5.0)
    _, info = o.admit_pc_candidates(
        [_cand("(Member sk_c pushed)", pf("(by r_other sp1)", "(Member sk_c pushed)"), rules(OTHER, DEF))], {"run": "r2"})
    assert "trivial_refused" not in info and "trivial_refused_guard_n" not in info


# ------------------------------------------------------------------ followup-v2 finding 5: trivial canaries as tests
# Known answers from the frozen B rerun (evidence/runs/r{1,2,3}/admit.json) and the s49 non-trivial control.
_EV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reports", "t-2026-11-10-wmtm-trivial-filter", "evidence")
_KNOWN_REFUSED = {"r1": 12, "r2": 14, "r3": 10}


@pytest.mark.parametrize("run", sorted(_KNOWN_REFUSED))
def test_canary_frozen_b_run_refuses_known_trivial(run, tmp_path):
    p = os.path.join(_EV, "runs", run, "admit.json")
    if not os.path.exists(p):
        pytest.skip("evidence not on this branch")
    d = json.load(open(p))
    why = [P.trivial_reason(x["proof"], x.get("rules")) for x in d["results"]]
    assert sum(1 for w in why if w) == _KNOWN_REFUSED[run]
    assert {w for w in why if w} == {"narrow_echo"}
    # same answer through the real admission path
    sd = tmp_path / "sh"; sd.mkdir(); (sd / P.ADMIT_FILE).write_text(json.dumps(d))
    _, info = P.load_candidates({"shadow_dir": str(sd), "reasoner_max_admit": 100, "gate_max_per_fact": 0},
                                None, now=float(d.get("spec_ts") or d["ts"]) + 1,
                                live_ids=sorted({s for x in d["results"] for s in x.get("sources") or []}))
    assert info["trivial_refused_n"] == _KNOWN_REFUSED[run]


def test_canary_s49_control_admitted_with_full_step_coverage():
    p = os.path.join(_EV, "controls_s49.json")
    if not os.path.exists(p):
        pytest.skip("evidence not on this branch")
    C = json.load(open(p))
    assert C, "no controls"
    for k, rows in C.items():
        assert len(rows) == 49, k
        for x in rows:
            assert x["rules"], (k, x["goal"])                       # control is not fail-open
            assert P.step_coverage(x["proof"], x["rules"])["missing"] == [], (k, x["goal"])
            assert P.trivial_reason(x["proof"], x["rules"]) is None, (k, x["goal"])


def test_step_coverage_counts_missing():
    c = P.step_coverage(pf("(by r_echo (by r_gone sp1))", "(Member sk_c staged)"), rules(ECHO))
    assert c == {"steps": 2, "known": 1, "missing": ["r_gone"]}
