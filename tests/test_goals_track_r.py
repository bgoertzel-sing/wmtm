"""Track R: GoalChainer phase 1 (log only).  Synthetic / mocked only: no real memories, made-up names and ids."""
import json, os
from wmtm import runtime_config as rc
from wmtm.goals import engine, legitimacy, needs, actions

NOW = 1_800_000_000.0
D = 86400.0
SM = {"speaker_map": {"quill": "quill", "9001": "quill", "wren": "wren"}, "speaker_self": "botty"}   # made-up people
ST = engine.settings(SM)


def _it(i, text, sti=1.0, age_d=1.0):
    return {"id": "syn-%d" % i, "content": text, "sti": sti, "source_type": "recalled", "origin_ts": NOW - age_d * D}


def test_goal_canary_passes():
    r = engine.goal_canary({})
    assert r["ok"], r


def test_no_signals_no_urge():
    est = needs.estimate([_it(1, "The widget3 is a gadget3 and works fine.")], NOW)
    assert est["unc"]["urge"] == 0.0 and est["comp"]["urge"] == 0.0
    assert engine.propose([_it(1, "The widget3 is a gadget3 and works fine.")], {}, now=NOW)["proposals"] == []


def test_urge_rises_with_count_age_and_salience():
    one = needs.estimate([_it(1, "Open question for Quill: should widget1 use the blue sprocket?")], NOW, ST)
    two = needs.estimate([_it(1, "Open question for Quill: should widget1 use the blue sprocket?"),
                          _it(2, "Open question for Wren: should gadget2 move to the red bracket next week?")], NOW, ST)
    old = needs.estimate([_it(1, "Open question for Quill: should widget1 use the blue sprocket?", age_d=6)], NOW, ST)
    low = needs.estimate([_it(1, "Open question for Quill: should widget1 use the blue sprocket?", sti=0.1),
                          _it(9, "unrelated filler text about widgets", sti=1.0)], NOW, ST)
    assert two["unc"]["urge"] > one["unc"]["urge"] > 0
    assert old["unc"]["urge"] > one["unc"]["urge"]
    assert low["unc"]["urge"] < one["unc"]["urge"]


def test_urge_formula_clipped():
    assert needs.urge(1.0, 0.8, 2.0) == 0.0
    assert abs(needs.urge(0.4, 0.8, 2.0) - 1.0) < 1e-9
    assert needs.urge(0.0, 0.8, 1.0) == 1.0


def test_resolved_question_is_dropped():
    items = [_it(1, "Open question for Quill: should widget1 use the blue sprocket bracket?", age_d=3),
             _it(2, "Quill answered: widget1 should use the blue sprocket bracket.", age_d=1)]
    est = needs.estimate(items, NOW)
    assert est["unc"]["signals"] == []


def test_competence_pending_and_failed():
    items = [_it(1, "Pending: the gadget5 replay is not yet sent to Quill.", age_d=2),
             _it(2, "Still waiting on Quill for the widget6 sprocket count.", age_d=2),
             _it(3, "The widget6 canary failed on the second sprocket run.")]   # R2: 'failed' alone is not an open item
    r = engine.propose(items, SM, {"requester": "quill"}, now=NOW)
    acts = {p["action"] for p in r["all_proposed"]}
    assert "RemindPending" in acts and "SummarizeStatus" in acts
    assert not any("canary failed" in p["text"] for p in r["all_proposed"])
    assert r["needs"]["comp"]["urge"] > 0


def test_forbidden_effects_vetoed():
    for eff in ("live_change", "push", "git_memory", "write"):
        c = {"key": "k-" + eff, "effects": ["message", eff]}
        lg = legitimacy.evaluate(c, {}, {})
        assert lg["d"] == 0.0 and lg["status"] == "forbidden", eff


def test_autonomous_turn_vetoes_messages_not_lookups():
    items = [_it(1, "Open question for Quill: which branch holds the widget1 sprocket fix?")]
    r = engine.propose(items, SM, {"autonomous": True}, now=NOW)
    assert r["proposals"]
    assert all(p["action"] == "LookUp" for p in r["proposals"])
    assert any(c["action"] == "ClarifyQuestion" and c["status"] == "vetoed" for c in r["candidates"])


def test_vetoed_never_passes_structural_check():
    items = [_it(1, "Open question for Quill: should widget1 use the blue sprocket?")]
    r = engine.propose(items, SM, {"autonomous": True}, now=NOW)
    assert r["vetoed"]
    for c in r["vetoed"]:
        assert engine.check_proposal(c) is not None
    assert engine.check_proposal({"id": "x"}) == "missing action"


def test_repeat_discount():
    items = [_it(1, "Open question for Quill: should widget1 use the blue sprocket?")]
    a = engine.propose(items, SM, now=NOW)["proposals"][0]
    b = engine.propose(items, SM, {"recent": {a["id"]}}, now=NOW)
    again = [c for c in b["candidates"] if c["id"] == a["id"]][0]
    assert abs(again["score"] - a["score"] * legitimacy.REPEAT_DISCOUNT) < 1e-3


def test_kb_proof_supports_lookup():
    items = [_it(1, "Open question for Quill: which branch holds the widget1 sprocket fix?")]
    no = [c for c in engine.propose(items, SM, now=NOW)["candidates"] if c["action"] == "LookUp"][0]
    yes = [c for c in engine.propose(items, SM, now=NOW, kb=["(: p (Member widget1 sprocket) (STV 1 0.9))"])["candidates"]
           if c["action"] == "LookUp"][0]
    assert yes["score"] > no["score"] and "widget1" in yes["proof"]


def test_parser_queries_feed_uncertainty():
    it = _it(1, "The widget1 sprocket was installed.")
    it["queries"] = ["(: $q (Location widget1 $where) (STV 1.0 0.9))"]
    est = needs.estimate([it], NOW)
    assert est["unc"]["signals"] and est["unc"]["signals"][0]["origin"] == "parser"


def test_flag_default_off_and_spec():
    cfg = rc.resolve(None, environ={})
    assert cfg["goalchainer"] is False
    assert engine.run_shadow([], {"status": "ok"}, cfg) is None


def test_run_shadow_logs_only_when_on(tmp_path):
    cfg = dict(rc.resolve(None, environ={}), goalchainer=True, runtime_dir=str(tmp_path), semparse_dir=str(tmp_path / "sp"),
               **SM)
    items = [_it(1, "Open question for Quill: should widget1 use the blue sprocket?")]
    run = engine.run_shadow(items, {"status": "ok", "queries": []}, cfg, source="cycle", now=NOW)
    assert run["status"] == "ok" and run["logged"] >= 1 and run["canary"]["ok"]
    lines = [json.loads(l) for l in open(tmp_path / "goalchainer" / "proposals.jsonl")]
    assert lines[0]["action"] == "ClarifyQuestion" and all(engine.check_proposal(l) is None for l in lines)
    run2 = engine.run_shadow(items, {"status": "ok", "queries": []}, cfg, source="cycle", now=NOW + 60)
    assert run2["logged"] == 0                     # repeat window
    assert sorted(os.listdir(tmp_path / "goalchainer")) == ["proposals.jsonl", "runs.jsonl"]


def test_run_shadow_respects_shadow_canary(tmp_path):
    cfg = dict(rc.resolve(None, environ={}), goalchainer=True, runtime_dir=str(tmp_path))
    run = engine.run_shadow([_it(1, "Should widget1 move?")], {"status": "canary_fail"}, cfg, now=NOW)
    assert run["status"] == "shadow_canary_fail"
    assert not (tmp_path / "goalchainer" / "proposals.jsonl").exists()


def test_run_shadow_automated_is_autonomous(tmp_path):
    cfg = dict(rc.resolve(None, environ={}), goalchainer=True, runtime_dir=str(tmp_path), semparse_dir=str(tmp_path / "sp"),
               **SM)
    run = engine.run_shadow([_it(1, "Open question for Quill: which branch holds the widget1 sprocket fix?")],
                            {"status": "ok"}, cfg, source="automated", now=NOW)
    assert run["logged"] >= 1
    assert run["autonomous"] is True
    for l in open(tmp_path / "goalchainer" / "proposals.jsonl"):
        assert "message" not in json.loads(l)["effects"]


def test_goal_chainer_deontic_reused_when_present(tmp_path):
    src = os.environ.get("WMTM_GOALCHAINER_SRC", "")   # GoalChainer checkout, if any (machine-specific: env only)
    impl = legitimacy.deontic_impl({"goalchainer_src": src})[2]
    assert impl in ("goal_chainer", "local")
    assert legitimacy.deontic_impl({"goalchainer_src": str(tmp_path / "missing")})[2] in ("goal_chainer", "local")


def test_worker_hook_present():
    src = open(os.path.join(os.path.dirname(rc.__file__), "workers", "pc_shadow.py")).read()
    assert "from wmtm.goals import run_shadow" in src and 'CFG.get("goalchainer")' in src


def test_raw_item_carries_origin_ts():
    from wmtm import pc_shadow
    r = pc_shadow.raw_item_from_dict({"id": "a", "content": "x", "origin_timestamp": 123.0})
    assert r["origin_ts"] == 123.0


def test_resolution_report_is_not_a_question():
    for txt in ("RESOLVED the open question from 17:16 about widget4 versus gadget4 counts.",
                "Quill answered the open question about the widget1 sprocket bracket."):
        assert needs.classify(txt) is None, txt
