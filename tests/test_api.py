"""Unit tests for wmtm.api (no LLM, no network)."""
import json, multiprocessing, subprocess, sys, threading
from pathlib import Path

import pytest

from wmtm.api import WMTM, WMTMConfig, drain_pending_derives, derived_item_id
from wmtm.journal import PettaJournal
from replay import scenarios

REPO = Path(__file__).resolve().parents[1]


class ListJournal:
    """Non-PeTTa journal adapter: only read_lines()/append() are required."""
    def __init__(self, text=""):
        self.lines = text.splitlines()
        self.appended = []

    def read_lines(self):
        return list(self.lines)

    def append(self, note, supersedes=None, about=None):
        self.appended.append(note)
        return {"ok": True}


def _mem(tmp_path, journal_text=scenarios.CANARY_CLUSTER + scenarios.DECOY_CLUSTER, **kw):
    return WMTM(WMTMConfig(state_dir=tmp_path, journal=ListJournal(journal_text), **kw))


def test_context_for_recalls_from_injected_journal(tmp_path):
    m = _mem(tmp_path)
    m.observe({"user": "what is the canary codeword in the kestrel archive?"})
    ctx = m.context_for("what is the canary codeword in the kestrel archive?")
    assert "zebra-quartz-41" in ctx and "tomato" not in ctx
    st = json.loads((tmp_path / "_wmtm_state.json").read_text())
    assert "ep-note-20261015T180000Z" in st["store"]["items"]


def test_negative_control_without_canary(tmp_path):
    m = _mem(tmp_path, journal_text=scenarios.DECOY_CLUSTER)
    ctx = m.context_for("what is the canary codeword in the kestrel archive?")
    assert ctx is None or "zebra-quartz-41" not in ctx


def test_automated_fast_path_does_not_load_engine(tmp_path):
    m = _mem(tmp_path)
    m.context_for("what is the canary codeword in the kestrel archive?")
    m2 = _mem(tmp_path)
    m2.observe({"user": ""})
    ctx = m2.context_for("")
    assert m2.orchestrator is None and "zebra-quartz-41" in ctx


def test_state_dirs_are_isolated(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    _mem(a).context_for("what is the canary codeword in the kestrel archive?")
    assert (a / "_wmtm_state.json").exists() and not (b / "_wmtm_state.json").exists()
    assert _mem(b).context_for("") is None


def test_default_journal_is_petta_under_state_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("JOURNAL_DIR", raising=False)
    m = WMTM(WMTMConfig(state_dir=tmp_path))
    assert isinstance(m.journal, PettaJournal)
    assert m.journal.path == tmp_path / "_journal" / "journal.metta"
    r = m.journal.append('note with "quotes" and \\ backslash', supersedes="old-1", about=["x"])
    assert r["ok"]
    txt = m.journal.path.read_text()
    assert "(Supersedes %s old-1)" % r["id"] in txt and "(About %s x)" % r["id"] in txt


def test_derive_then_admitted(tmp_path):
    m = _mem(tmp_path)
    out = m.derive("a derived belief about kestrel archives and codewords", "src-1")
    assert out.startswith("Registered derived belief " + derived_item_id("a derived belief about kestrel archives and codewords"))
    ctx = m.context_for("kestrel codeword?")
    assert "[derived sti=" in ctx
    assert (tmp_path / "_wmtm_pending_derives.jsonl").read_text() == ""


def test_reasoner_flag(tmp_path):
    for m in ("pettachainer", "off"):                   # Track L: "python" removed
        WMTM(WMTMConfig(state_dir=tmp_path, reasoner=m))
    for bad in ("prolog", "both", "python"):
        with pytest.raises(ValueError):
            WMTM(WMTMConfig(state_dir=tmp_path, reasoner=bad))


def test_decide_with_injected_solver(tmp_path):
    m = _mem(tmp_path)
    seen = {}

    def solve(request, memory_items=None):
        seen["items"] = memory_items
        return {"decided": "a1", "label": "Do it", "status": "ok",
                "decisions": [{"action_id": "a1", "label": "Do it", "status": "permitted", "score": 0.9}]}

    out = m.decide("should I do it?", solve_incident=solve)
    assert out.startswith("Decision: a1 - Do it") and "WMTM evidence: 2 items" in out
    assert {i["id"] for i in seen["items"]} >= {"ep-note-20261015T180000Z"}


def test_cli_context(tmp_path):
    jd = tmp_path / "j"; jd.mkdir()
    (jd / "journal.metta").write_text(scenarios.CANARY_CLUSTER)
    p = subprocess.run([sys.executable, "-m", "wmtm", "context", "--state-dir", str(tmp_path), "--journal-dir", str(jd)],
                       input=json.dumps({"user": "kestrel archive canary codeword?"}), capture_output=True, text=True, cwd=REPO)
    assert p.returncode == 0 and "zebra-quartz-41" in p.stdout


# ── lock semantics (ported from Iter's test_wmtm_derive_lock / drain_lock) ──

def _proc_worker(state_dir, i):
    m = WMTM(WMTMConfig(state_dir=state_dir, journal=ListJournal()))
    for k in range(50):
        m.derive(f"p{i}-{k} " + "x" * 2000)


def test_derive_threads_append_exactly(tmp_path):
    m = _mem(tmp_path)
    ts = [threading.Thread(target=lambda i=i: [m.derive(f"t{i}-{k}") for k in range(50)]) for i in range(4)]
    [t.start() for t in ts]; [t.join() for t in ts]
    lines = [json.loads(l) for l in (tmp_path / "_wmtm_pending_derives.jsonl").read_text().splitlines() if l.strip()]
    assert len(lines) == 200 and len({l["note"] for l in lines}) == 200


def test_derive_processes_append_exactly(tmp_path):
    ctx = multiprocessing.get_context("fork")
    ps = [ctx.Process(target=_proc_worker, args=(str(tmp_path), i)) for i in range(4)]
    [x.start() for x in ps]; [x.join(60) for x in ps]
    assert all(x.exitcode == 0 for x in ps)
    lines = [json.loads(l) for l in (tmp_path / "_wmtm_pending_derives.jsonl").read_text().splitlines() if l.strip()]
    assert len(lines) == 200 and len({l["note"] for l in lines}) == 200


def test_drain_concurrent_with_writers_loses_nothing(tmp_path):
    p = tmp_path / "_wmtm_pending_derives.jsonl"; p.write_text("")
    mp = multiprocessing.get_context("fork")
    ws = [mp.Process(target=_proc_worker, args=(str(tmp_path), i)) for i in range(4)]
    [w.start() for w in ws]
    seen = []
    while any(w.is_alive() for w in ws):
        seen += drain_pending_derives(p)
    [w.join(60) for w in ws]
    assert all(w.exitcode == 0 for w in ws)
    seen += drain_pending_derives(p)
    notes = [json.loads(l)["note"] for l in seen if l.strip()]
    assert len(notes) == 200 and len(set(notes)) == 200
    assert p.read_text() == ""


def test_engine_init_once_under_threads(tmp_path):
    m = _mem(tmp_path)
    orchs = []
    def go():
        m._ensure_store_ready(); orchs.append(m.orchestrator)
    ts = [threading.Thread(target=go) for _ in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len({id(o) for o in orchs}) == 1
