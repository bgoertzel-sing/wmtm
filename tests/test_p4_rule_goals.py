"""P4 rev3: parser Implication rules propose goals (real atoms from cached parse of note 20261028T190214Z)."""
from wmtm import pc_shadow as ps

FACT = ("Member", "hive_t_2026_10_28_goalchainer_v2_status", "branch__nw_50b94ee13a")
RULES = [
    "(: i_ep_note_20261028T190214Z__n7_implication (Implication (Member hive_t_2026_10_28_goalchainer_v2_status branch__nw_50b94ee13a) (Member hive_t_2026_10_28_goalchainer_v2_status local)) (STV 0.9 0.7))",
    "(: nwdef_branch__nw_50b94ee13a (Implication (Member $x branch__nw_50b94ee13a) (Member $x branch)) (CTV (STV 1.0 0.99) (STV 0.0 0.0)))",
]

def test_parsed_rule_proposes_goal():
    pool = ps.rule_goal_pool({FACT}, RULES, 3)
    assert ("Member", FACT[1], "local") in pool and ("Member", FACT[1], "branch") in pool
    hops, chain = pool[("Member", FACT[1], "local")]
    assert hops == 1 and chain[0] == FACT and chain[-1][0] == "Rule"

def test_and_premise_and_two_hops():
    rules = ["(: r1 (Implication (And (Member $x a) (Member $x b)) (Member $x c)) (STV 1.0 0.9))",
             "(: r2 (Implication (Member $x c) (Member $x d)) (STV 1.0 0.9))"]
    pool = ps.rule_goal_pool({("Member", "bob", "a"), ("Member", "bob", "b")}, rules, 3)
    assert pool[("Member", "bob", "c")][0] == 1 and pool[("Member", "bob", "d")][0] == 2
    assert ps.rule_goal_pool({("Member", "bob", "a")}, rules, 3) == {}

def test_function_term_consequent_skipped():
    rules = ["(: r (Implication (Member $y skip) (Member (sk_depend__n $y) depend)) (STV 0.9 0.7))"]
    assert ps.rule_goal_pool({("Member", "s", "skip")}, rules, 3) == {}


# --- review 2 finding 1: real-engine test of a PARSED note chaining (no fake "x is a y" parser) ---
import json, os, subprocess, sys
import pytest
from wmtm import runtime_config as rc
from wmtm.store import WMTMStore

_FIX = os.path.join(os.path.dirname(__file__), "fixtures", "p4_note_190214Z", "parse.json")
_CFG = rc.resolve()   # vendor paths; override with WMTM_PC_PETTA / WMTM_PC_VENDOR / WMTM_SWIPL_BIN
HAVE_PC = os.path.isdir(os.path.join(_CFG["petta_dir"], "python")) and os.path.isdir(os.path.join(_CFG["pettachainer_dir"], "pettachainer"))
GOAL = "(Member sk_bundle_1__i_ep_note_20261028T190214Z acl_d)"   # B #9, hand-judged CORRECT


def _parsed_store(monkeypatch):
    fx = json.load(open(_FIX))
    st = WMTMStore(); st.admit(fx["item_id"], "note 190214Z", source_type="recalled", initial_sti=1.0)
    monkeypatch.setattr(ps, "_cache_lookup", lambda items, *a, **k: {it.id: list(fx["atoms"]) for it in items})
    return st


def test_parsed_note_proposes_rule_goal(monkeypatch):
    spec = ps.build_snapshot(_parsed_store(monkeypatch), cycle=1)
    assert spec["goal_rank"]["pool"] > 0 and GOAL in spec["goals"]


@pytest.mark.skipif(not HAVE_PC, reason="vendored PeTTa / PeTTaChainer not present")
def test_parsed_note_chains_on_real_engine(monkeypatch, tmp_path):
    spec = ps.build_snapshot(_parsed_store(monkeypatch), cycle=1)
    sp = tmp_path / "spec.json"; sp.write_text(json.dumps(spec)); out = tmp_path / "shadow.jsonl"
    code = subprocess.run([sys.executable, "-m", "wmtm.workers.pc_shadow", "--spec", str(sp), "--out", str(out), "--timeout", "10"],
                          env=rc.worker_env(_CFG), cwd=rc.DIST_ROOT, timeout=300).returncode
    rec = json.loads(out.read_text().strip().splitlines()[-1])
    assert code == 0 and rec["status"] == "ok" and rec["canary"]["ok"] and not rec["neg"]["ok"]
    q = {x["goal"]: x for x in rec["queries"]}
    proof = q[GOAL].get("proof") or ""
    assert q[GOAL]["ok"] and q[GOAL].get("stv") and ("nwdef" in proof or "implication" in proof)
