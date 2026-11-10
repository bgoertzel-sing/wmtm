"""Unit tests for judge_v2.py (v2 W1 rule, andy Work msg 355). Synthetic ids/facts only."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import judge_v2 as J

W4 = {}

def _ext(tmp_path, premises, proof, goal, nw=None):
    sh = tmp_path / "shadow.jsonl"
    sh.write_text(json.dumps({"queries": [{"goal": goal, "ok": True, "stv": [0.9, 0.8], "proof": proof}]}) + "\n")
    return {"shadow": str(sh), "premises": premises, "gate_rejected": [], "nw_symbol_notes": nw or {}}

def test_identical_class_fact_in_two_notes_is_corroboration_not_w1(tmp_path):
    P = {"sp0": {"src": "n1", "fact": "(Member sk_a__i_n1 pilot)"},
         "sp1": {"src": "n1", "fact": "(Inheritance pilot person)"},
         "sp2": {"src": "n2", "fact": "(Inheritance pilot person)"}}
    e = _ext(tmp_path, P, "sp0 sp2", "(Member sk_a__i_n1 person)")
    c0, _ = J.judge(e, W4, False); c1, _ = J.judge(e, W4, True)
    assert c0["W1"] == 1 and c1["W1"] == 0

def test_negative_different_class_facts_stay_w1(tmp_path):
    P = {"sp0": {"src": "n1", "fact": "(Member sk_a__i_n1 pilot)"},
         "sp2": {"src": "n2", "fact": "(Inheritance pilot person)"}}
    e = _ext(tmp_path, P, "sp0 sp2", "(Member sk_a__i_n1 person)")
    assert J.judge(e, W4, True)[0]["W1"] == 1

def test_negative_witness_fact_in_two_notes_stays_w1(tmp_path):
    P = {"sp0": {"src": "n1", "fact": "(Member sk_a__i_n1 pilot)"},
         "sp1": {"src": "n2", "fact": "(Member sk_a__i_n1 pilot)"},
         "sp2": {"src": "n2", "fact": "(Member sk_a__i_n1 tall)"}}
    # the proof uses the witness fact from n1 and a fact from n2: a witness fact repeated in n2 is not corroboration
    e = _ext(tmp_path, P, "sp0 sp2", "(Member sk_a__i_n1 x)")
    assert J.judge(e, W4, False)[0]["W1"] == 1 and J.judge(e, W4, True)[0]["W1"] == 1

def test_nwdef_join_unchanged(tmp_path):
    P = {"sp0": {"src": "n1", "fact": "(Member sk_c__i_n1 config__nw_b)"}}
    e = _ext(tmp_path, P, "sp0 nwdef_config__nw_b1a247bbd8", "(Member sk_c__i_n1 config)",
             nw={"config__nw_b1a247bbd8": ["n1", "n2"]})
    assert J.judge(e, W4, False)[0]["W1"] == 1 and J.judge(e, W4, True)[0]["W1"] == 1
