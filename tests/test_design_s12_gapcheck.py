"""t-2026-11-10-wmtm-design-gap-check: acceptance tests from Ben's design doc (docs/wmtm_design_doc.txt, Sep 5).

One test per design requirement (s12.2 integration, s12.3 simulation, s12.4 properties, plus the s3/s7/s8 rules
those tests rely on).  Synthetic data only.  No production code was changed for these tests.

Known gaps are marked xfail(strict=True, reason="GAP-n ..."): they fail today, and the suite turns red (XPASS)
as soon as main closes the gap, so the marker must then be removed.  GAP numbers match the ranked gap list in
the task report (REPORT.md, t-2026-11-10-wmtm-design-gap-check).

Reasoner note: these tests drive the memory lifecycle with synthetic reasoner candidates (InferenceCandidate, the
object PeTTaChainer admission produces).  Inference on the real engine is covered by
tests/test_design_s12_engine.py (PeTTaChainer b6aacc68, PeTTa 3681b9b).
"""
import json
import os
import random

import pytest

from wmtm.candidate import InferenceCandidate
from wmtm.orchestrator import WMTMOrchestrator
from wmtm.recall_bridge import RecallBridge, parse_journal
from wmtm.store import WMTMStore

PC = {"reasoner": "pettachainer"}          # provenance of a PeTTaChainer-admitted conclusion


@pytest.fixture(autouse=True)
def _isolated_flags(monkeypatch, tmp_path):
    """Default flags only: no flags file, no WMTM_* overrides from the caller's environment."""
    for k in list(os.environ):
        if k.startswith("WMTM_") and k not in ("WMTM_PC_PETTA", "WMTM_PC_VENDOR", "WMTM_SWIPL_BIN",
                                               "WMTM_GAPCHECK_SIM_OUT"):
            monkeypatch.delenv(k, raising=False)
    monkeypatch.chdir(tmp_path)


def _cand(text, srcs, sti=1.0, prov=PC):
    return InferenceCandidate(content=text, confidence=0.9, derived_from=list(srcs),
                              inference_type="pc_deduction", initial_sti=sti, provenance=dict(prov) if prov else None)


def _orch(capacity=200):
    return WMTMOrchestrator(WMTMStore(capacity=capacity))


def _journal(clusters):
    """clusters: [(id, about, note, extra_lines)] -> journal lines in the petta-memory format recall_bridge parses."""
    out = []
    for cid, about, note, extra in clusters:
        out.append(f";;; BEGIN MemoryCluster {cid}")
        out.append(f"(MemoryCluster {cid})")
        out.append(f"(About {cid} {about})")
        out.append(f'(EventNote ev-{cid} "{note}")')
        out.extend(extra)
        out.append(f";;; END MemoryCluster {cid}")
    return out


# ------------------------------------------------------------------------------------------- s12.4 properties

def test_s12_4_capacity_never_exceeded_random_ops():
    """s12.4: WMTM never exceeds capacity, under random admits (all source types), ticks and forgetting."""
    rnd = random.Random(1209)
    orch = _orch(capacity=20)
    for step in range(600):
        op = rnd.random()
        if op < 0.6:
            st = rnd.choice(["recalled", "derived", "asserted", "user"])
            orch.store.admit(f"i{rnd.randrange(80)}", f"text {rnd.randrange(80)}", source_type=st,
                             initial_sti=rnd.uniform(0, 3))
        elif op < 0.8:
            orch._admit_derived([_cand(f"d {rnd.randrange(50)}", [f"i{rnd.randrange(80)}"], rnd.uniform(0, 3))])
        else:
            orch.forget_phase()
        assert len(orch.store) <= orch.store.capacity, step


def test_s12_4_every_evicted_derived_item_is_forgotten_or_promoted():
    """s12.4 / s7.2: no derived item leaves WMTM without a forgetting-log record or an LTM promotion."""
    orch = _orch(capacity=8)
    written = []
    seen_derived = set()
    for c in range(60):
        orch.store.admit(f"r{c}", f"recalled note {c}", initial_sti=1.0)
        for j in range(2):
            it = orch._admit_derived([_cand(f"derived {c}-{j}", [f"r{c}"])])
            seen_derived.update(i.id for i in it)
        orch.cycle(append_fn=lambda s: written.append(s))
    alive = {i.id for i in orch.store.get_active_set()}
    logged = {r.item_id for r in orch.forget_log.get_records()}
    promoted = {i for i in seen_derived if orch.writeback.has_been_written(i)}
    lost = seen_derived - alive - logged - promoted
    assert seen_derived and not lost


def test_s12_4_forgetting_log_blocks_identical_rederivation():
    """s12.4 / s7.3: an identical derivation (same conclusion, same sources) is not re-admitted after it was forgotten."""
    orch = _orch()
    orch.store.admit("s0", "cats are mammals", initial_sti=50.0)
    orch.store.admit("s1", "mammals are animals", initial_sti=50.0)
    [d] = orch._admit_derived([_cand("cats are animals", ["s0", "s1"], sti=1.0)])
    for _ in range(40):                     # never used: decays and/or ages out
        orch.forget_phase()
        if d.id not in orch.store:
            break
    assert d.id not in orch.store
    assert orch.forget_log.is_forgotten("cats are animals", ["s0", "s1"])
    for _ in range(5):                      # the reasoner offers it again on later cycles
        assert orch._admit_derived([_cand("cats are animals", ["s0", "s1"], sti=1.0)]) == []
        orch.forget_phase()


def test_s12_4_forgetting_log_survives_snapshot():
    """s7.3 with F01b persistence: the derivation key survives snapshot_state/restore_state."""
    orch = _orch()
    orch.store.admit("s0", "a", initial_sti=50.0)
    [d] = orch._admit_derived([_cand("x is y", ["s0"])])
    orch.forget_log.record(orch.store.evict(d.id), 0)
    snap = json.loads(json.dumps(orch.snapshot_state()))
    o2 = _orch()
    o2.restore_state(snap)
    assert o2.forget_log.is_forgotten("x is y", ["s0"])
    assert o2._admit_derived([_cand("x is y", ["s0"])]) == []


def test_s12_4_recall_never_admits_superseded():
    """s12.4 / s8.2: a superseded cluster is never a recall candidate, even when it matches best."""
    lines = _journal([
        ("c-old", "zebra", "zebra stripes are white on black", []),
        ("c-new", "zebra", "zebra stripes are black on white", ["(Supersedes c-new c-old)"]),
    ])
    rb = RecallBridge(parse_journal(lines))
    ids = [c.cluster_id for c in rb.recall("zebra stripes white on black", WMTMStore(), top_k=10)]
    assert "c-new" in ids and "c-old" not in ids


# ------------------------------------------------------------------------------------- s3.3 / s8 recall rules

def test_s3_3_spreading_activation_recalls_linked_cluster_without_keywords():
    """s3.3 'key insight' / s13.5: graph neighbours of active items are recalled even with no shared keyword."""
    lines = _journal([
        ("c-a", "zebra", "zebra herd seen at the river", []),
        ("c-b", "quantum", "photon counts doubled overnight", ["(EvidenceFor c-b c-a)"]),
    ])
    rb = RecallBridge(parse_journal(lines))
    st = WMTMStore()
    st.admit("c-a", "zebra herd seen at the river", initial_sti=5.0)
    ids = [c.cluster_id for c in rb.recall("zebra herd", st, top_k=10)]
    assert "c-b" in ids


def test_s8_1_spreading_activation_follows_promotes_from():
    """s8.1b: spreading activation follows PromotesFrom edges (depth 1)."""
    lines = _journal([
        ("c-a", "alpha", "alpha note", []),
        ("c-p", "beta", "beta summary", ["(PromotesFrom c-p c-a)"]),
    ])
    rb = RecallBridge(parse_journal(lines))
    assert "c-p" in rb.spreading_activation(["c-a"], depth=1)


def test_s8_1_spreading_activation_follows_evidence_for_with_decay():
    """s8.1b: EvidenceFor edges are followed (both directions in main) with per-hop decay."""
    lines = _journal([
        ("c-a", "alpha", "alpha note", []),
        ("c-b", "beta", "beta note", ["(EvidenceFor c-b c-a)"]),
        ("c-c", "gamma", "gamma note", ["(EvidenceFor c-c c-b)"]),
    ])
    rb = RecallBridge(parse_journal(lines))
    s = rb.spreading_activation(["c-a"], depth=2, decay=0.7)
    assert s["c-a"] > s["c-b"] > s["c-c"] > 0


# ----------------------------------------------------------------------------------------- s7.1 eviction rules

@pytest.mark.xfail(strict=True, reason="GAP-3 forgetting: capacity eviction (store._evict_lowest_sti) uses STI only; the "
                   "design's composite STI*0.4+utility*0.4+LTI*0.2 with the 1.5x derived penalty is not implemented")
def test_s7_1c_capacity_eviction_prefers_derived_via_composite_penalty():
    """s7.1c: recalled STI 1.0 (composite 0.40) vs derived STI 1.2 (0.48/1.5 = 0.32): the derived item goes first."""
    st = WMTMStore(capacity=2)
    st.admit("rec", "recalled fact", source_type="recalled", initial_sti=1.0)
    st.admit("der", "derived fact", source_type="derived", derived_from=["rec"], initial_sti=1.2)
    st.admit("new", "new recalled fact", source_type="recalled", initial_sti=3.0)
    assert "rec" in st and "der" not in st


def test_s7_1a_unused_items_decay_and_are_evicted():
    """s7.1a: an unused item's STI decays every cycle and the item is evicted once under the threshold."""
    orch = _orch()
    orch.store.admit("r", "idle note", initial_sti=1.0)
    stis = []
    for _ in range(60):
        if "r" not in orch.store:
            break
        stis.append(orch.store.get("r").attention.sti)
        orch.forget_phase()
    assert "r" not in orch.store
    assert all(a > b for a, b in zip(stis, stis[1:]))


def test_s7_1_derived_items_forgotten_no_later_than_recalled():
    """s7.1 / s13.3: under identical attention and no use, a derived item is evicted no later than a recalled one."""
    orch = _orch()
    orch.store.admit("r", "recalled", source_type="recalled", initial_sti=1.0)
    orch.store.admit("d", "derived", source_type="derived", derived_from=["r"], initial_sti=1.0)
    gone = {}
    for c in range(80):
        orch.forget_phase()
        for k in ("r", "d"):
            if k not in orch.store and k not in gone:
                gone[k] = c
    assert gone["d"] <= gone["r"]


@pytest.mark.xfail(strict=True, reason="GAP-6 forgetting: no contradiction-resolution trigger (s7.1d); a derived belief "
                   "that negates a higher-confidence recalled belief is kept")
def test_s7_1d_contradicting_lower_confidence_derived_belief_is_evicted():
    orch = _orch()
    orch.store.admit("r", "the bridge is open", initial_sti=5.0)
    orch._admit_derived([InferenceCandidate(content="unlikely: the bridge is open", confidence=0.4, derived_from=["x"],
                                            inference_type="pc_deduction", initial_sti=5.0, provenance=dict(PC))])
    orch.forget_phase()
    assert not any(i.source_type == "derived" for i in orch.store.get_active_set())


# -------------------------------------------------------------------------------------- s12.2 integration tests

def test_s12_2_full_cycle_recall_infer_use_decay_forget():
    """s12.2: one cycle recall -> infer -> use -> decay -> forget, with the derived item linked to its parents."""
    orch = _orch(capacity=50)
    recall = lambda: [("s0", "cats are mammals", 5.0), ("s1", "mammals are animals", 5.0), ("s2", "idle", 0.011)]
    orch.cycle(recall_fn=recall)
    assert "s0" in orch.store and "s1" in orch.store and "s2" not in orch.store   # decayed under the floor: forgotten
    assert orch.forget_log.is_id_forgotten("s2")
    [d] = orch._admit_derived([_cand("cats are animals", ["s0", "s1"], sti=2.0)])
    assert d.source_type == "derived" and d.derived_from == ["s0", "s1"]
    assert orch.utility.get_record("s0").inferred_from_count == 1                 # parents credited (s3.5)
    sti0 = d.attention.sti
    orch.utility.record_use(d.id, orch._cycle)                                    # USE
    orch.cycle()                                                                  # DECAY + reinforce + FORGET
    it = orch.store.get(d.id)
    assert it is not None and it.utility > 0
    assert it.attention.sti > sti0 * it.attention.sti_decay                       # reinforced, not only decayed


def test_s12_2_multicycle_forgetting_log_prevents_rederivation():
    """s12.2: over many cycles, a reasoner that keeps offering the same never-used conclusion gets it admitted once."""
    orch = _orch(capacity=50)
    admitted = 0
    for c in range(80):
        orch.store.admit("s0", "cats are mammals", initial_sti=5.0)
        orch.store.admit("s1", "mammals are animals", initial_sti=5.0)
        orch.utility.record_use("s0", orch._cycle); orch.utility.record_use("s1", orch._cycle)
        admitted += len(orch._admit_derived([_cand("cats are animals", ["s0", "s1"], sti=1.0)]))
        orch.cycle()
    assert admitted == 1


def _promotion_run(cycles=25):
    orch = _orch(capacity=50)
    written = []
    orch.store.admit("s0", "cats are mammals", initial_sti=5.0)
    orch.store.admit("s1", "mammals are animals", initial_sti=5.0)
    [d] = orch._admit_derived([_cand("cats are animals", ["s0", "s1"], sti=2.0)])
    for _ in range(cycles):
        for iid in (d.id, "s0", "s1"):
            orch.utility.record_use(iid, orch._cycle)
        orch.cycle(append_fn=lambda s: written.append(s))
    return orch, d, written


@pytest.mark.xfail(strict=True, reason="GAP-4 promotion: with default flags a durable PeTTaChainer conclusion is never "
                   "promoted to LTM (reasoner_writeback defaults to False, runtime_config.py:109; filter at "
                   "orchestrator.py:341-343)")
def test_s12_2_durable_derived_belief_promoted_to_ltm_default_flags():
    orch, d, written = _promotion_run()
    assert any(f"wmtm-derived-{d.id}" in w for w in written)


def test_s12_2_durable_derived_belief_promoted_with_reasoner_writeback(monkeypatch):
    """s12.2 / s6.3: with reasoner_writeback on, the used derived belief is written as a DerivedBelief cluster
    carrying DerivedFrom metadata, exactly once."""
    monkeypatch.setenv("WMTM_REASONER_WRITEBACK", "1")
    orch, d, written = _promotion_run()
    mine = [w for w in written if f"wmtm-derived-{d.id}" in w]
    assert len(mine) == 1
    assert "(ClusterType wmtm-derived-%s DerivedBelief)" % d.id in mine[0]
    assert "(DerivedFrom wmtm-derived-%s s0)" % d.id in mine[0] and "(DerivedFrom wmtm-derived-%s s1)" % d.id in mine[0]


def test_s12_2_recalled_item_enrichment_written_back():
    """s12.2 writeback: a recalled item used for >= 30 cycles is written back (EnrichmentNote) once."""
    orch = _orch(capacity=50)
    written = []
    for _ in range(35):
        orch.utility.record_use("s0", orch._cycle)
        orch.cycle(recall_fn=lambda: [("s0", "cats are mammals", 2.0)], append_fn=lambda s: written.append(s))
    mine = [w for w in written if "wmtm-enrich-s0" in w]
    assert len(mine) == 1 and "EnrichmentNote" in mine[0]


@pytest.mark.xfail(strict=True, reason="GAP-7 writeback: enrichment writes a copy of the note (EnrichmentNote), not the "
                   "new EvidenceFor links discovered while the item was active (s4 step 6, s5.2)")
def test_s4_6_enrichment_carries_new_evidence_links():
    orch = _orch(capacity=50)
    written = []
    for _ in range(35):
        orch.utility.record_use("s0", orch._cycle); orch.utility.record_use("s1", orch._cycle)
        orch.cycle(recall_fn=lambda: [("s0", "cats are mammals", 2.0), ("s1", "mammals are animals", 2.0)],
                   append_fn=lambda s: written.append(s))
        orch._admit_derived([_cand("cats are animals", ["s0", "s1"], sti=2.0)])
    assert any("EvidenceFor" in w for w in written if "wmtm-enrich-s0" in w)


@pytest.mark.xfail(strict=True, reason="GAP-8 forgetting: a forgotten derived belief is not recorded in LTM as "
                   "(WMTMDerivedForgotten ...) (s6.3); the forgetting log lives only in the WMTM snapshot")
def test_s6_3_forgotten_derived_belief_noted_in_ltm():
    orch = _orch(capacity=50)
    written = []
    orch.store.admit("s0", "a", initial_sti=50.0)
    orch._admit_derived([_cand("x is y", ["s0"], sti=0.5)])
    for _ in range(40):
        orch.cycle(append_fn=lambda s: written.append(s))
    assert any("WMTMDerivedForgotten" in w for w in written)


# ---------------------------------------------------------------------------------- s3.5 / s13.3 useful vs trivial

@pytest.mark.xfail(strict=True, reason="GAP-5 usefulness: nothing in admission, utility or eviction distinguishes a "
                   "one-hop restatement ('an X_Y is a Y') from a non-trivial conclusion; both are treated identically")
def test_s3_5_trivial_restatement_ranked_below_nontrivial_conclusion():
    orch = _orch(capacity=50)
    orch.store.admit("n1", "the apple_tree in the yard", initial_sti=5.0)
    orch.store.admit("n2", "cats are mammals", initial_sti=5.0)
    orch.store.admit("n3", "mammals are animals", initial_sti=5.0)
    [triv] = orch._admit_derived([_cand("an apple_tree is a tree", ["n1"], sti=1.0)])
    [real] = orch._admit_derived([_cand("cats are animals", ["n2", "n3"], sti=1.0)])
    for _ in range(3):
        orch.forget_phase()
    t, r = orch.store.get(triv.id), orch.store.get(real.id)
    assert t is None or (r is not None and (t.attention.total, t.utility) < (r.attention.total, r.utility))


# ------------------------------------------------------------------------------------------- s12.3 simulation

def _simulate(cycles=100, capacity=20, seed=123):
    """100 cycles of synthetic task contexts.  60 LTM notes: 8 useful (used whenever active; each task names 3 of
    them), 52 background (each task names 4 at random; never used).  The synthetic reasoner offers 2 conclusions per
    cycle from pairs of active recalled notes; conclusions from two useful notes are used, others are not."""
    rnd = random.Random(seed)
    useful = [f"u{i}" for i in range(8)]
    background = [f"b{i}" for i in range(52)]
    text = {k: f"note {k}" for k in useful + background}
    orch = _orch(capacity=capacity)
    useful_derived = set()
    m = {"occupancy": [], "evicted": [], "inferred": [], "useful_resident": [], "derived_resident": []}
    lifetimes = {"useful": [], "background": []}
    admitted_at = {}
    for c in range(cycles):
        task = rnd.sample(useful, 3) + rnd.sample(background, 4)
        recall = lambda: [(k, text[k], 1.5) for k in task]
        before = {i.id for i in orch.store.get_active_set()}
        log0 = len(orch.forget_log)
        for k in task:
            admitted_at.setdefault(k, c)
        active = [i.id for i in orch.store.get_active_set() if i.source_type == "recalled"]
        cands = []
        for _ in range(2):
            if len(active) >= 2:
                a, b = sorted(rnd.sample(active, 2))
                cands.append(_cand(f"concl {a} {b}", [a, b], sti=1.0))
        got = orch._admit_derived(cands)
        for it in got:
            if all(p.startswith("u") for p in it.derived_from):
                useful_derived.add(it.id)
        for i in orch.store.get_active_set():                               # USE
            if i.id in useful or i.id in useful_derived:
                orch.utility.record_use(i.id, orch._cycle)
        r = orch.cycle(recall_fn=recall)
        after = {i.id for i in orch.store.get_active_set()}
        for k in (before | set(task)) - after:
            if k in admitted_at:
                lifetimes["useful" if k in useful else "background"].append(c - admitted_at.pop(k))
        m["occupancy"].append(len(orch.store))
        # every eviction, capacity overflow included (CycleResult.evicted counts only the forget phase)
        m["evicted"].append(len(orch.forget_log) - log0)
        m.setdefault("evicted_forget_phase", []).append(r.evicted)
        m["inferred"].append(len(got))
        m["useful_resident"].append(sum(1 for u in useful if u in orch.store))
        m["derived_resident"].append(sum(1 for i in orch.store.get_active_set() if i.source_type == "derived"))
    return orch, m, lifetimes, useful


def _sim_summary():
    orch, m, lifetimes, useful = _simulate()
    occ = m["occupancy"]
    mean = lambda xs: (sum(xs) / len(xs)) if xs else None
    s = {
        "capacity": 20, "cycles": len(occ),
        "occupancy_mean": mean(occ), "occupancy_min_last50": min(occ[50:]), "occupancy_max": max(occ),
        "evictions_per_cycle_mean": mean(m["evicted"]),
        "inferences_admitted_per_cycle_mean": mean(m["inferred"]),
        "useful_resident_last10_mean": mean(m["useful_resident"][-10:]),
        "derived_resident_last10_mean": mean(m["derived_resident"][-10:]),
        "lifetime_useful_mean": mean(lifetimes["useful"]), "lifetime_useful_n": len(lifetimes["useful"]),
        "lifetime_background_mean": mean(lifetimes["background"]), "lifetime_background_n": len(lifetimes["background"]),
        "forgetting_log_size": len(orch.forget_log),
    }
    out = os.environ.get("WMTM_GAPCHECK_SIM_OUT")
    if out:
        with open(out, "w") as f:
            json.dump({"summary": s, "series": m}, f, indent=1)
    return s


def test_s12_3_simulation_100_cycles_stabilises():
    """s12.3: no endless growth, no collapse, forgetting active."""
    s = _sim_summary()
    assert s["occupancy_max"] <= 20
    assert s["occupancy_min_last50"] >= 5
    assert s["evictions_per_cycle_mean"] > 0


def test_s12_3_simulation_useful_items_survive():
    """s12.3: at steady state most of the 8 useful notes are resident, and they outlive background notes."""
    s = _sim_summary()
    assert s["useful_resident_last10_mean"] >= 6
    assert s["lifetime_background_n"] > 0
    assert s["lifetime_useful_mean"] is None or s["lifetime_useful_mean"] > s["lifetime_background_mean"]


# ------------------------------------------------------------------------ Mesto's worked examples (synthetic)

def test_mesto_4_forgetting_frees_space_without_forbidding_a_new_derivation():
    """Mesto s4: a forgotten conclusion reached again from different sources is a new derivation and is admitted."""
    orch = _orch()
    orch.store.admit("s0", "a", initial_sti=50.0); orch.store.admit("s9", "b", initial_sti=50.0)
    [d] = orch._admit_derived([_cand("x is y", ["s0"])])
    orch.forget_log.record(orch.store.evict(d.id), 0)
    assert orch._admit_derived([_cand("x is y", ["s0"])]) == []
    assert len(orch._admit_derived([_cand("x is y", ["s9"])])) == 1


def test_mesto_9_every_eviction_path_records_in_forgetting_log():
    """Mesto s9: capacity overflow, the tick floor and the policy all record the evicted item."""
    orch = _orch(capacity=3)
    for i in range(6):
        orch.store.admit(f"r{i}", f"note {i}", initial_sti=1.0 + i)
    orch._log_capacity_evictions()
    orch.store.admit("tiny", "tiny", initial_sti=0.005)
    orch.forget_phase()
    logged = {r.item_id for r in orch.forget_log.get_records()}
    assert {"r0", "r1", "r2"} <= logged and "tiny" in logged
