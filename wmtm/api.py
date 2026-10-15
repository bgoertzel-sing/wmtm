"""Public WMTM interface: the only thing bots call.

    mem = WMTM(WMTMConfig(state_dir=...))
    mem.observe({"user": user_text, "assistant": last_reply})  # this turn's content
    ctx = mem.context_for(user_text)        # text block for the prompt, or None
    mem.derive(note, source_ids=None)       # explicit tool: add a derived belief
    mem.decide(request)                     # explicit tool: GoalChainer decision
    mem.save(); mem.close()

The turn logic is the Iter glue (transformations/wmtm_context.py at
snapshot 83ea611) with its bot-specific parts injected through WMTMConfig.
Behaviour is identical on the same inputs (tests/test_replay_equivalence.py).

Concurrency (unchanged from the Iter glue):
- Engine init is guarded by a per-instance threading lock (double-checked).
- Pending derives use an fcntl.flock-protected file in state_dir:
  derive() appends under LOCK_EX, context_for() drains (read + truncate)
  under LOCK_EX, so appends from other threads/processes are never lost.
- The state file itself is not locked (same as the glue); see README.
"""
from __future__ import annotations

import hashlib
import json as _json
import os as _os
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from . import context as _ctx
from .journal import PettaJournal, default_journal_dir, resolve_supersedes

DEFAULT_GOALCHAINER_SRC = '/home/openclaw/research-agent/projects/omegaclaw/repos/OmegaClaw-GoalChainer/src'


@dataclass
class WMTMConfig:
    """Everything bot-specific. The module never hardcodes these."""
    state_dir: Any                              # store + locks live here (one per bot)
    journal: Any = None                         # read_lines()/append(note, supersedes, about); default PettaJournal
    llm: Optional[Callable[..., str]] = None    # llm(prompt, **opts) -> str (unused until semantic parsing lands)
    petta: Any = None                           # PeTTa runtime handle/path (PeTTaChainer backend, not yet used)
    use_goalchainer: bool = False
    reasoner: str = "python"                    # "python" | "pettachainer" (not yet implemented)
    capacity: int = 60
    use_pln: bool = True
    journal_refresh_interval: float = 300.0     # re-parse the journal at most every N s
    time_budget: float = 20.0                   # skip heavy phases after N s (Iter transform timeout is 30 s)
    cycle_budget: float = 15.0                  # run the full orchestrator cycle only within N s
    goalchainer_src: str = DEFAULT_GOALCHAINER_SRC
    state_filename: str = "_wmtm_state.json"
    pending_filename: str = "_wmtm_pending_derives.jsonl"


def drain_pending_derives(pending_path):
    """Read + clear the pending-derives file under the same flock that
    derive() uses, so an append landing between read and clear is never
    lost. Returns the list of raw lines read."""
    import fcntl
    with open(pending_path, 'r+') as pf:
        fcntl.flock(pf, fcntl.LOCK_EX)
        try:
            lines = pf.read().strip().splitlines()
            pf.seek(0)
            pf.truncate()
        finally:
            fcntl.flock(pf, fcntl.LOCK_UN)
    return lines


def append_pending_derive(pending_path, note, source_ids):
    """Append one derive request under LOCK_EX (multi-thread/multi-process safe)."""
    import fcntl
    entry = _json.dumps({'note': note, 'source_ids': source_ids})
    with open(pending_path, 'a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(entry + chr(10))
            f.flush()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def derived_item_id(note):
    return 'derived-' + hashlib.md5(note.encode()).hexdigest()[:12]


class WMTM:
    def __init__(self, config: WMTMConfig):
        if config.reasoner != "python":
            raise NotImplementedError(f"reasoner={config.reasoner!r} (only 'python' is available)")
        self.config = config
        self.state_dir = Path(config.state_dir)
        self.state_file = self.state_dir / config.state_filename
        self.pending_path = self.state_dir / config.pending_filename
        self.journal = config.journal if config.journal is not None else PettaJournal(default_journal_dir(self.state_dir))
        self._orchestrator = None
        self._recall_bridge = None
        self._journal_clusters = None
        self._last_refresh = 0
        self._lock = threading.Lock()
        self._turn = threading.local()

    # ── lazy init ──────────────────────────────────────────────────

    @property
    def orchestrator(self):
        return self._orchestrator

    def _ensure_store_ready(self):
        """Create orchestrator + restore persisted state. Fast path (<1 s)."""
        if self._orchestrator is not None:
            return
        with self._lock:
            if self._orchestrator is not None:
                return
            from . import WMTMStore, WMTMOrchestrator
            store = WMTMStore(capacity=self.config.capacity)
            orch = WMTMOrchestrator(store, use_pln=self.config.use_pln,
                                    use_goalchainer=self.config.use_goalchainer)
            try:
                if _os.path.exists(self.state_file):
                    with open(self.state_file) as f:
                        snapshot = _json.load(f)
                    orch.restore_state(snapshot)
            except Exception as e:
                print(f"[wmtm_context] WARN: state restore failed: {type(e).__name__}: {e}", file=sys.stderr)
            self._orchestrator = orch

    def _ensure_journal_ready(self):
        """Parse the journal and (re)create the recall bridge (slow path)."""
        iv = self.config.journal_refresh_interval
        if self._recall_bridge is not None and (time.time() - self._last_refresh) < iv:
            return
        with self._lock:
            if self._recall_bridge is not None and (time.time() - self._last_refresh) < iv:
                return
            from .recall_bridge import parse_journal, RecallBridge
            lines = self.journal.read_lines()
            clusters = parse_journal(resolve_supersedes(lines))
            self._journal_clusters = clusters
            self._last_refresh = time.time()
            self._recall_bridge = RecallBridge(clusters)

    # ── per-turn API ───────────────────────────────────────────────

    def observe(self, turn):
        """Record this turn's content and apply response feedback.

        turn: {"user": str, "assistant": str | None} or a plain user string.
        "user" is the real user request for this turn ("" for automated
        turns; then nothing happens and no engine is loaded). "assistant"
        is the previous reply, passed only if it answered a real user
        message (the adapter decides; F30).
        """
        if isinstance(turn, str):
            turn = {"user": turn}
        user = (turn or {}).get("user") or ""
        tl = self._turn
        tl.t0 = None
        tl.failed = False
        if not user:
            return
        tl.t0 = time.time()
        try:
            self._ensure_store_ready()
            if not self._budget_ok():
                return
            texts = []
            resp = turn.get("assistant") or ""
            if resp and len(resp) >= 20:
                texts.append(("response", resp))
            if len(user) >= 20:
                texts.append(("query", user))
            _ctx.check_response_feedback(texts, self._orchestrator.store, self._orchestrator)
        except Exception as e:
            tl.failed = True
            print(f"[wmtm_context] WARNING: {type(e).__name__}: {e}", file=sys.stderr)

    def _budget_ok(self, limit=None):
        t0 = getattr(self._turn, "t0", None)
        if t0 is None:
            return True
        return (time.time() - t0) < (self.config.time_budget if limit is None else limit)

    def context_for(self, prompt_text, automated=None):
        """Recall + reason + rank, persist state, and return the context block.

        Empty prompt_text (or automated=True) takes the automated fast path:
        no engine import, the block is rendered from the state file, which
        gets STI decay + stale cleanup. Returns None when there is nothing
        to show.
        """
        if automated is None:
            automated = not prompt_text
        tl = self._turn
        if automated:
            tl.t0 = None
            return _ctx.fast_path_automated(self.state_file)
        if getattr(tl, "t0", None) is None:
            tl.t0 = time.time()
        failed = getattr(tl, "failed", False)
        tl.failed = False
        user_msg = prompt_text
        context = None
        try:
            if failed:
                raise _ObserveFailed()
            self._ensure_store_ready()
            orch = self._orchestrator

            if not self._budget_ok():
                # Store init alone consumed the budget: inject only, no persist (as in the glue).
                return _ctx.format_active_context(orch.store, orch.cycle_count) if orch else None

            store = orch.store

            if user_msg and self._budget_ok():
                self._ensure_journal_ready()
            if user_msg and self._recall_bridge and self._budget_ok():
                rb = self._recall_bridge
                candidates = rb.recall(user_msg, store, top_k=15)
                admitted_snippets = []
                for c in candidates:
                    if c.cluster_id not in store:
                        if _ctx.is_duplicate_topic(c.content, admitted_snippets):
                            continue
                        origin_ts = rb.get_cluster_timestamp(c.cluster_id)
                        store.admit(
                            c.cluster_id, c.content,
                            source_type='recalled',
                            initial_sti=max(c.score * 10, 1.0),
                            origin_timestamp=origin_ts,
                        )
                        admitted_snippets.append(c.content)
                _ctx.relevance_stimulus(store, rb, user_msg, orch)

            if self._budget_ok():
                if self.pending_path.exists():
                    try:
                        for line in drain_pending_derives(self.pending_path):
                            if not line.strip():
                                continue
                            d = _json.loads(line)
                            item_id = derived_item_id(d['note'])
                            if item_id not in store:
                                store.admit(
                                    item_id, d['note'],
                                    source_type='derived',
                                    derived_from=d.get('source_ids', []),
                                    initial_sti=20.0,
                                )
                    except Exception:
                        pass

            if self._budget_ok():
                _ctx.cleanup_stale_items(store, orch.cycle_count)

            if self._budget_ok(limit=self.config.cycle_budget):
                if self.config.use_goalchainer:
                    orch.goalchainer_request = user_msg
                journal = self.journal
                orch.cycle(append_fn=lambda note: journal.append(note))
            elif self._budget_ok():
                evicted = store.tick()
                for ev in evicted:
                    orch.forget_log.record(ev, orch._cycle)
                orch.utility.tick(store, orch._cycle)
                orch._cycle += 1

            context = _ctx.format_active_context(orch.store, orch.cycle_count)
            if context:
                # F17: passive utility for displayed items.
                for item in orch.store.get_active_set()[:15]:
                    orch.utility.record_use(item.id, orch._cycle)

        except _ObserveFailed:
            pass
        except Exception as e:
            print(f"[wmtm_context] WARNING: {type(e).__name__}: {e}", file=sys.stderr)
        finally:
            tl.t0 = None

        self.save()
        return context

    # ── explicit tools ─────────────────────────────────────────────

    def derive(self, note, source_ids=None):
        """Register a derived belief; admitted on the next context_for()."""
        try:
            if source_ids is None:
                source_ids = []
            elif isinstance(source_ids, str):
                source_ids = [source_ids]
            append_pending_derive(self.pending_path, note, source_ids)
            item_id = derived_item_id(note)
            return 'Registered derived belief ' + item_id + ' in WMTM (pending): ' + note[:100]
        except Exception as e:
            return 'WMTM derive error: ' + str(e)

    def _decide_memory_items(self):
        """WMTM evidence for GoalChainer: a scratch store from the latest journal clusters."""
        try:
            from . import WMTMStore, WMTMOrchestrator
            from .recall_bridge import parse_journal
            clusters = parse_journal(resolve_supersedes(self.journal.read_lines()))
            store = WMTMStore(capacity=self.config.capacity)
            for c in clusters[-15:]:
                store.admit(c.id, c.event_note or c.text, source_type='recalled', initial_sti=10.0)
            WMTMOrchestrator(store).cycle()
            items = [{'id': it.id, 'content': it.content, 'sti': float(it.attention.sti)}
                     for it in store.get_active_set()[:20]]
            return items or None
        except Exception:
            return None

    def decide(self, request, solve_incident=None):
        """Run the GoalChainer decision pipeline with WMTM evidence. Returns text."""
        try:
            if solve_incident is None:
                gc_dir = self.config.goalchainer_src
                if gc_dir and gc_dir not in sys.path:
                    sys.path.insert(0, gc_dir)
                _os.environ.setdefault('GOALCHAINER_USE_HEURISTIC_PLN', '1')
                from goal_chainer.pipeline import solve_incident
            memory_items = self._decide_memory_items()
            result = solve_incident(request, memory_items=memory_items)
            lines = ['Decision: ' + str(result.get('decided')) + ' - ' + str(result.get('label')),
                     'Status: ' + str(result.get('status')), '', 'Ranked actions:']
            for d in result.get('decisions', []):
                score = d.get('score', 'N/A')
                lines.append('  ' + str(d.get('action_id')) + ': ' + str(d.get('label')) + ' - '
                             + str(d.get('status')) + ' (score=' + str(score) + ')')
            motivation = result.get('motivation')
            if motivation:
                lines += ['', 'Motivation: ' + str(motivation)[:200]]
            if memory_items:
                lines += ['', 'WMTM evidence: ' + str(len(memory_items)) + ' items fed to GoalChainer']
            return '\n'.join(lines)
        except Exception as e:
            return 'GoalChainer error: ' + str(e)

    # ── persistence ────────────────────────────────────────────────

    def save(self):
        """Persist the loaded engine state (no-op if the engine was never loaded)."""
        try:
            if self._orchestrator is not None:
                snapshot = self._orchestrator.snapshot_state()
                if snapshot and not snapshot.get("store", {}).get("items"):
                    print(f"[wmtm_context] WARN: saving snapshot with 0 store items "
                          f"(cycle={snapshot.get('cycle', '?')})", file=sys.stderr)
                if snapshot:
                    with open(self.state_file, "w") as f:
                        _json.dump(snapshot, f)
        except Exception as e:
            print(f"[wmtm_context] ERROR persisting state: {type(e).__name__}: {e}", file=sys.stderr)

    def close(self):
        """Drop in-memory engine state. Does NOT save: context_for() already
        persisted, and the automated fast path may have updated the state
        file since the engine was loaded."""
        self._orchestrator = None
        self._recall_bridge = None
        self._journal_clusters = None


class _ObserveFailed(Exception):
    pass
