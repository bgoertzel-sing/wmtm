"""t-2026-11-14-wmtm-trivial-filter-coref: TRIVIAL_RULE extended by rule id to the master rules' symmetry and plain
coreference restatements (andy's line, fixed before re-scoring).  Proof shapes copy the engine's master-path output
((by (bi-forward R) L), (by R (conjunction L1 L2)), note-suffixed labels); all symbols are synthetic."""
import json, time
import pytest
from wmtm import pc_admit as P

L1, L2, L3 = "s01_x1_a__ep_note_20990101T000000Z", "s01_x2_b__ep_note_20990101T000000Z", "so_pole_hi_lo"
G = "(Coref sk_a__ep_note_20990101T000000Z sk_b__ep_note_20990101T000000Z)"


def pf(term, goal=G):
    return "(: %s %s (STV 0.99 0.9))" % (term, goal)


NARROW = {"coref_sym": "symmetry_restatement", "so_sym": "symmetry_restatement",
          "same_coref": "coref_restatement", "coref_bearer": "coref_restatement"}
ROLE = ("coref_agent", "coref_patient", "coref_theme", "coref_member", "coref_possession")


def test_line_is_the_one_fixed_in_the_order():
    assert P.RESTATEMENT_RULES == NARROW
    assert tuple(P.COREF_ROLE_RULES) == ROLE
    assert not set(P.RESTATEMENT_RULES) & set(P.COREF_ROLE_RULES)


@pytest.mark.parametrize("term,rid", [
    ("(by (bi-forward coref_sym) %s)" % L1, "coref_sym"),
    ("(by (bi-forward so_sym) %s)" % L3, "so_sym"),
    ("(by same_coref %s)" % L1, "same_coref"),
    ("(by coref_bearer (conjunction %s %s))" % (L1, L2), "coref_bearer"),
    ("(by coref_sym %s)" % L1, "coref_sym"),              # plain (by R ..) form too
    ("(by so_sym sp1)", "so_sym"),                       # legacy sp<n> label as premise
])
def test_each_listed_restatement_is_trivial(term, rid):
    for rl in (None, {}):
        assert P.trivial_reason(pf(term), rl) == NARROW[rid]


@pytest.mark.parametrize("rid", ROLE)
def test_each_role_rule_conclusion_is_not_trivial(rid):
    for term in ("(by %s (conjunction %s %s))" % (rid, L1, L2), "(by %s %s)" % (rid, L1),
                 "(by (bi-forward %s) %s)" % (rid, L1)):
        assert P.trivial_reason(pf(term), None) is None
        assert P.trivial_reason(pf(term), {}) is None


@pytest.mark.parametrize("rid", ROLE)
def test_restatement_of_a_role_conclusion_is_not_trivial(rid):
    t = "(by (bi-forward coref_sym) (by %s (conjunction %s %s)))" % (rid, L1, L2)
    assert P.trivial_reason(pf(t), None) is None


def test_chain_and_revision_of_restatements_is_trivial():
    assert P.trivial_reason(pf("(by (bi-forward coref_sym) (by same_coref %s))" % L1), None) == "coref_restatement"
    assert P.trivial_reason(pf("(merge/revision (by (bi-forward coref_sym) %s) (by coref_sym %s))" % (L1, L2)), None) \
        == "symmetry_restatement"


def test_exact_rule_id_only():
    for rid in ("coref_sym2", "xcoref_sym", "Coref_sym", "so_sym_x", "same_coref_"):
        assert P.trivial_reason(pf("(by %s %s)" % (rid, L1)), None) is None
        assert P.trivial_reason(pf("(by (bi-forward %s) %s)" % (rid, L1)), None) is None


def test_non_label_premises_fail_open():
    assert P.trivial_reason(pf("(by same_coref (weird %s))" % L1), None) is None
    assert P.trivial_reason(pf("(by same_coref $x)"), None) is None
    assert P.trivial_reason(pf("(by same_coref 0.5)"), None) is None
    assert P.trivial_reason(pf("(by same_coref coref_sym)"), None) is None      # a rule id is not a fact label


def test_mixed_with_another_rule_is_not_trivial():
    assert P.trivial_reason(pf("(by (bi-forward coref_sym) (by month_class %s))" % L1), None) is None
    assert P.trivial_reason(pf("(by partof_trans (conjunction (by same_coref %s) %s))" % (L1, L2)), None) is None


def test_wide_split_hook_counts_role_rules():
    wide = dict(NARROW, **{r: "coref_restatement" for r in ROLE})
    for rid in ROLE:
        t = pf("(by %s (conjunction %s %s))" % (rid, L1, L2))
        assert P.trivial_reason(t, None) is None
        assert P.trivial_reason(t, None, restatement_rules=wide) == "coref_restatement"
    # the hook does not change the default
    assert P.trivial_reason(pf("(by coref_agent %s)" % L1), None) is None


def test_old_shapes_unchanged_by_new_forms():
    # forms read for restatement rules only must not open the old nwdef/narrow paths
    from wmtm.pc_shadow import narrow_symbol
    S = narrow_symbol(["Narrow", "commit", ["Member", "staged"]])
    DEF = "(: r_def (Implication (Member $x %s) (Member $x commit)) (CTV (STV 1.0 0.99) (STV 0.0 0.0)))" % S
    rl = {"r_def": DEF}
    assert P.trivial_reason(pf("(by r_def sp1)", "(Member a commit)"), rl) == "nwdef_head_noun"
    assert P.trivial_reason(pf("(by r_def %s)" % L1, "(Member a commit)"), rl) is None
    assert P.trivial_reason(pf("(by r_def (conjunction sp1 sp2))", "(Member a commit)"), rl) is None
    assert P.trivial_reason(pf("(by (bi-forward r_def) sp1)", "(Member a commit)"), rl) is None
    assert P.trivial_reason(pf("(by (bi-forward coref_sym) (by r_def sp1))", "(Member a commit)"), rl) is None


def test_load_candidates_refuses_restatement_admits_role(tmp_path):
    sd = tmp_path / "sh"; sd.mkdir()
    res = lambda term: {"goal": "(Member sk_a person)", "stv": [0.9, 0.7], "proof": pf(term, "(Member sk_a person)"),
                        "sources": ["n1"], "facts": [], "rules": {}}
    doc = {"ts": time.time(), "spec_ts": time.time(), "status": "ok", "canary_ok": True,
           "results": [res("(by (bi-forward coref_sym) %s)" % L1), res("(by coref_agent (conjunction %s %s))" % (L1, L2))]}
    (sd / P.ADMIT_FILE).write_text(json.dumps(doc))
    cands, info = P.load_candidates({"shadow_dir": str(sd), "reasoner_max_admit": 10}, None, live_ids=["n1"])
    assert len(cands) == 1 and "coref_agent" in cands[0].provenance["proof"]
    assert info["trivial_refused_n"] == 1
    assert info["trivial_refused"][0]["reason"] == "symmetry_restatement"
    assert info["trivial_refused"][0]["steps"] == ["coref_sym"]
