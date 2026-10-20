"""v0.6.0-rc1: goal engine live wiring (request history from completed/ request files, budget, error logging, re-ask
history) and the log-only guarantees.  Synthetic only: made-up people, ids, chats and notes; no real memories."""
import json
import os
import re
import stat
import time

import pytest

from wmtm import pc_shadow
from wmtm import runtime_config as rc
from wmtm.api import WMTM, WMTMConfig
from wmtm.goals import engine, needs
from wmtm.goals import requests as greq

NOW = 1_800_000_000.0
D = 86400.0
MAP = {"9001": "quill", "wren_x": "wren", "9002": "wren", "9999": "botty"}      # made-up ids/usernames -> names
SM = {"speaker_map": MAP, "speaker_self": "botty"}
QUESTION = "Open question for Quill: should the widget7 gadget be renamed to sprocket9?"
CTX = ("<external_untrusted_telegram_group_context>\n"
       "[message_id=11 user_id=9002 sender_is_bot=false sender_username=\"wren_x\" sender_name=\"W\"] widget7 sprocket9 "
       "renamed already\n</external_untrusted_telegram_group_context>\n")


def _it(i, text, age_d=2.0, sti=1.0):
    return {"id": "syn-%d" % i, "content": text, "sti": sti, "source_type": "recalled", "origin_ts": NOW - age_d * D}


def _req(d, name, prompt, source, mtime):
    p = d / name
    p.write_text(json.dumps({"schema_version": 1, "identity": "Botty", "request_id": name[:-5], "prompt": prompt,
                             "prompt_sha256": "0" * 64, "source": source}))
    os.utime(p, (mtime, mtime))
    return p


def _cfg(tmp_path, chan, **kw):
    return dict(SM, goalchainer=True, runtime_dir=str(tmp_path / "rt"), goal_requests_dir=str(chan),
                semparse_dir=str(tmp_path / "none"), **kw)


# ── request history ─────────────────────────────────────────────────

def test_sender_from_envelope_only(tmp_path):
    assert greq.sender({"chat_id": -5, "message_id": 1, "update_id": 1, "user_id": 9001}, MAP) == "quill"
    assert greq.sender({"chat_id": -5, "message_id": 1, "update_id": 1, "sender_username": "@Wren_X"}, MAP) == "wren"
    assert greq.sender({"chat_id": 9002, "message_id": 1, "update_id": 1}, MAP) == "wren"        # private chat
    assert greq.sender({"chat_id": -5, "message_id": 1, "update_id": 1}, MAP) is None             # group, no sender
    assert greq.sender({"chat_id": 9999, "message_id": 1, "update_id": 1}, MAP, "botty") is None  # never the bot
    assert greq.sender({"chat_id": 4242, "message_id": 1, "update_id": 1}, MAP) is None           # unmapped
    # quoted group context names other people; it is stripped and never used as the sender
    assert greq.request_text(CTX + "@Botty please check") == "@Botty please check"


def test_index_is_bounded_cached_and_holds_no_raw_text(tmp_path):
    chan = tmp_path / "completed"; chan.mkdir()
    secret = "zebracorn marmalade quantum"   # must never be copied to the index
    _req(chan, "a" * 64 + ".json", CTX + "[reply to your message 7] the widget7 rename is fine, " + secret,
         {"chat_id": -5, "message_id": 12, "update_id": 1, "user_id": 9001}, NOW - D)
    _req(chan, "b" * 64 + ".json", "group request without a sender", {"chat_id": -5, "message_id": 13, "update_id": 2},
         NOW - D)
    _req(chan, "c" * 64 + ".json", "too old", {"chat_id": 9001, "message_id": 14, "update_id": 3}, NOW - 30 * D)
    (chan / ("d" * 64 + ".json")).write_text(json.dumps({"request_id": "d", "response": "bot reply", "source": {}}))
    os.utime(chan / ("d" * 64 + ".json"), (NOW - D, NOW - D))
    (chan / "broken.json").write_text("{not json")
    os.utime(chan / "broken.json", (NOW - D, NOW - D))
    cfg = _cfg(tmp_path, chan)
    st = {}
    reqs = greq.load(cfg, NOW, st)
    assert [r["who"] for r in reqs] == ["quill"] and reqs[0]["reply"] is True
    assert "widget7" in reqs[0]["keys"] and abs(reqs[0]["ts"] - (NOW - D)) < 1e-3
    assert st["files"] == 4 and st["parsed"] == 4 and st["with_sender"] == 1 and st["read_errors"] == 1
    ip = tmp_path / "rt" / "goalchainer" / greq.INDEX
    raw = ip.read_text()
    assert secret not in raw and "reply to your message" not in raw and "without a sender" not in raw
    assert stat.S_IMODE(os.stat(ip).st_mode) == 0o600
    st2 = {}
    assert greq.load(cfg, NOW, st2) == reqs and st2["parsed"] == 0              # cached: nothing re-read
    st3 = {}
    greq.load(dict(cfg, speaker_map={}), NOW, st3)
    assert st3["parsed"] == st3["files"] and st3["with_sender"] == 0            # map changed -> rebuilt
    assert sorted(os.listdir(chan)) == sorted(["a" * 64 + ".json", "b" * 64 + ".json", "c" * 64 + ".json",
                                               "d" * 64 + ".json", "broken.json"])   # read-only: nothing added


def test_cap_and_missing_dir(tmp_path):
    chan = tmp_path / "completed"; chan.mkdir()
    for i in range(5):
        _req(chan, "%064d.json" % i, "widget%d sprocket check" % i, {"chat_id": 9001, "message_id": i, "update_id": i},
             NOW - D + i)
    st = {}
    reqs = greq.load(_cfg(tmp_path, chan, goal_requests_max=2), NOW, st)
    assert st["files"] == 2 and [round(r["ts"]) for r in reqs] == [round(NOW - D + 3), round(NOW - D + 4)]
    st = {}
    assert greq.load(_cfg(tmp_path, tmp_path / "nope"), NOW, st) == [] and "error" in st
    st = {}
    assert greq.load(dict(SM, runtime_dir=str(tmp_path / "rt")), NOW, st) == [] and st["dir"] == "unset"


def test_digest_matches_text_semantics():
    reqs_text = [{"ts": NOW - D, "who": "quill", "text": "[reply to your message 3] widget7 rename ok"},
                 {"ts": NOW - D, "who": "wren", "text": "answers to 10:30: the gadget9 bracket is gone now"}]
    reqs_dig = [dict(ts=r["ts"], who=r["who"], **needs.request_digest(r["text"])) for r in reqs_text]
    items = [_it(1, QUESTION), _it(2, "Blocked on Wren: which gadget9 bracket goes on the widget5 frame?")]
    a = engine.propose(items, dict(SM, goal_requests=reqs_text), {"autonomous": False}, now=NOW)
    b = engine.propose(items, dict(SM, goal_requests=reqs_dig), {"autonomous": False}, now=NOW)
    assert [p["id"] for p in a["all_proposed"]] == [p["id"] for p in b["all_proposed"]]
    assert a["suppressed"] == b["suppressed"]


def test_reply_in_completed_closes_the_question(tmp_path):
    chan = tmp_path / "completed"; chan.mkdir()
    items = [_it(1, QUESTION)]
    run = engine.run_shadow(items, {"status": "ok", "queries": []}, _cfg(tmp_path, chan), source="cycle", now=NOW)
    assert run["status"] == "ok" and run["logged"] >= 1 and run["requests"]["with_sender"] == 0
    # the addressee replies on the topic (group chat, sender in the envelope) -> nothing more to ask
    _req(chan, "e" * 64 + ".json", CTX + "[reply to your message 9] keep widget7, no sprocket9 rename",
         {"chat_id": -5, "message_id": 20, "update_id": 9, "user_id": 9001}, NOW - D)
    rt2 = tmp_path / "rt2"
    run2 = engine.run_shadow(items, {"status": "ok", "queries": []}, dict(_cfg(tmp_path, chan), runtime_dir=str(rt2)),
                             source="cycle", now=NOW)
    assert run2["status"] == "ok" and run2["requests"]["with_sender"] == 1
    props = (rt2 / "goalchainer" / "proposals.jsonl")
    assert not props.exists() or not any(json.loads(l)["action"] == "ClarifyQuestion" for l in props.read_text().splitlines())


def test_history_blocks_reask_after_repeat_window(tmp_path):
    cfg = _cfg(tmp_path, tmp_path / "completed", goal_repeat_s=60.0)
    (tmp_path / "completed").mkdir()
    r1 = engine.run_shadow([_it(1, QUESTION)], {"status": "ok", "queries": []}, cfg, now=NOW)
    assert r1["logged"] >= 1
    r2 = engine.run_shadow([_it(1, QUESTION)], {"status": "ok", "queries": []}, cfg, now=NOW + 3600)
    assert r2["status"] == "ok" and r2["logged"] == 0 and r2["history"] >= 1     # same person+topic within reask_s
    lines = [json.loads(l) for l in open(tmp_path / "rt" / "goalchainer" / "proposals.jsonl")]
    assert all(l["topic"] for l in lines)


# ── budget / errors: swallowed and logged ─────────────────────────

def test_budget_exceeded_is_logged_not_raised(tmp_path, monkeypatch):
    def slow(*a, **k):
        time.sleep(3)
    monkeypatch.setattr(engine, "cached_queries", slow)
    t = time.time()
    run = engine.run_shadow([_it(1, QUESTION)], {"status": "ok"}, _cfg(tmp_path, "", goal_budget_s=0.3), now=NOW)
    assert run["status"] == "budget_exceeded" and time.time() - t < 2.5
    last = json.loads(open(tmp_path / "rt" / "goalchainer" / "runs.jsonl").read().splitlines()[-1])
    assert last["status"] == "budget_exceeded"


def test_exception_is_logged_not_raised(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("synthetic failure")
    monkeypatch.setattr(engine, "cached_queries", boom)
    run = engine.run_shadow([_it(1, QUESTION)], {"status": "ok"}, _cfg(tmp_path, ""), now=NOW)
    assert run["status"] == "error" and "synthetic failure" in run["error"]
    assert not (tmp_path / "rt" / "goalchainer" / "proposals.jsonl").exists()


def test_worker_hook_logs_setup_errors():
    src = open(os.path.join(os.path.dirname(rc.__file__), "workers", "pc_shadow.py")).read()
    hook = src[src.index("Track R: GoalChainer"):src.index("if not a.keep_spec")]
    assert '"hook_error"' in hook and "except Exception" in hook and "raise" not in hook


# ── names come from speaker_map only ───────────────────────────────

def test_addressees_come_from_speaker_map():
    items = [_it(1, QUESTION), _it(2, "Still waiting on Wren for the gadget4 sprocket count."),
             _it(3, "Open question for Zorblax: is the widget8 frame steel?")]       # unmapped name
    r = engine.propose(items, SM, {"autonomous": False}, now=NOW)
    names = set(MAP.values()) | {needs.SELF, None}
    assert r["all_proposed"] and all(p.get("who") in names for p in r["candidates"])
    for p in r["all_proposed"]:
        if p["action"] in ("ClarifyQuestion", "FlagUncertainty", "SummarizeStatus", "RemindPending"):
            assert p["who"] in set(MAP.values()) - {"botty"}
    none = engine.propose(items, {}, {"autonomous": False}, now=NOW)
    assert not [p for p in none["all_proposed"] if p["action"] == "ClarifyQuestion"]


def test_runtime_spec_defaults():
    cfg = rc.resolve(None, environ={})
    assert cfg["goalchainer"] is False and cfg["goal_requests_dir"] == ""
    assert cfg["goal_budget_s"] == 10.0 and cfg["goal_requests_days"] == 14.0 and cfg["goal_requests_max"] == 500
    assert cfg["goal_reask_s"] == 259200.0 and cfg["goal_remind_after_s"] == 86400.0


def test_requests_dir_relative_to_state_dir(tmp_path):
    (tmp_path / "_wmtm_flags.json").write_text(json.dumps({"goal_requests_dir": "chan/completed", "goalchainer": True}))
    cfg = rc.resolve(str(tmp_path), environ={})
    assert cfg["goal_requests_dir"] == str(tmp_path / "chan" / "completed") and cfg["goalchainer"] is True
    assert "unknown_keys" not in cfg["_source"]


def test_no_home_paths_or_ids_in_goal_code():
    base = os.path.join(os.path.dirname(rc.__file__), "goals")
    for f in os.listdir(base):
        if f.endswith(".py"):
            src = open(os.path.join(base, f)).read()
            assert not re.search(r"/(home|Users|root)/|~/", src), f
            assert not re.search(r"\b\d{8,}\b", src.replace("1_800_000_000", "")), f


# ── log-only: nothing reaches the block, the state or the journal ─────

class ListJournal:
    def __init__(self, text=""):
        self.lines = text.splitlines(); self.appended = []

    def read_lines(self):
        return list(self.lines)

    def append(self, note, supersedes=None, about=None):
        self.appended.append(note)
        return {"ok": True}


def _cluster(age_s, note):
    t = time.gmtime(time.time() - age_s)
    cid = "ep-note-" + time.strftime("%Y%m%dT%H%M%SZ", t)
    iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", t)
    return (f";;; BEGIN MemoryCluster {cid}\n(MemoryCluster {cid})\n(SchemaVersion {cid} medium-memory-v1)\n"
            f"(ClusterType {cid} Episode)\n(ClusterSource {cid} iter-experience)\n"
            f"(ClusterOpenedAt {cid} {iso})\n(Contains {cid} ev-{cid})\n(ObservedEvent ev-{cid})\n"
            f"(About {cid} journal)\n(EventNote ev-{cid} \"{note}\")\n;;; END MemoryCluster {cid}\n")


@pytest.mark.parametrize("on", [True, False])
def test_goalchainer_on_never_reaches_block_state_or_journal(tmp_path, monkeypatch, on):
    for k in list(os.environ):
        if k.startswith("WMTM_"):
            monkeypatch.delenv(k, raising=False)
    chan = tmp_path / "chan" / "completed"; chan.mkdir(parents=True)
    flags = dict(SM, pc_shadow=True, goalchainer=on, goal_requests_dir="chan/completed", semparse_feed=False)
    (tmp_path / "_wmtm_flags.json").write_text(json.dumps(flags))
    runs = []

    def fake_launch(spec, cfg=None, out_dir=None, module=None):   # the worker hook, run in-process (no PeTTa)
        runs.append(engine.run_shadow(spec["raw_items"], {"status": "ok", "queries": [], "cycle": spec["cycle"]},
                                      cfg, source=spec.get("source")))
        return 4242
    monkeypatch.setattr(pc_shadow, "launch", fake_launch)
    j = ListJournal(_cluster(2 * D, QUESTION) + _cluster(2 * D - 60, "Still waiting on Wren for the gadget4 sprocket count."))
    m = WMTM(WMTMConfig(state_dir=tmp_path, journal=j, reasoner="off"))
    q = "what is still open about the widget7 gadget and sprocket9?"
    blocks = []
    for _ in range(2):
        m.observe({"user": q})
        blocks.append(m.context_for(q) or "")
    from wmtm import context as ctx
    for _ in range(2):
        blocks.append(ctx.fast_path_automated(str(tmp_path / "_wmtm_state.json"), run_hooks=True, admit=False) or "")
    m.save(); m.close()
    gdir = tmp_path / "_wmtm_shadow" / "goalchainer"
    if not on:
        assert all(r is None for r in runs) and not gdir.exists()
        return
    assert runs and all(r and r["status"] == "ok" for r in runs), runs
    props = [json.loads(l) for l in (gdir / "proposals.jsonl").read_text().splitlines()]
    assert props and any(p["action"] == "ClarifyQuestion" and p["who"] == "quill" for p in props)
    state = (tmp_path / "_wmtm_state.json").read_text()
    for p in props:
        for b in blocks:
            assert p["text"] not in b and p["id"] not in b and p["action"] not in b
        assert p["text"] not in state and p["id"] not in state
    assert any("widget7" in b for b in blocks)        # the note itself is recalled as usual
    assert all("goalchainer" not in b.lower() for b in blocks)
    assert j.appended == []                            # nothing written to the journal
    assert sorted(os.listdir(gdir)) == ["proposals.jsonl", "requests_index.json", "runs.jsonl"]
    assert os.listdir(chan) == []


def test_only_the_worker_imports_the_goal_engine():
    root = os.path.dirname(rc.__file__)
    users = []
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.endswith(".py") and "goals" not in dp.split(os.sep):
                src = open(os.path.join(dp, f)).read()
                if re.search(r'from (wmtm|\.+)\.?goals\b|import wmtm\.goals|"goalchainer"\s*[,)]' , src):
                    users.append(os.path.relpath(os.path.join(dp, f), root))
    assert users == [os.path.join("workers", "pc_shadow.py")], users
    for f in os.listdir(os.path.join(root, "goals")):
        if f.endswith(".py"):
            src = open(os.path.join(root, "goals", f)).read()
            for bad in ("socket", "urllib", "http", "subprocess", "telegram", "journal.", "writeback", "outbox",
                        "send(", "context_for", "_wmtm_state"):
                assert bad not in src.lower(), (f, bad)


# ── real worker (needs the vendored PeTTa runtime; skipped otherwise) ──

_RC = rc.resolve()
HAVE_PC = os.path.isdir(os.path.join(_RC["petta_dir"], "python")) and \
    os.path.isdir(os.path.join(_RC["pettachainer_dir"], "pettachainer"))


@pytest.mark.skipif(not HAVE_PC, reason="vendored PeTTa v1.0.6 / PeTTaChainer not present")
def test_worker_runs_goal_engine_after_canary(tmp_path, monkeypatch):
    import subprocess, sys
    chan = tmp_path / "completed"; chan.mkdir()
    spec = {"cycle": 7, "ts": time.time(), "k": 5, "atoms": [], "goals": [], "source": "cycle",
            "raw_items": [dict(_it(1, QUESTION), origin_ts=time.time() - 2 * D)]}
    sp = tmp_path / "spec.json"; sp.write_text(json.dumps(spec)); out = tmp_path / "shadow" / "shadow.jsonl"
    env = dict(rc.worker_env(_RC), WMTM_GOALCHAINER="1", WMTM_RUNTIME_DIR=str(tmp_path / "rt"),
               WMTM_SPEAKER_MAP=json.dumps(MAP), WMTM_SPEAKER_SELF="botty", WMTM_GOAL_REQUESTS_DIR=str(chan),
               WMTM_SEMPARSE_DIR=str(tmp_path / "sp"))
    subprocess.run([sys.executable, "-m", "wmtm.workers.pc_shadow", "--spec", str(sp), "--out", str(out)],
                   env=env, cwd=rc.DIST_ROOT, timeout=180)
    rec = json.loads(out.read_text().splitlines()[-1])
    run = json.loads((tmp_path / "rt" / "goalchainer" / "runs.jsonl").read_text().splitlines()[-1])
    assert run["shadow_status"] == rec["status"] and run["canary"]["ok"]
    if rec["status"] == "ok":
        assert run["status"] == "ok" and run["logged"] >= 1 and run["s"] < run["budget_s"]
    else:
        assert run["status"] == "shadow_canary_fail"
