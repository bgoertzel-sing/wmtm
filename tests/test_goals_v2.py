"""v0.7: GoalChainer v2 as the goal engine's core.  Synthetic only: made-up people, ids and notes; no real memories.

Unit tests run v2 through the real subprocess client with a protocol-compatible test double (conftest.py).  The
test_real_* tests run the actual GoalChainer v2 runtime and are skipped unless WMTM_TEST_GC2_PYTHON points at its
interpreter (a separate environment; see docs/GOALS_V2.md)."""
import json
import os
import re
import sys
import time

import pytest

from wmtm import runtime_config as rc
from wmtm import goal_prompt as gp
from wmtm.goals import actions, engine, legitimacy, needs, v2

NOW = 1_800_000_000.0
D = 86400.0
MAP = {"9001": "quill", "9002": "wren", "9999": "botty"}
Q = "Open question for Quill: should the widget7 gadget be renamed to sprocket9?"
P = "Still pending: Wren to send the sprocket9 gear order for widget7."
OK = {"status": "ok", "queries": []}
GC2 = os.environ.get("WMTM_TEST_GC2_PYTHON", "")


def _it(i, text, age_d=2.0, sti=1.0):
    return {"id": "syn-%d" % i, "content": text, "sti": sti, "source_type": "recalled", "origin_ts": NOW - age_d * D}


def _cfg(tmp_path, **kw):
    (tmp_path / "completed").mkdir(exist_ok=True)
    return dict(rc.resolve(None, environ={}), goalchainer=True, runtime_dir=str(tmp_path / "rt"),
                goal_requests_dir=str(tmp_path / "completed"), semparse_dir=str(tmp_path / "none"),
                speaker_map=MAP, speaker_self="botty", **kw)


def _g(tmp_path, name):
    return tmp_path / "rt" / "goalchainer" / name


def _lines(p):
    return [json.loads(l) for l in open(p)] if p.exists() else []


def _prep(items, ctx=None, passes=("human",), **cfg):
    return engine.prepare_v2(items, dict({"speaker_map": MAP, "speaker_self": "botty"}, **cfg), ctx or {"autonomous": False},
                             now=NOW, passes=passes)


# ── defaults / switch ────────────────────────────────────────────────────────────────────────────────────────────
def test_engine_switch_defaults_to_v2_and_accepts_native():
    cfg = rc.resolve(None, environ={})
    assert cfg["goal_engine"] == "v2" and engine.engine_name(cfg) == "v2" and engine.engine_name({}) == "v2"
    assert engine.engine_name({"goal_engine": "native"}) == "native"
    assert engine.engine_name({"goal_engine": "bogus"}) == "v2"
    assert cfg["goal_v2_timeout_s"] == 60.0 and cfg["goal_v2_mem_mb"] == 1536 and cfg["goal_budget_s"] == 90.0


def test_native_switch_keeps_the_v06_core(tmp_path):
    run = engine.run_shadow([_it(1, Q)], OK, _cfg(tmp_path, goal_engine="native"), source="cycle", now=NOW)
    assert run["status"] == "ok" and run["engine"] == "native" and run["deontic_impl"] in ("local", "goal_chainer")
    assert "v2" not in run
    ln = _lines(_g(tmp_path, "proposals.jsonl"))
    assert ln and all("engine" not in l and "v2" not in l for l in ln)


# ── domain generation ────────────────────────────────────────────────────────────────────────────────────────────
def test_domain_generation_per_item_actions_needs_readings():
    p = _prep([_it(1, Q), _it(2, P, age_d=3.0)])
    job, amap = p["job"], p["amap"]
    h = job["header"]
    assert '(gc-domain "WMTM goals")' in h and "(gc-need unc settle_open_questions (scale 0 1) (band 0.8 1) (drive 1)" in h
    assert "(gc-need comp keep_commitments (scale 0 1) (band 0.8 1) (drive 1)" in h
    assert "(gc-goal settle_open_questions wmtm individual 1.0" in h and "(gc-signal automated_turn" in h
    # one gc-action per WMTM candidate, instantiated per item and person; action ids are plain names
    kinds = sorted(c["action"] for c in amap.values())
    assert "ClarifyQuestion" in kinds and "RemindPending" in kinds
    assert set(job["order"]) == set(amap) == set(job["blocks"])
    for a, c in amap.items():
        assert re.fullmatch(r"a\d\d_[a-z]+_[0-9a-f]{8}", a)
        b = job["blocks"][a]
        assert b.startswith("(gc-action %s %s " % (a, json.dumps(c["action"])))
        assert all("(given (wmtm-effect %s %s))" % (a, e) in b for e in c["effects"])
        assert "(candidate %s))" % a in b and "(signal item_" in b
        assert b.count("(gc-need-expectation %s " % a) == 2       # both needs declared (a missing one is unknown)
    ask = next(a for a, c in amap.items() if c["action"] == "ClarifyQuestion")
    assert "quill" in job["blocks"][ask] and "widget7" in job["blocks"][ask]
    # attributed readings (item ids, never text), need observations, both passes see the same items
    r = job["passes"][0]["readings"]
    assert {x["signal"] for x in r} >= {"automated_turn", "goal_review"}
    items = [x for x in r if x["signal"].startswith("item_")]
    assert items and all(x["state"] == "detected" and x["source"].startswith("wmtm:items:syn-") for x in items)
    assert all("widget7" not in x["source"] and "widget7" not in x["note"] for x in items)
    auto = next(x for x in r if x["signal"] == "automated_turn")
    assert auto["state"] == "refuted"
    obs = {o["need"]: o for o in job["observations"]}
    assert obs["unc"]["level"] == p["est"]["unc"]["level"] and obs["comp"]["level"] == p["est"]["comp"]["level"]


def test_metta_strings_are_escaped():
    p = _prep([_it(1, 'Open question for Quill: should the "widget7" gadget\\path be renamed to sprocket9?')])
    blk = next(iter(p["job"]["blocks"].values()))
    assert '\\"widget7\\"' in blk and "\\\\path" in blk and "\n(given" in blk


def test_expectations_cap_below_band_keep_order_and_break_ties():
    p = _prep([_it(1, Q)])
    est = p["est"]
    cands = list(p["amap"].values())
    raw = [v2.raw_change(c, est, p["st"], NOW) for c in cands]
    ch = v2.expectations(cands, est, p["st"], NOW)
    gap = est["unc"]["target"] - est["unc"]["level"]
    assert all(0 < x < gap for x in ch)                                 # never 'satisfied' by one action
    order_raw = sorted(range(len(cands)), key=lambda i: -raw[i])
    order_ch = sorted(range(len(cands)), key=lambda i: -ch[i])
    assert order_raw == order_ch and len(set(ch)) == len(ch)            # same order, no exact ties
    rep = v2.expectations(cands, est, p["st"], NOW, recent={cands[0]["key"]})
    assert v2.raw_change(cands[0], est, p["st"], NOW, {cands[0]["key"]}) == pytest.approx(raw[0] * legitimacy.REPEAT_DISCOUNT)
    assert rep[0] <= ch[0]


def test_stamp_reference_closes_the_referenced_note():
    a = {"id": "syn-1", "content": "Mar03 14:05 inventory. PENDING: diff the widget7 files against branch sprocket9-deploy, "
         "then commit them on a cleanup branch.", "sti": 1.0, "source_type": "recalled", "origin_ts": NOW - 2 * D}
    b = {"id": "syn-2", "content": "Mar04 09:10 the widget7 cleanup from Mar03 14:05 is done; pushed to a new branch.",
         "sti": 1.0, "source_type": "recalled", "origin_ts": NOW - 1.7 * D}
    c = {"id": "syn-3", "content": "Mar04 10:00 the cleanup from Mar03 14:05 is not done yet.", "sti": 1.0,
         "source_type": "recalled", "origin_ts": NOW - 1.7 * D}
    tr = []
    assert needs.extract([a, b], NOW, trace=tr) == []
    assert any(r == "closed_by_stamp_reference_note" for _i, _t, r in tr)
    assert [s["kind"] for s in needs.extract([a, c], NOW)] == ["self"]          # negated: still open
    assert needs.stamp(a["content"]) == "Mar03 14:05" and needs.stamp("no stamp here") is None


def test_duplicate_candidate_keys_reach_v2_once():
    """The same self-task can come from two rules (reminder and summary own-promise split): v2 sees it once."""
    dup = dict(engine.CANARY_FORBIDDEN, key="same-key", effects=["log"], action="SelfTask", who="self")
    p = engine.prepare_v2([_it(1, Q)], {"speaker_map": MAP}, {"autonomous": False}, now=NOW,
                          extra_candidates=[dup, dict(dup)])
    keys = [c["key"] for c in p["amap"].values()]
    assert keys.count("same-key") == 1 and len(keys) == len(set(keys))


# ── norm mapping ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_norms_mirror_legitimacy_rules():
    t = v2.norms_text()
    for rid, eff, _r, _p in legitimacy.RULES:
        kind = "always" if rid in v2.STRICT else "normally"
        assert "(%s %s (wmtm-effect ?a %s) (forbidden (do ?a)))" % (kind, rid, eff) in t
        if kind == "normally":
            assert "(prefer %s permit)" % rid in t
    for eff in legitimacy.AUTONOMOUS_EFFECTS:
        assert "(always no_autonomous_%s (and (signal automated_turn) (wmtm-effect ?a %s)) (forbidden (do ?a)))" % (eff, eff) in t
    assert "approved_change" not in t
    ta = v2.norms_text(approved=True)
    assert "(normally approved_change (approved ?a) (may (do ?a)))" in ta and "(prefer approved_change no_live_change)" in ta
    assert "(prefer approved_change no_git_memory)" not in ta          # strict rules are never lifted


def test_forbidden_actions_are_vetoed_by_v2(tmp_path):
    forb = dict(engine.CANARY_FORBIDDEN, who="quill")
    r = engine.propose_v2([_it(1, Q)], {"speaker_map": MAP}, {"autonomous": False}, now=NOW, extra_candidates=[forb])
    h = r["human"]
    f = next(c for c in h["candidates"] if c["key"] == "canary-forbidden")
    assert f["status"] == "vetoed" and f["legit"]["d"] == 0 and "no_live_change" in f["legit"]["rules"]
    assert all(p["key"] != "canary-forbidden" for p in h["proposals"])
    assert h["proposals"][0]["action"] == "ClarifyQuestion" and h["proposals"][0]["who"] == "quill"


def test_automated_pass_forbids_every_message_action():
    r = engine.propose_v2([_it(1, Q), _it(2, "PENDING: diff the widget7 branch against the sprocket9 tag.")],
                          {"speaker_map": MAP, "speaker_self": "botty"}, {"autonomous": True}, now=NOW,
                          passes=("automated", "human"))
    a, h = r["automated"], r["human"]
    assert not [p for p in a["proposals"] if p["action"] in actions.MESSAGE_ACTIONS]
    assert [p for p in a["proposals"] if p["action"] == "SelfTask"]
    msg = [c for c in a["candidates"] if c["action"] in actions.MESSAGE_ACTIONS]
    assert msg and all(c["status"] == "vetoed" and any(x.startswith("no_autonomous_") for x in c["legit"]["rules"])
                       for c in msg)
    assert [p for p in h["proposals"] if p["action"] == "ClarifyQuestion"]


# ── review -> proposal mapping ───────────────────────────────────────────────────────────────────────────────────
def _review(rid, disp, action=None, cands=(), value=0.2):
    rv = {"review_id": rid, "disposition": disp, "fingerprint": "sha256:" + rid, "engine": {"inferences": 5},
          "candidates": [{"action": a, "deontic": d} for a, d in cands], "steps": [], "deontic_support": [],
          "display_order": [], "hold": None, "escalation": None, "blockers": []}
    if disp == "propose":
        rv["proposal"] = {"action": action, "deontic": "permitted", "decided_at": "Pareto elimination",
                          "carrying_path": {"value": {"low": value, "high": value}}, "licensed_authority_ceiling": "advisory",
                          "authorization": "unresolved", "predicted_need_changes": []}
        rv["display_order"] = [{"action": action, "projection": value}]
        rv["deontic_support"] = [{"kind": "rule", "literal": "(lit pos P none do (%s))" % action, "label": "permit",
                                  "premises": [{"kind": "fact", "literal": "(lit pos none none signal (item_x))", "label": "f1"}]}]
    if disp == "hold":
        rv["hold"] = {"satisfied": ["unc"], "unserved": []}
    if disp == "escalate":
        rv["escalation"] = {"reasons": ["projection not decisive"], "contested": [a for a, _ in cands]}
    return rv


def test_review_to_proposal_mapping():
    p = _prep([_it(1, Q), _it(2, P, age_d=3.0)])
    ids = p["job"]["order"]
    ask = next(a for a in ids if "_ask_" in a)
    rem = next(a for a in ids if "_remind_" in a)
    cands = [(a, "permitted") for a in ids]
    reviews = [_review("r0", "propose", rem, cands, 0.3), _review("r1", "propose", ask, cands, 0.1),
               _review("r2", "escalate", None, cands)]
    res = engine.finish_v2(p, {"label": "main", "passes": [{"label": "human", "reviews": reviews}]}, "human")
    props = res["proposals"]
    assert ids.index(ask) < ids.index(rem)                                   # v2's order, not candidate order
    assert [x["action_id"] for x in props] == [rem, ask] and [x["v2"]["rank"] for x in props] == [1, 2]
    assert [x["v2"]["review_id"] for x in props] == ["r0", "r1"]
    for x in props:
        assert engine.check_proposal(x) is None and x["decision"] == "propose" and x["engine"] == "goalchainer-v2"
        assert x["status"] == "proposed" and x["legit"]["d"] == 1.0 and x["legit"]["impl"] == "goalchainer-v2"
        assert x["v2"]["proof"].startswith("P(do %s) <- permit" % x["action_id"]) and x["v2"]["plan"][0]["action"] == x["action"]
        assert x["score"] > 0 and set(engine.FIELDS) <= set(x)
    flag = next(c for c in res["candidates"] if c["action"] == "FlagUncertainty")
    assert flag["status"] == "dup" and flag["decision"] == "withdrawn"          # same person + topic as the Ask
    rest = [c for c in res["candidates"] if c["status"] not in ("proposed", "dup")]
    assert all(c["status"] == "escalated" and c["score"] == 0.0 for c in rest)
    assert [d["disposition"] for d in res["decisions"]] == ["propose", "propose", "escalate"]
    assert res["decisions"][2]["escalation"]["reasons"] == ["projection not decisive"]


@pytest.mark.parametrize("disp", ["hold", "escalate"])
def test_hold_and_escalate_are_logged_never_shown(tmp_path, monkeypatch, disp):
    orig = v2.client

    def client(job, cfg, wd):                       # the real client + fake runner; main's reviews replaced
        res = orig(job, cfg, wd)
        for s in res["series"]:
            if s["label"] == "main":
                ids = next(j for j in job["series"] if j["label"] == "main")["order"]
                for p in s["passes"]:
                    p["reviews"] = [_review("m0", disp, None, [(a, "permitted") for a in ids])]
        return res
    monkeypatch.setattr(v2, "client", client)
    cfg = _cfg(tmp_path, goal_prompt=True)
    run = engine.run_shadow([_it(1, Q)], OK, cfg, source="cycle", now=NOW)
    assert run["status"] == "ok" and run["canary"]["ok"] and run["v2"]["decisions"] == {disp: 1} and run["logged"] == 0
    assert run["v2"]["reviews"][0]["disposition"] == disp
    assert ("hold" in run["v2"]["reviews"][0]) if disp == "hold" else run["v2"]["reviews"][0]["escalation"]["reasons"]
    assert not _g(tmp_path, "proposals.jsonl").exists()
    lat = json.load(open(_g(tmp_path, "latest.json")))
    assert lat["status"] == "ok" and lat["proposals"] == []
    assert gp.render(cfg, now=NOW + 10, speaker="quill") is None


# ── the run: records, display, latest ────────────────────────────────────────────────────────────────────────────
def test_run_shadow_v2_records_and_prompt(tmp_path):
    cfg = _cfg(tmp_path, goal_prompt=True, goal_v2_release="test-tag")
    run = engine.run_shadow([_it(1, Q)], OK, cfg, source="cycle", now=NOW)
    assert run["status"] == "ok" and run["engine"] == "v2" and run["canary"]["ok"] and run["logged"] >= 1
    assert run["deontic_impl"] == "goalchainer-v2" and run["v2"]["status"] == "ok" and run["v2"]["release"] == "test-tag"
    assert run["v2"]["decisions"].get("propose", 0) >= 1 and run["v2"]["series"] == 2   # canary + main (the negative canary has no candidate)
    ln = _lines(_g(tmp_path, "proposals.jsonl"))
    assert ln[0]["action"] == "ClarifyQuestion" and ln[0]["who"] == "quill" and ln[0]["decision"] == "propose"
    assert ln[0]["engine"] == "goalchainer-v2" and ln[0]["v2"]["rank"] == 1 and ln[0]["v2"]["proof"]
    assert all(engine.check_proposal(l) is None for l in ln)
    lat = json.load(open(_g(tmp_path, "latest.json")))
    assert lat["canary_ok"] and lat["proposals"][0]["decision"] == "propose"
    out = gp.render(cfg, now=NOW + 10, speaker="quill", record=True)
    assert out and "Open question for you: should the widget7 gadget be renamed to sprocket9?" in out
    assert _lines(_g(tmp_path, "asked.jsonl"))[0]["who"] == "quill"
    assert not [p for p in os.listdir(tmp_path / "rt" / "goalchainer") if p.startswith(".v2work")]   # scratch removed


def test_run_shadow_v2_automated_display_only(tmp_path):
    cfg = _cfg(tmp_path, goal_prompt=True)
    run = engine.run_shadow([_it(1, Q)], OK, cfg, source="automated", now=NOW)
    assert run["status"] == "ok" and run["autonomous"] and run["display_only"] >= 1
    assert not [l for l in _lines(_g(tmp_path, "proposals.jsonl")) if l["action"] in actions.MESSAGE_ACTIONS]
    disp = _lines(_g(tmp_path, "display.jsonl"))
    assert disp and disp[0]["display_only"] and disp[0]["decision"] == "propose" and disp[0]["engine"] == "goalchainer-v2"


def test_shadow_canary_fail_does_not_start_v2(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("v2 must not run")
    monkeypatch.setattr(v2, "client", boom)
    run = engine.run_shadow([_it(1, Q)], {"status": "canary_fail"}, _cfg(tmp_path), now=NOW)
    assert run["status"] == "shadow_canary_fail" and not _g(tmp_path, "proposals.jsonl").exists()


# ── failures: no proposals, logged ───────────────────────────────────────────────────────────────────────────────
def _script(tmp_path, body):
    p = tmp_path / "runner.py"; p.write_text("import sys, time\n" + body + "\n")
    return str(p)


@pytest.mark.parametrize("body,status", [
    ("time.sleep(30)", "v2_timeout"),
    ("sys.stderr.write('Traceback: synthetic'); sys.exit(1)", "v2_crash"),
    ("sys.stdout.write('not json')", "v2_bad_output"),
    ("sys.stdout.write('{\"protocol\": \"wmtm-gc2-result-v1\", \"series\": [], \"error\": \"ImportError: x\"}')", "v2_error"),
    ("sys.stdout.write('{\"protocol\": \"wmtm-gc2-result-v1\", \"series\": []}')", "canary_fail"),
])
def test_runner_failures_give_no_proposals_and_are_logged(tmp_path, body, status):
    old = tmp_path / "rt" / "goalchainer"; old.mkdir(parents=True)
    (old / "latest.json").write_text(json.dumps({"status": "ok", "canary_ok": True, "ts": NOW, "proposals": [
        {"id": "x", "action": "ClarifyQuestion", "who": "quill", "text": "Ask quill: old", "status": "proposed"}]}))
    cfg = _cfg(tmp_path, goal_v2_runner=_script(tmp_path, body), goal_v2_timeout_s=2.0, goal_prompt=True)
    t = time.time()
    run = engine.run_shadow([_it(1, Q)], OK, cfg, source="cycle", now=NOW)
    assert time.time() - t < 15
    assert run["status"] == status and run["canary"]["ok"] is False
    assert not _g(tmp_path, "proposals.jsonl").exists()
    last = _lines(_g(tmp_path, "runs.jsonl"))[-1]
    assert last["status"] == status and last["engine"] == "v2"
    lat = json.load(open(_g(tmp_path, "latest.json")))
    assert lat["proposals"] == [] and lat["canary_ok"] is False          # an older run's suggestions never survive
    assert gp.render(cfg, now=NOW + 10, speaker="quill") is None
    assert not [p for p in os.listdir(old) if p.startswith(".v2work")]


def test_unconfigured_runtime_is_logged(tmp_path):
    run = engine.run_shadow([_it(1, Q)], OK, _cfg(tmp_path, goal_v2_python=str(tmp_path / "nope")), now=NOW)
    assert run["status"] == "v2_unconfigured" and not _g(tmp_path, "proposals.jsonl").exists()


def test_timeout_kills_the_runner_process_group(tmp_path):
    pidf = tmp_path / "child.pid"
    body = ("import subprocess\np = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
            "open(%r, 'w').write(str(p.pid))\ntime.sleep(60)" % str(pidf))
    cfg = _cfg(tmp_path, goal_v2_runner=_script(tmp_path, body), goal_v2_timeout_s=2.0)
    run = engine.run_shadow([_it(1, Q)], OK, cfg, now=NOW)
    assert run["status"] == "v2_timeout"
    pid = int(pidf.read_text())
    for _ in range(50):
        try:
            os.kill(pid, 0)
            st = open("/proc/%d/stat" % pid).read().rsplit(")", 1)[1].split()[0]
            if st == "Z":
                break
        except (OSError, IndexError):
            break
        time.sleep(0.1)
    else:
        pytest.fail("grandchild still running")


def test_runner_is_standalone_and_licence_boundary_holds():
    root = os.path.dirname(rc.__file__)
    src = open(os.path.join(root, "goals", "v2_runner.py")).read()
    assert "import wmtm" not in src and "from wmtm" not in src and "from ." not in src
    imports = set(re.findall(r"^\s*(?:from|import) ([\w.]+)", src, re.M))
    assert imports <= {"argparse", "json", "os", "sys", "time", "resource", "importlib", "goal_chainer.motivation",
                       "goal_chainer.requests", "goal_chainer.runtime.budget"}, imports
    for dp, _, fs in os.walk(root):                                     # no WMTM module imports goal_chainer
        for f in fs:
            if f.endswith(".py") and f != "v2_runner.py":
                s = open(os.path.join(dp, f)).read()
                m = re.findall(r"^\s*(?:from|import) (goal_chainer[\w.]*)", s, re.M)
                # only the optional GoalChainer v1 (MIT) entry points of the old bridges / native fallback; v2
                # removed these modules, and the v2 core is reached through the runner process only
                assert set(m) <= {"goal_chainer.pipeline", "goal_chainer.deontic", "goal_chainer.models"}, (f, m)


# ── real GoalChainer v2 runtime (separate environment) ───────────────────────────────────────────────────────────
real = pytest.mark.skipif(not (GC2 and os.path.exists(GC2)), reason="WMTM_TEST_GC2_PYTHON not set")


def _real(**kw):
    return dict({"goal_v2_python": GC2, "goal_v2_runner": "", "speaker_map": MAP, "speaker_self": "botty"}, **kw)


@real
def test_real_goal_canary():
    can = engine.goal_canary_v2(_real())
    assert can["ok"], can


@real
def test_real_clarify_to_the_right_person_and_live_change_blocked():
    forb = dict(engine.CANARY_FORBIDDEN, who="wren", text="Turn widget7 on in the live flags file for wren")
    r = engine.propose_v2([_it(1, Q), _it(2, P, age_d=3.0)], _real(), {"autonomous": False}, now=NOW,
                          extra_candidates=[forb], passes=("human", "automated"))
    h, a = r["human"], r["automated"]
    ask = [p for p in h["proposals"] if p["action"] == "ClarifyQuestion"]
    assert ask and ask[0]["who"] == "quill" and "widget7" in ask[0]["text"] and ask[0]["v2"]["fingerprint"].startswith("sha256:")
    assert ask[0]["v2"]["proof"].startswith("P(do ") and ask[0]["decision"] == "propose"
    f = next(c for c in h["candidates"] if c["key"] == "canary-forbidden")
    assert f["status"] == "vetoed" and "no_live_change" in f["legit"]["rules"] and f["legit"]["reasons"][0].startswith("F(do ")
    assert all(engine.check_proposal(p) is None for p in h["proposals"])
    assert not [p for p in a["proposals"] if p["action"] in actions.MESSAGE_ACTIONS]
    assert r["_runner"]["versions"]["pymetta"].startswith("0.9.4+goalchainer.native")


@real
def test_real_hold_when_needs_are_in_band():
    r = engine.propose_v2([_it(1, Q)], _real(goal_targets="0.3,0.3"), {"autonomous": False}, now=NOW)
    h = r["human"]
    assert h["proposals"] == [] and h["decisions"][0]["disposition"] == "hold"
    assert "unc" in h["decisions"][0]["hold"]["satisfied"]
