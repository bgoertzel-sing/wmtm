"""F2 (t-2026-11-06-wmtm-f2-context): acceptance conditions 5, 7, 10 of the WMTM worked-examples review, and the
stemmer.  Every example is synthetic (Rex, dogs, vets, service-1).  Each test has a negative control: undo the fix
and it fails for the reason in its docstring (reports/t-2026-11-06-wmtm-f2-context/controls.py runs them)."""
import os
import re
import sys
import time
import types

import pytest

from wmtm import context as ctx
from wmtm.api import WMTM, WMTMConfig
from wmtm.goals import engine, needs, v2
from wmtm.store import WMTMStore

NOW_WALL = time.time()


# ── helpers ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _cluster(i, note, age_s):
    ts = time.gmtime(NOW_WALL - age_s)
    cid = "ep-note-" + time.strftime("%Y%m%dT%H%M%SZ", ts)
    iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", ts)
    return cid, (";;; BEGIN MemoryCluster %s\n(MemoryCluster %s)\n(SchemaVersion %s medium-memory-v1)\n"
                 "(ClusterType %s Episode)\n(ClusterSource %s iter-experience)\n(ClusterOpenedAt %s %s)\n"
                 "(Contains %s ev-%s)\n(ObservedEvent ev-%s)\n(About %s journal)\n(EventNote ev-%s \"%s\")\n"
                 ";;; END MemoryCluster %s\n") % (cid, cid, cid, cid, cid, cid, iso, cid, cid, cid, cid, cid, note, cid)


class _Journal:
    def __init__(self, text):
        self.lines = text.splitlines()

    def read_lines(self):
        return list(self.lines)

    def append(self, note, supersedes=None, about=None):
        return {"ok": True}


def _recalled_after_turn(tmp_path, notes, request):
    """notes -> {cluster id: note}; runs one real user turn through WMTM.context_for (the production recall path)
    and returns the notes that are in working memory afterwards."""
    ids, text = {}, ""
    for i, n in enumerate(notes):
        cid, block = _cluster(i, n, 3600 + 60 * (len(notes) - i))      # oldest first, one minute apart
        ids[cid] = n
        text += block
    m = WMTM(WMTMConfig(state_dir=tmp_path, journal=_Journal(text), reasoner="off"))
    m.context_for(request)
    store = m._orchestrator.store
    return [ids[i] for i in ids if i in store], ids


REX = ["rex is a dog", "rex is a mammal", "rex is an animal", "rex is a pet", "mammal is a vertebrate"]


# ── section 5: notes are not dropped or merged for sharing words ─────────────────────────────────────────────────
def test_s5_five_compatible_rex_notes_are_all_admitted(tmp_path):
    """Condition 5: all five notes are admitted; ranking decides which are shown.
    Control (0.6 word-overlap test restored): "rex is a dog" / "rex is a mammal" are skipped as duplicate topics."""
    got, _ = _recalled_after_turn(tmp_path, REX, "what do we know about rex the dog, mammal, animal, pet, vertebrate?")
    assert sorted(got) == sorted(REX)


def test_s5_two_cpu_readings_are_two_observations(tmp_path):
    """Condition 5: the two readings are two observations (the later one is the current value, by age).
    Control: the 55% reading is skipped as a duplicate of the 92% one."""
    notes = ["service-1 CPU reads 92% after the restart", "service-1 CPU reads 55% after the restart"]
    got, ids = _recalled_after_turn(tmp_path, notes, "what does service-1 CPU read after the restart?")
    assert sorted(got) == sorted(notes)
    newest = max(ids)                                   # cluster ids are timestamps
    assert ids[newest] == notes[1]


def test_s5_same_proposition_is_still_merged():
    """The merge that stays: the same proposition (case / spacing / final stop), or the same parse."""
    assert ctx.is_duplicate_topic("Rex is a dog.", ["rex  is a dog"])
    assert not ctx.is_duplicate_topic("rex is a mammal", ["rex is a dog"])
    parse = {"rex is a dog": ["(Member rex dog)"], "rex's a dog": ["(Member  rex dog)"],
             "rex is a mammal": ["(Member rex mammal)"]}.get
    assert ctx.same_proposition("rex is a dog", "rex's a dog", parse)
    assert not ctx.same_proposition("rex is a dog", "rex is a mammal", parse)
    assert not ctx.same_proposition("rex is a dog", "unparsed dog note about rex", parse)


def test_s5_goal_engine_keeps_questions_to_different_people_apart():
    """Condition 5 (goal engine): open questions addressed to different people stay two signals.
    Control: extract() merges them into one signal (cluster_match on shared words, person ignored)."""
    now = 1_800_000_000.0
    items = [{"id": "syn-1", "content": "Open question for Quill: should the vet clinic dogs get the rabies booster?",
              "sti": 1.0, "source_type": "recalled", "origin_ts": now - 2 * 86400},
             {"id": "syn-2", "content": "Open question for Wren: should the vet clinic dogs get the rabies booster?",
              "sti": 1.0, "source_type": "recalled", "origin_ts": now - 86400}]
    sigs = needs.extract(items, now, people=needs.people_patterns({"1": "quill", "2": "wren"}), self_name="botty")
    qs = [s for s in sigs if s["kind"] == "question"]
    assert sorted(s["who"] for s in qs) == ["quill", "wren"]


# ── section 7: evidence apart from attention ─────────────────────────────────────────────────────────────────────
def _belief_store():
    store = WMTMStore(capacity=20)
    store.admit("ep-a", "rex is a dog", source_type="recalled", initial_sti=1.0)
    store.admit("ep-b", "dogs are mammals", source_type="recalled", initial_sti=1.0)
    store.admit("ep-z", "the tomato seedlings were moved to the greenhouse", source_type="recalled", initial_sti=1.0)
    store.admit("dv-rex-mammal", "rex is a mammal", source_type="derived", derived_from=["ep-a", "ep-b"],
                initial_sti=1.0, provenance={"reasoner": "pettachainer", "stv": [0.9, 0.7]})
    return store


def _attention(store, stis):
    for iid, s in stis.items():
        store.get(iid).attention.sti = float(s)


REL = {"cycle": 1, "scores": {"ep-a": 1.0, "ep-b": 0.6}, "terms": {"rex": 1.0, "mammal": 0.8}, "smax": 1.0}
STATE_1 = {"ep-a": 1.0, "ep-b": 2.0, "ep-z": 50.0, "dv-rex-mammal": 40.0}
STATE_2 = {"ep-a": 40.0, "ep-b": 30.0, "ep-z": 0.1, "dv-rex-mammal": 0.5}


def _block(store, cfg):
    text, shown = ctx.format_context(store, 3, cfg, REL)
    lines = text.splitlines()
    return lines[0], lines[1:], shown


@pytest.mark.parametrize("rank", [True, False])
def test_s7_belief_is_the_same_at_two_attention_states(rank):
    """Condition 7: each derived line shows its truth value and source note ids; attention only orders the lines,
    so the believed lines are the same at two attention states.
    Control (attention-only lines, attention-scored floor): lines carry sti=/util=, which differ between the
    states, and the irrelevant high-STI note is shown in one state only."""
    cfg = {"context_rank": rank}
    store = _belief_store()
    _attention(store, STATE_1)
    h1, l1, _ = _block(store, cfg)
    _attention(store, STATE_2)
    h2, l2, _ = _block(store, cfg)
    assert h1 == h2
    assert sorted(l1) == sorted(l2)
    derived = [l for l in l1 if "rex is a mammal" in l]
    assert len(derived) == 1 and "tv=0.90,0.70" in derived[0] and "from=ep-a,ep-b" in derived[0]
    assert all("sti=" not in l and "util=" not in l for l in l1)
    assert any("from=ep-a" in l and l.endswith("rex is a dog") for l in l1)


def test_s7_attention_still_orders_the_lines():
    """Attention keeps its job: the order of equally relevant lines follows STI."""
    store = _belief_store()
    _attention(store, STATE_1)
    _, l1, _ = _block(store, {})
    _attention(store, STATE_2)
    _, l2, _ = _block(store, {})
    assert l1 != l2


def test_s7_engine_tv_is_shown_unchanged_and_missing_tv_is_said():
    store = WMTMStore(capacity=5)
    store.admit("dv-1", "rex is an animal", source_type="derived", derived_from=["ep-a"], initial_sti=1.0,
                provenance={"stv": [0.123456, 0.654321]})
    store.admit("dv-2", "rex is a pet", source_type="derived", derived_from=[], initial_sti=1.0)
    text, _ = ctx.format_context(store, 1, {"context_rank": True}, None)
    assert "tv=0.12,0.65 from=ep-a" in text and "tv=none from=none" in text


# ── section 10: GoalChainer reads everything WMTM sends; ties go to a human ──────────────────────────────────────
_STV = re.compile(r"\(Acceptable\s+[A-Za-z0-9_:-]+\)\s+\(STV\s+[0-9.eE+-]+\s+[0-9.eE+-]+\)")
_EC = re.compile(r"\(EvidencePacket\s+\(Acceptable\s+[A-Za-z0-9_:-]+\)\s+\(EC\s+[0-9.eE+-]+\s+[0-9.eE+-]+\)")


def _goalchainer_reads(items):
    """How many of the items GoalChainer v1 reads: its own parse_memory_evidence when WMTM_TEST_GC1_SRC points at
    OmegaClaw-GoalChainer/src, else a copy of its acceptance rule at 10627ce (slot + atom shape)."""
    src = os.environ.get("WMTM_TEST_GC1_SRC", "")
    if src and os.path.isdir(src):
        sys.path.insert(0, src)
        try:
            from goal_chainer.heuristic_beliefs import parse_memory_evidence
            return len(parse_memory_evidence(list(items)))
        finally:
            sys.path.remove(src)
    n = 0
    for it in items:
        a, slot = str(it.get("atom", "")), it.get("goalchainer_slot")
        n += bool((slot == "acceptability-belief-evidence" and _STV.search(a))
                  or (slot == "contextual-appraisal-evidence" and _EC.search(a)))
    return n


def test_s10_decide_sends_only_what_goalchainer_reads(tmp_path):
    """Condition 10 (v1 decide): whatever is sent is read, and the reply never claims more items than were read.
    Control (v1 path restored): 3 notes are sent as {id, content, sti}, GoalChainer reads 0, the reply says
    "3 items fed"."""
    text = "".join(_cluster(i, n, 3600 + i * 60)[1] for i, n in enumerate(REX[:3]))
    m = WMTM(WMTMConfig(state_dir=tmp_path, journal=_Journal(text), reasoner="off"))
    seen = {"items": None}

    def solve(request, memory_items=None):
        seen["items"] = memory_items
        return {"decided": "a1", "label": "x", "status": "ok", "decisions": []}

    out = m.decide("should rex see the vet?", solve_incident=solve)
    sent = list(seen["items"] or ())
    read = _goalchainer_reads(sent)
    assert len(sent) == read
    claim = re.search(r"(\d+) items fed", out)
    assert claim is None or int(claim.group(1)) == read


def test_s10_orchestrator_phase_sends_only_what_goalchainer_reads(monkeypatch):
    """Condition 10 (orchestrator use_goalchainer phase, same v1 feed).
    Control: run_goalchainer_over_wmtm sends the active set ({id, content, sti}); GoalChainer reads 0 of them."""
    seen = {"items": None}
    mod = types.ModuleType("goal_chainer.pipeline")

    def solve(request, memory_items=None):
        seen["items"] = memory_items
        return {"decisions": []}
    mod.solve_incident = solve
    monkeypatch.setitem(sys.modules, "goal_chainer", types.ModuleType("goal_chainer"))
    monkeypatch.setitem(sys.modules, "goal_chainer.pipeline", mod)
    from wmtm.goalchainer_bridge import run_goalchainer_over_wmtm
    store = WMTMStore(capacity=10)
    for i, n in enumerate(REX):
        store.admit("ep-%d" % i, n)
    run_goalchainer_over_wmtm(store, "should rex see the vet?")
    sent = list(seen["items"] or ())
    assert len(sent) == _goalchainer_reads(sent)


NOW = 1_800_000_000.0
MAP = {"9001": "quill", "9002": "wren", "9999": "botty"}
TIE_A = "Open question for Quill: should the widget7 gadget be renamed to sprocket9?"
TIE_B = "Open question for Wren: should the gizmo4 gadget be renamed to cog8?"


def _syn(i, text):
    return {"id": "syn-%d" % i, "content": text, "sti": 1.0, "source_type": "recalled", "origin_ts": NOW - 2 * 86400.0}


ORDERS = ([_syn(1, TIE_A), _syn(2, TIE_B)], [_syn(2, TIE_B), _syn(1, TIE_A)])


def test_s10_tied_candidates_declare_equal_expectations_in_both_orders():
    """Condition 10 (v2 ties, engine-free half): two equally urgent questions to different people declare equal
    expected changes, whatever the list order.  Control (TIE_STEP restored): the first in the list is declared
    slightly larger, so list order decides."""
    for items in ORDERS:
        p = engine.prepare_v2(items, {"speaker_map": MAP, "speaker_self": "botty"}, {"autonomous": False}, now=NOW)
        cands = list(p["amap"].values())
        ch = v2.expectations(cands, p["est"], p["st"], NOW)
        ask = {c["who"]: x for c, x in zip(cands, ch) if c["action"] == "ClarifyQuestion"}
        assert set(ask) == {"quill", "wren"} and ask["quill"] == ask["wren"]


GC2 = os.environ.get("WMTM_TEST_GC2_PYTHON", "")


@pytest.mark.skipif(not (GC2 and os.path.exists(GC2)), reason="WMTM_TEST_GC2_PYTHON not set")
def test_s10_real_v2_escalates_a_tie_in_both_orders():
    """Condition 10 (v2 ties, real GoalChainer v2): the tie escalates to a human in both orders; nothing is proposed.
    Control (TIE_STEP restored): v2 proposes the ClarifyQuestion that comes first in the list."""
    cfg = {"goal_v2_python": GC2, "goal_v2_runner": "", "speaker_map": MAP, "speaker_self": "botty"}
    for items in ORDERS:
        h = engine.propose_v2(items, cfg, {"autonomous": False}, now=NOW)["human"]
        assert h["proposals"] == []
        d = h["decisions"][0]
        assert d["disposition"] == "escalate", d
        assert "not decisive" in d["escalation"]["reasons"][0]
        assert len(d["escalation"]["contested"]) == 2


# ── stemmer ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_stemmer_dogs_matches_dog():
    """Stemmer: "dogs" and "dog" match.  Control (old stemmer): "dogs" is kept whole (a 4-letter word was never
    stripped), so the plural never matches the singular."""
    assert needs.stem("dogs") == needs.stem("dog") == "dog"
    assert needs.stem("vets") == "vet"
    assert needs.norm({"dogs", "vets"}) == needs.norm({"dog", "vet"})
    assert needs.cluster_match({"dogs", "vets"}, {"dog", "vet"})
    for w in ("glass", "status", "this", "bus"):            # not plurals: unchanged by the new rule
        assert needs.stem(w) == (w[:-1] if len(w) >= 5 and w.endswith("s") else w)
