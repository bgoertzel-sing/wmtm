"""WMTMOrchestrator: ties all WMTM components into a single cycle.

One orchestration cycle:
1. Recall from LTM (via recall_bridge) into WMTM
2. Reasoner phase: admit PeTTaChainer conclusions from the shadow worker (Track L: the only reasoner)
3. GoalChainer feedback (optional)
4. Tick: decay attention, age items
5. Track utility (use/miss)
6. Apply forgetting policy (evict low-attention/low-utility)
7. Writeback high-utility items to LTM

The orchestrator is designed to be called once per agent step.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from .store import WMTMStore
from .utility import UtilityTracker
from .forgetting_log import ForgettingLog
from .forgetting import ForgettingPolicy
from .writeback import WritebackManager
from .goal_store import GoalStore


@dataclass
class CycleResult:
    """Summary of a single orchestration cycle."""
    cycle: int
    admitted_derived: int = 0
    pln_admitted: int = 0
    gc_admitted: int = 0
    pc_admitted: int = 0                 # Track I: PeTTaChainer conclusions admitted this cycle
    reasoner: str = "pettachainer"       # effective mode this cycle: pettachainer | off (Track L)
    reasoner_skipped: bool = False       # nothing admitted: reasoner off or no usable worker run (Track K/L)
    reasoner_info: dict = field(default_factory=dict)
    evicted: int = 0
    written_back: int = 0
    active_count: int = 0
    forgetting_log_size: int = 0


class WMTMOrchestrator:
    """Coordinates the full WMTM cycle: recall -> infer -> forget -> writeback.

    Usage:
        orch = WMTMOrchestrator(store)
        result = orch.cycle(recall_fn=None, append_fn=petta_append)
    """

    def __init__(
        self,
        store: WMTMStore,
        utility_tracker: Optional[UtilityTracker] = None,
        forgetting_policy: Optional[ForgettingPolicy] = None,
        forgetting_log: Optional[ForgettingLog] = None,
        writeback_manager: Optional[WritebackManager] = None,
        use_pln: bool = True,
        use_goalchainer: bool = False,
        goalchainer_request: str = '',
        goal_store: Optional[GoalStore] = None,
    ) -> None:
        """Initialize the WMTM orchestrator with a store and default forgetting policy.

        Args:
            use_pln: if True, run the reasoner phase (PeTTaChainer admission) each cycle.
        """
        self.store = store
        self.utility = utility_tracker or UtilityTracker()
        self.forgetting = forgetting_policy or ForgettingPolicy()
        self.forget_log = forgetting_log or ForgettingLog()
        self.forget_log_override_threshold = 500.0  # only re-derive forgotten content if exceptionally high attention
        self.writeback = writeback_manager or WritebackManager()
        self.use_pln = use_pln
        self.use_goalchainer = use_goalchainer
        self.goalchainer_request = goalchainer_request
        self.goal_store = goal_store
        self._cycle = 0
        # Bot memory dir for the background-hook flags file (set by wmtm.api; None = env-only, dev/tests).
        self.runtime_state_dir = None
        self.default_reasoner = "pettachainer"   # used when the flags file / env does not set "reasoner"
        self.pc_admit_state = {}           # rc2: {"consumed_run": id, ...} - each admit.json run is admitted once
        self.context_rel = None            # Track P: relevance of items to the last real request (context.request_relevance)


    def active_goal(self):
        """Return the highest-priority active goal, or None."""
        if self.goal_store is None:
            return None
        active = self.goal_store.active()
        return active[0] if active else None

    # ── F01: State persistence for subprocess boundaries ───────────

    def snapshot_state(self) -> dict:
        """Serialize orchestrator state for persistence across subprocess restarts.

        F01: WMTM state (store items, attention values, cycle count) is lost when
        the agent process restarts. This method captures a JSON-serializable
        snapshot that can be restored via restore_state().

        F01b: Also persists UtilityTracker and ForgettingLog state. Without this,
        utility scores reset to 0.0 on every restart, making the forgetting policy
        unable to distinguish useful items from noise (all items show util=0.0).
        """
        snap = {
            "cycle": self._cycle,
            "store": self.store.to_dict(),
            "utility": self.utility.to_dict(),
            "forgetting_log": self.forget_log.to_dict(),
            "goal_store_path": self.goal_store.path if self.goal_store is not None else None,
        }
        if self.pc_admit_state:
            snap["pc_admit"] = dict(self.pc_admit_state)      # rc2: consumed admit.json run (absent until one)
        if self.context_rel:
            live = set(self.store._items)
            rel = dict(self.context_rel)
            rel["scores"] = {k: v for k, v in (rel.get("scores") or {}).items() if k in live}
            snap["context_rel"] = rel                          # Track P: read by the automated fast path
        return snap

    def restore_state(self, snapshot: dict) -> None:
        """Restore orchestrator state from a snapshot (F01).

        F01b: Also restores UtilityTracker and ForgettingLog state so that
        utility scores and forgetting history survive process restarts.

        Args:
            snapshot: dict from snapshot_state(), or empty dict for fresh start.
        """
        if not snapshot:
            return
        self._cycle = snapshot.get("cycle", 0)
        if "store" in snapshot:
            from .store import WMTMStore
            self.store = WMTMStore.from_dict(snapshot["store"])
        if "utility" in snapshot:
            from .utility import UtilityTracker
            self.utility = UtilityTracker.from_dict(snapshot["utility"])
        if "forgetting_log" in snapshot:
            from .forgetting_log import ForgettingLog
            self.forget_log = ForgettingLog.from_dict(snapshot["forgetting_log"])
        if isinstance(snapshot.get("pc_admit"), dict):
            self.pc_admit_state = dict(snapshot["pc_admit"])
        if isinstance(snapshot.get("context_rel"), dict):
            self.context_rel = dict(snapshot["context_rel"])

    # ── Phase helpers ──────────────────────────────────────────────

    def _recall_from_ltm(
        self,
        recall_fn: Optional[Callable[[], list[tuple[str, str, float]]]],
    ) -> None:
        """Pull items from LTM into the store via recall_fn."""
        if recall_fn is None:
            return
        for item_id, content, sti in recall_fn():
            self.store.admit(
                item_id=item_id,
                content=content,
                source_type='recalled',
                initial_sti=sti,
            )
        self._log_capacity_evictions()

    def _log_capacity_evictions(self) -> None:
        """Record any items evicted by capacity pressure since last drain."""
        for ev in self.store.drain_pending_evicted():
            self.forget_log.record(ev, self._cycle)


    def _goal_context_boost(self) -> None:
        """Boost STI for items whose content matches the active goal description."""
        goal = self.active_goal()
        if goal is None:
            return
        keywords = set(w.lower() for w in goal.description.split() if len(w) > 3)
        for item in self.store.get_active_set():
            item_words = set(w.lower() for w in item.content.split() if len(w) > 3)
            overlap = len(keywords & item_words)
            if overlap > 0:
                boost = 2.0 * overlap / max(len(keywords), 1)
                item.attention.boost(boost)

    def _admit_derived(self, candidates: list) -> list:
        """Admit novel, non-forgotten derived candidates; return admitted items."""
        admitted = []
        for i, cand in enumerate(candidates):
            if self._is_skipworthy(cand):
                continue
            item = self._admit_candidate(cand, i)
            if item is not None:
                admitted.append(item)
                for pid in cand.derived_from:
                    self.utility.record_inferred_from(pid)
        self._log_capacity_evictions()
        return admitted

    def _is_skipworthy(self, cand) -> bool:
        """Check if a candidate should be skipped (forgotten or duplicate)."""
        if self.forget_log.is_forgotten(cand.content):
            if cand.initial_sti < self.forget_log_override_threshold:
                return True
        return not self._is_novel(cand)

    def _is_novel(self, cand) -> bool:
        """Exact (case-insensitive, stripped) content match against the active set."""
        c = cand.content.lower().strip()
        return all(item.content.lower().strip() != c for item in self.store.get_active_set())

    def _admit_candidate(self, cand, index: int) -> None:
        """Admit a single derived candidate into the store."""
        item_id = f"derived-{cand.inference_type}-{self._cycle}-{index}"
        if cand.inference_type == "pc_deduction":
            # rc2: PeTTaChainer items can be admitted outside cycle() (budget-skipped / automated turns), where the
            # cycle counter may not advance between admissions: key by content so ids never collide.
            import hashlib
            item_id = f"derived-pc_deduction-{self._cycle}-{hashlib.md5(cand.content.encode()).hexdigest()[:8]}"
        return self.store.admit(
            item_id=item_id,
            content=cand.content,
            source_type='derived',
            derived_from=cand.derived_from,
            initial_sti=cand.initial_sti,
            provenance=getattr(cand, "provenance", None),
        )

    def _run_pln_phase(self, cfg=None, result=None, mode="pettachainer") -> list:
        """Reasoner phase (Track L: PeTTaChainer only; the Python PLN engine is gone).

        Admits PeTTaChainer conclusions from the shadow worker's admit file (never waits).  If the reasoner is off
        (mode "off": invalid/unknown flag value) or no fresh, canary-passed run is available, nothing is admitted
        this cycle and result.reasoner_info["skipped"] says why.  Returns the list of admitted derived items.
        """
        if not self.use_pln:
            return []
        if result is not None:
            result.reasoner = mode
        if mode != "pettachainer":
            if result is not None:
                result.reasoner_skipped = True
                result.reasoner_info = {"skipped": "reasoner_off"}
            return []
        pc_items, info = self.admit_reasoner(cfg)
        if pc_items is None:
            pc_items = []
            if result is not None:
                result.reasoner_skipped = True
        if result is not None:
            result.reasoner_info = info
            result.pc_admitted = len(pc_items)
        return pc_items

    def admit_reasoner(self, cfg=None, now=None):
        """Admit PeTTaChainer conclusions from admit.json (rc2: also called outside cycle()).  Cheap: no PLN.

        -> (items | None, info).  None = nothing may be admitted (missing/stale/failed run, already consumed)."""
        try:
            from .pc_admit import load_candidates
            from .candidate import InferenceCandidate

            def known(text):   # same tests as _is_skipworthy (PeTTaChainer STI s*c < forget-log override threshold)
                c = InferenceCandidate(content=text, confidence=0.0, derived_from=[], inference_type="pc_deduction")
                return self.forget_log.is_forgotten(text) or not self._is_novel(c)
            cands, info = load_candidates(cfg or {}, self.store, now,
                                          consumed=(self.pc_admit_state or {}).get("consumed_run"), known=known)
        except Exception as e:
            return None, {"skipped": "error:" + type(e).__name__, "admitted": 0}
        if cands is None:
            info["admitted"] = 0
            return None, info
        return self.admit_pc_candidates(cands, info)

    def admit_pc_candidates(self, cands, info):
        """Admit gated PeTTaChainer candidates; mark the run consumed if it yielded any.  -> (items, info)."""
        items = []
        if not cands:
            info["skipped"] = "no_candidates"
        else:
            try:
                items = self._admit_derived(cands)
            except Exception as e:
                info["admit_error"] = type(e).__name__
                info["admitted"] = 0
                return items, info
            import time as _t
            self.pc_admit_state = {"consumed_run": info.get("run"), "consumed_at": round(_t.time(), 3),
                                   "admitted": len(items), "cycle": self._cycle}
        info["admitted"] = len(items)
        return items, info

    def _run_goalchainer_phase(self) -> list:
        """Run GoalChainer over the WMTM active set and admit decisions.

        This is the feedback loop: GoalChainer reads WMTM evidence,
        makes a decision, and the results are admitted back into WMTM.

        Returns the list of admitted GoalChainer-derived items.
        """
        if not self.use_goalchainer or not self.goalchainer_request:
            return []
        # No evidence -> nothing for GoalChainer to decide on (matches
        # run_goalchainer_over_wmtm; lost when F04 inlined the call).
        if not self.store.get_active_set():
            return []
        try:
            from .goalchainer_bridge import run_goalchainer_over_wmtm
            gc_candidates = run_goalchainer_over_wmtm(
                self.store,
                self.goalchainer_request,
            )
            if not gc_candidates:
                return []
            return self._admit_derived(gc_candidates)
        except Exception:
            return []

    def _reinforce(self) -> None:
        """Boost STI for items that were actually used this cycle."""
        for item in self.store.get_active_set():
            rec = self.utility.get_record(item.id)
            if rec is not None and rec.use_count > 0 and rec.last_use_tick == self._cycle:
                item.attention.boost(2.0)

    def _do_writeback(
        self,
        append_fn: Optional[Callable[[str], None]],
        result: CycleResult,
        cfg: Optional[dict] = None,
    ) -> None:
        """Write high-utility items back to LTM via append_fn.

        v0.4: items admitted from PeTTaChainer (provenance reasoner=pettachainer) are written back only when the
        ``reasoner_writeback`` flag is on (default off: working memory only).
        """
        if append_fn is None:
            return
        wb_candidates = self.writeback.select_candidates(self.store)
        if not (cfg or {}).get("reasoner_writeback"):
            wb_candidates = [c for c in wb_candidates
                             if (getattr(c.item, "provenance", None) or {}).get("reasoner") != "pettachainer"]
        written = self.writeback.writeback(wb_candidates, append_fn)
        result.written_back = len(written)

    # ── Main cycle ─────────────────────────────────────────────────

    def cycle(
        self,
        recall_fn: Optional[Callable[[], list[tuple[str, str, float]]]] = None,
        append_fn: Optional[Callable[[str], None]] = None,
    ) -> CycleResult:
        """Run one full WMTM orchestration cycle.

        Args:
            recall_fn: optional callable returning [(item_id, content, sti)] from LTM
            append_fn: optional callable for writeback to LTM (petta_append)

        Returns CycleResult summary.
        """
        result = CycleResult(cycle=self._cycle)

        # 1. Recall from LTM
        self._recall_from_ltm(recall_fn)

        # 1b. Goal-driven context boost
        self._goal_context_boost()

        # 2a'. One flags read per cycle (Tracks G / H / I).
        try:
            from . import runtime_config as _rc
            _cfg = _rc.resolve(self.runtime_state_dir)
        except Exception:
            _cfg = {}
        try:
            from .pc_admit import mode as _reasoner_mode
            _mode = _reasoner_mode(_cfg, self.default_reasoner)
        except Exception:
            _mode = "off"
        if not self.runtime_state_dir:
            _mode = "off"   # Track L: scratch orchestrators (no state dir, e.g. decide()) never launch or admit from the shadow worker

        # 2b. Reasoner phase: admitted PeTTaChainer conclusions (Track L: no Python PLN)
        pln_admitted = self._run_pln_phase(_cfg, result, _mode)
        result.pln_admitted = len(pln_admitted)
        result.admitted_derived = len(pln_admitted)

        # 2b'. Track G / H background hooks: off unless enabled in <state_dir>/_wmtm_flags.json (or env).
        # Detached workers; they never admit, never wait and never raise.  One flags read per cycle.
        if _cfg.get("pc_shadow") or _mode == "pettachainer":
            try:
                from .pc_shadow import maybe_launch
                maybe_launch(self.store, self._cycle, cfg=_cfg, **({"force": True} if _mode == "pettachainer" else {}))       # Track G: PeTTaChainer shadow
            except Exception:
                pass
        if _cfg.get("semparse_feed"):
            try:
                from .parse_cache import maybe_feed
                maybe_feed(self.store, self._cycle, cfg=_cfg)         # Track H: enqueue top-K for parsing
            except Exception:
                pass

        # 2c. Run GoalChainer feedback loop and admit its decisions
        gc_admitted = self._run_goalchainer_phase()
        result.gc_admitted = len(gc_admitted)

        # 4. Tick: decay + age
        evicted_by_tick = self.store.tick()
        for ev in evicted_by_tick:
            self.forget_log.record(ev, self._cycle)

        # 5. Utility tracking
        self.utility.tick(self.store, self._cycle)

        # 5b. Reinforce used items
        self._reinforce()

        # 6. Forgetting policy
        evicted_by_policy = self.forgetting.evaluate(self.store)
        for ev in evicted_by_policy:
            self.forget_log.record(ev, self._cycle)
            self.utility.remove(ev.id)

        result.evicted = len(evicted_by_tick) + len(evicted_by_policy)

        # 7. Writeback
        self._do_writeback(append_fn, result, _cfg)

        result.active_count = len(self.store)
        result.forgetting_log_size = len(self.forget_log)

        # 8. Goal lifecycle: check achievement/expiry
        self._goal_lifecycle_check()

        self._cycle += 1
        return result


    def _goal_lifecycle_check(self) -> None:
        """Check active goals for expiry and update goal store."""
        if self.goal_store is None:
            return
        for goal in self.goal_store.active():
            if goal.is_expired(self._cycle) and goal.status in ('pending', 'active'):
                goal.abandon()
                self.goal_store.update(goal)

    @property
    def cycle_count(self) -> int:
        """Return the current cycle count."""
        return self._cycle
