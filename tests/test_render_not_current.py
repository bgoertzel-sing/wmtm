"""t-2026-11-17-wmtm-render-not-current: render() for the extra rules' negated 1-ary conclusions
(Not (Current x)) and (Not (Valid x)).  All symbols are synthetic."""
import json, os, tempfile, time
import pytest
from wmtm import pc_admit as P


@pytest.mark.parametrize("goal,text", [
    ("(Not (Current sk_plan_a))", "sk_plan_a is no longer current"),
    ("(Not (Valid sk_claim_b))", "sk_claim_b no longer holds"),
    ("(Not (Current old_rota__ep_note_20990101T000000Z))", "old_rota__ep_note_20990101T000000Z is no longer current"),
])
def test_not_current_valid_render(goal, text):
    assert P.render(goal) == text


@pytest.mark.parametrize("goal", ["(Not (Current sk_x))", "(Not (Valid sk_x))"])
def test_negation_kept_in_wording(goal):
    t = P.render(goal)
    assert t and "no longer" in t and t.startswith("sk_x")


@pytest.mark.parametrize("goal", [
    "(Current sk_x)", "(Valid sk_x)",                         # un-negated 1-ary: no shape
    "(Not (Member sk_x cls))", "(Not (Patient sk_e sk_x))",   # other Not shapes unchanged (None)
    "(Not (Coref sk_a sk_b))", "(Not (Unknown sk_x))", "(Not sk_x)",
    "(Not (Current (f sk_x)))", "(Not (Current sk_x sk_y))", "(Not (Current))",
    "(Not (Current sk_x)) ", "(Not  (Current sk_x))", "(Not (Not (Current sk_x)))",
    "(Not (current sk_x))", "(Not (Valid $y))x", "",
])
def test_other_not_shapes_stay_none(goal):
    assert P.render(goal) is None


def test_existing_shapes_unchanged():
    assert P.render("(Member sk_a cls)") == "sk_a is a cls"
    assert P.render("(Theme sk_e sk_x)") == "the theme of sk_e is sk_x"
    assert P.render("(Coref (f a) b)") is None


def test_goal_regex_unchanged_for_sources_fallback():
    # sources_for's goal fallback still matches only binary heads
    assert P._GOAL.match("(Not (Current sk_x))") is None
    assert P.sources_for("(Not (Current sk_x))", "", {"fact_src": [["Member", "sk_x", "cls", "n1"]]}) == []


def _doc(results):
    return {"ts": time.time(), "spec_ts": time.time(), "cycle": 1, "status": "ok", "canary_ok": True, "results": results}


def test_load_candidates_admits_not_shapes_with_negation():
    proof = "(: (by xr_supersedes_not_current_ap (sl1 sl2)) (Not (Current sk_x)) (STV 1.0 0.88))"
    res = [{"goal": "(Not (Current sk_x))", "stv": [1.0, 0.88], "proof": proof, "sources": ["n1"],
            "facts": [], "rules": ["xr_supersedes_not_current_ap"]},
           {"goal": "(Not (Valid sk_y))", "stv": [1.0, 0.88], "proof": proof.replace("Current sk_x", "Valid sk_y"),
            "sources": ["n1"], "facts": [], "rules": ["xr_contradicts_not_ap"]},
           {"goal": "(Not (Member sk_x cls))", "stv": [1.0, 0.88], "proof": proof, "sources": ["n1"],
            "facts": [], "rules": []}]
    with tempfile.TemporaryDirectory() as d:
        json.dump(_doc(res), open(os.path.join(d, P.ADMIT_FILE), "w"))
        c, info = P.load_candidates({"shadow_dir": d, "reasoner_max_admit": 100, "gate_max_per_fact": 0}, None,
                                    live_ids=["n1"])
    assert sorted(x.content for x in c) == ["sk_x is no longer current", "sk_y no longer holds"]
    assert info["dropped"]["bad"] == 1
    assert all(x.provenance["polarity"] == "positive" for x in c)
