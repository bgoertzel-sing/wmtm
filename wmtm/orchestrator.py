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
        self.trivial_filter = True         # GAP-5: pc_admit.TRIVIAL_RULE on PeTTaChainer candidates (flag admit_trivial_filter)
        self.trivial_refused = []          # GAP-5: last 200 refusals {cycle, rule, reason, goal}; count in trivial_refused_n
        self.trivial_refused_n = 0
        self.context_rel = None            # Track P: relevance of items to the last real request (context.request_relevance)
        self._recall_used = [-1, 0]        # design s8.3: [cycle, new recalled items admitted in that cycle]


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
        if self._recall_used[1] and self._recall_used[0] == self._cycle:
            snap["recall_used"] = list(self._recall_used)       # design s8.3: this cycle's recall budget use (absent if none)
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
        ru = snapshot.get("recall_used")
        if isinstance(ru, (list, tuple)) and len(ru) == 2:
            try:
                self._recall_used = [int(ru[0]), max(0, int(ru[1]))]
            except (TypeError, ValueError):
                pass

    # ── Phase helpers ──────────────────────────────────────────────

    # ── Design s8.3 recall budget ──────────────────────────────────
    # "Each cycle: admit at most N new items (default: 10)".  One budget per WMTM cycle (the cycle counter), shared by
    # every path that admits recalled items in that cycle: the user-turn recall in api.context_for (which runs before
    # cycle() under the same counter) and cycle(recall_fn=...).  Re-admitting a resident item is not a new item.

    def recall_slots(self, budget) -> Optional[int]:
        """New recalled items this cycle may still admit under budget (an int > 0, or None = no budget)."""
        if budget is None:
            return None
        used = self._recall_used[1] if self._recall_used[0] == self._cycle else 0
        return max(0, int(budget) - used)

    def take_recall_slot(self, budget) -> bool:
        """Count one new recalled item against this cycle's budget; False (nothing counted) when it is spent."""
        slots = self.recall_slots(budget)
        if slots is not None and slots <= 0:
            return False
        if self._recall_used[0] != self._cycle:
            self._recall_used = [self._cycle, 0]
        self._recall_used[1] += 1
        return True

    def _recall_budget(self):
        try:
            from . import runtime_config as _rc
            from .context import recall_budget
            return recall_budget(_rc.resolve(self.runtime_state_dir))
        except Exception:
            return 10

    def _recall_from_ltm(
        self,
        recall_fn: Optional[Callable[[], list[tuple[str, str, float]]]],
    ) -> None:
        """Pull items from LTM into the store via recall_fn, at most recall_budget new items this cycle (design s8.3).

        When recall_fn offers more new items than the budget has left, the ones with the highest STI are admitted
        (ties: recall_fn's order); re-admissions of resident items are not limited."""
        if recall_fn is None:
            return
        rows = list(recall_fn())
        budget = self._recall_budget()
        slots = self.recall_slots(budget)
        keep = None
        if slots is not None:
            new, seen = [], set()
            for i, (item_id, _c, sti) in enumerate(rows):
                if item_id not in self.store and item_id not in seen:
                    seen.add(item_id)
                    new.append((-float(sti), i, item_id))
            if len(new) > slots:
                keep = {iid for _s, _i, iid in sorted(new)[:slots]}
        for item_id, content, sti in rows:
            if item_id not in self.store:
                if keep is not None and item_id not in keep:
                    continue
                if not self.take_recall_slot(budget):
                    continue
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
            if self._is_skipworthy(cand) or self._is_trivial(cand):
                continue
            item = self._admit_candidate(cand, i)
            if item is not None:
                admitted.append(item)
                for pid in cand.derived_from:
                    self.utility.record_inferred_from(pid)
        self._log_capacity_evictions()
        return admitted

    def _is_trivial(self, cand) -> bool:
        """GAP-5 TRIVIAL_RULE (pc_admit.trivial_reason): refuse a PeTTaChainer conclusion whose proof is only an nwdef
        head-noun step or a Narrow-restriction echo applied to asserted facts.  Logged and counted."""
        prov = getattr(cand, "provenance", None) or {}
        if not self.trivial_filter or cand.inference_type != "pc_deduction" or not prov.get("proof"):
            return False
        from .pc_admit import trivial_reason, TRIVIAL_RULE
        why = trivial_reason(prov.get("proof"), prov.get("rules"))
        if not why:
            return False
        self.trivial_refused_n += 1
        self.trivial_refused = (self.trivial_refused + [{"cycle": self._cycle, "rule": TRIVIAL_RULE, "reason": why,
                                                          "goal": prov.get("goal")}])[-200:]
        return True

    def _note_guard_refusals(self, info, n0) -> None:
        """followup-v2 finding 4: copy refusals made by the orchestrator guard (_is_trivial) during this admit into
        info, so pc_admit.log_admission writes them to admit_log.jsonl like the load_candidates (primary) path.
        Each entry is tagged by="guard"; trivial_refused_n and dropped["trivial"] count both paths."""
        k = self.trivial_refused_n - n0
        if k <= 0:
            return
        new = [dict(e, by="guard") for e in self.trivial_refused[-k:]] if k <= len(self.trivial_refused) else \
            [dict(e, by="guard") for e in self.trivial_refused]
        info["trivial_refused"] = list(info.get("trivial_refused") or []) + new
        info["trivial_refused_n"] = int(info.get("trivial_refused_n") or 0) + k
        info["trivial_refused_guard_n"] = k
        drop = info.get("dropped")
        if isinstance(drop, dict):
            drop["trivial"] = int(drop.get("trivial") or 0) + k

    def _is_skipworthy(self, cand) -> bool:
        """Check if a candidate should be skipped (forgotten or duplicate)."""
        if self.forget_log.is_forgotten(cand.content, list(cand.derived_from or [])):   # F1 §4: derivation key
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
            from .pc_admit import load_candidates, trivial_filter_on
            from .candidate import InferenceCandidate
            self.trivial_filter = trivial_filter_on(cfg)

            def known(text, srcs=()):   # same tests as _is_skipworthy; F1 §4: forgotten = this derivation (text + sources)
                c = InferenceCandidate(content=text, confidence=0.0, derived_from=list(srcs), inference_type="pc_deduction")
                return self.forget_log.is_forgotten(text, list(srcs)) or not self._is_novel(c)
            cands, info = load_candidates(cfg or {}, self.store, now,
                                          consumed=(self.pc_admit_state or {}).get("consumed_run"), known=known,
                                          context_rel=self.context_rel)
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
            n0 = self.trivial_refused_n
            try:
                items = self._admit_derived(cands)
            except Exception as e:
                info["admit_error"] = type(e).__name__
                info["admitted"] = 0
                return items, info
            self._note_guard_refusals(info, n0)
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

        # 4-6. Tick, utility, reinforce, forgetting policy (F1 §9: the same rule the automated fast path applies)
        result.evicted = len(self.forget_phase())

        # 7. Writeback
        self._do_writeback(append_fn, result, _cfg)

        result.active_count = len(self.store)
        result.forgetting_log_size = len(self.forget_log)

        # 8. Goal lifecycle: check achievement/expiry
        self._goal_lifecycle_check()

        self._cycle += 1
        return result


    def forget_phase(self) -> list:
        """F1 §9: the one eviction/forgetting rule of a turn, shared by cycle() and the automated fast path.

        Tick (decay + age, STI floor), utility tick, reinforce used items, forgetting policy.  Every eviction is
        recorded in the forgetting log (and its utility record dropped).  -> evicted items."""
        evicted = []
        for ev in self.store.tick():
            self.forget_log.record(ev, self._cycle)
            evicted.append(ev)
        self.utility.tick(self.store, self._cycle)
        self._reinforce()
        for ev in self.forgetting.evaluate(self.store):
            self.forget_log.record(ev, self._cycle)
            self.utility.remove(ev.id)
            evicted.append(ev)
        return evicted

    def stale_cleanup(self, protect=None, record=True) -> list:
        """F1 §9: wall-clock stale cleanup (context.cleanup_stale_items) with each eviction recorded in the
        forgetting log, on every path.  -> evicted items."""
        from .context import cleanup_stale_items
        evicted = cleanup_stale_items(self.store, self._cycle, protect=protect) or []
        for ev in (evicted if record else []):
            self.forget_log.record(ev, self._cycle)
            self.utility.remove(ev.id)
        return evicted

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
