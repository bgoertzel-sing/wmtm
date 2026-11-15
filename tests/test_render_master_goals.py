"""t-2026-11-14-wmtm-render-master-goals: render() for the master parser's binary heads, and label -> source maps
for master_ops specs (sources_for / proof_facts / write_admit_file).  All symbols and labels are synthetic."""
import json, os, tempfile, time
import pytest
from wmtm import pc_admit as P, master_loader as ML

N = "ep_note_20990101T000000Z"; NID = "ep-note-20990101T000000Z"; SUF = "__" + N


@pytest.mark.parametrize("goal,text", [
    ("(Coref sk_a sk_b)", "sk_a refers to the same thing as sk_b"),
    ("(ScaleOpposite hi lo)", "hi is the opposite of lo"),
    ("(Agent sk_e sk_x)", "the agent of sk_e is sk_x"),
    ("(Patient sk_e sk_x)", "the patient of sk_e is sk_x"),
    ("(Theme sk_e sk_x)", "the theme of sk_e is sk_x"),
    ("(Bearer sk_e sk_x)", "the bearer of sk_e is sk_x"),
    ("(Possession sk_t sk_o)", "sk_t belongs to sk_o"),
    ("(PartOf sk_p sk_w)", "sk_p is part of sk_w"),
    ("(Because sk_e sk_c)", "sk_e happens because of sk_c"),
    ("(Member sk_a cls)", "sk_a is a cls"),                       # old shapes unchanged
    ("(Inheritance a b)", "a is a b"),
])
def test_render_each_head(goal, text):
    assert P.render(goal) == text


@pytest.mark.parametrize("goal", ["(Coref (f a) b)", "(Coref a)", "(Unknown a b)", "(Coref a b c)", ""])
def test_unrenderable_shapes_stay_none(goal):
    assert P.render(goal) is None


def test_label_fact():
    assert ML._label_fact("(: s1_x1_member%s (Member sk_a%s cls) (STV 1.0 0.99))" % (SUF, SUF)) == \
        ("s1_x1_member" + SUF, "(Member sk_a%s cls)" % SUF)
    assert ML._label_fact("(Member a b)") == (None, None)


OPS = [("pred", "Coref"),
       ("atom", "(: so_sym (BiImplication (ScaleOpposite $a $b) (ScaleOpposite $b $a)) (STV 1.0 0.99))"),
       ("atom", "(: pole_lo_hi (ScaleOpposite lo hi) (STV 1.0 0.99))"),
       ("atom", "(: s1_c1_coref%s (Coref sk_m%s sk_a%s) (STV 1.0 0.99))" % (SUF, SUF, SUF)),
       ("atom", "(: s1_v1_agent%s (Agent sk_e%s sk_m%s) (STV 1.0 0.99))" % (SUF, SUF, SUF))]


def test_spec_maps_note_labels_only():
    mp = ML.spec_maps(OPS, [NID, "ep-note-20990102T000000Z"])
    assert mp["atom_src"] == {"s1_c1_coref" + SUF: NID, "s1_v1_agent" + SUF: NID}   # rules/poles: no note
    assert mp["label_fact"]["s1_v1_agent" + SUF] == "(Agent sk_e%s sk_m%s)" % (SUF, SUF)


PROOF = "(: (by coref_agent (conjunction s1_c1_coref%s s1_v1_agent%s)) (Agent sk_e%s sk_a%s) (STV 0.8 0.9))" % (SUF, SUF, SUF, SUF)
GOAL = "(Agent sk_e%s sk_a%s)" % (SUF, SUF)


def test_sources_and_facts_from_master_labels():
    spec = ML.spec_maps(OPS, [NID])
    assert P.proof_labels(PROOF, spec["atom_src"]) == ["s1_c1_coref" + SUF, "s1_v1_agent" + SUF]
    assert P.sources_for(GOAL, PROOF, spec) == [NID]
    assert P.proof_facts(GOAL, PROOF, spec) == sorted(spec["label_fact"].values())
    assert P.sources_for(GOAL, PROOF, {}) == []                                    # no map -> no source
    assert P.sources_for("(ScaleOpposite hi lo)", "(: (by (bi-forward so_sym) pole_lo_hi) (ScaleOpposite hi lo) (STV 1 0.98))", spec) == []


def test_legacy_labels_unchanged():
    spec = {"atom_src": {"sp0": "s0", "sp1": "s1"}, "label_fact": {"sp0": "(Inheritance a b)"}}
    assert P.proof_labels("(inh_trans sp0 sp1 wm3)", {}) == ["sp0", "sp1", "wm3"]
    assert P.sources_for("(Inheritance a c)", "(inh_trans sp0 sp1)", spec) == ["s0", "s1"]


def test_write_admit_file_lifts_master_meta_maps():
    mp = ML.spec_maps(OPS, [NID])
    spec = {"ts": 1.0, "cycle": 0, "load_order": "master_ops", "master_ops": OPS, "atoms": [],
            "master_meta": {"rules": 1, "atom_src": mp["atom_src"], "label_fact": mp["label_fact"]}}
    rec = {"status": "ok", "canary": {"ok": True}, "neg": {"ok": False, "timeout": False},
           "queries": [{"goal": GOAL, "ok": True, "timeout": False, "stv": [0.8, 0.9], "proof": PROOF, "s": 0.1}]}
    with tempfile.TemporaryDirectory() as d:
        doc = P.write_admit_file(d, rec, spec)
        r = doc["results"][0]
        assert r["sources"] == [NID] and len(r["facts"]) == 2
        # end to end: load_candidates admits it (coref role rule is not a restatement in the shipped line)
        doc["spec_ts"] = doc["ts"] = time.time()
        json.dump(doc, open(os.path.join(d, P.ADMIT_FILE), "w"))
        c, info = P.load_candidates({"shadow_dir": d, "reasoner_max_admit": 10, "gate_max_per_fact": 0}, None,
                                    live_ids=[NID])
        assert info["dropped"]["bad"] == 0 and info["dropped"]["no_live_source"] == 0
        assert [x.content for x in c] == ["the agent of sk_e%s is sk_a%s" % (SUF, SUF)] and c[0].derived_from == [NID]


def test_legacy_spec_not_touched():
    spec = {"atom_src": {"sp0": "s0"}, "master_meta": {"atom_src": {"x": "y"}}}
    assert P._with_master_maps(spec) is spec
