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
    reasoner: str = "pettachainer"              # "pettachainer" | "off" (flags file "reasoner" overrides; unknown = off)
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
        from .pc_admit import REASONERS
        if config.reasoner not in REASONERS:
            raise ValueError(f"reasoner={config.reasoner!r} (expected one of {REASONERS})")
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
            orch.runtime_state_dir = str(self.state_dir)     # <state_dir>/_wmtm_flags.json gates the shadow hooks
            orch.default_reasoner = self.config.reasoner
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

    def context_for(self, prompt_text, automated=None, source=None):
        """Recall + reason + rank, persist state, and return the context block.

        Empty prompt_text (or automated=True) takes the automated fast path:
        no engine import, the block is rendered from the state file, which
        gets STI decay + stale cleanup. Returns None when there is nothing
        to show.

        source (Track Q, optional): the request's source envelope (e.g. the
        Telegram {"chat_id", ...} or sender fields). Stored, normalised, on
        the source_type=user request item for speaker linking. When omitted
        and the flags key speaker_link is on, it is read from the Iter
        request binding (wmtm.request_source.from_iter_env).
        """
        if automated is None:
            automated = not prompt_text
        tl = self._turn
        if automated:
            tl.t0 = None
            return _ctx.fast_path_automated(self.state_file, default_reasoner=self.config.reasoner,
                                            admit=self.config.use_pln)
        if getattr(tl, "t0", None) is None:
            tl.t0 = time.time()
        failed = getattr(tl, "failed", False)
        tl.failed = False
        user_msg = prompt_text
        context = None
        # v0.4 rc2: per-phase timing (seconds since turn start / per phase) + admission outcome -> admit_log.jsonl
        t_turn = tl.t0
        timing = {"cycle_budget": self.config.cycle_budget}
        adm = {"path": "user", "info": None}

        def lap(key, t):
            now = time.time()
            timing[key] = round(now - t, 4)
            return now
        try:
            if failed:
                adm["info"] = {"skipped": "observe_failed", "admitted": 0}
                raise _ObserveFailed()
            t = time.time()
            timing["pre_s"] = round(t - t_turn, 4)       # observe() (feedback) since turn start
            self._ensure_store_ready()
            t = lap("store_s", t)
            orch = self._orchestrator

            if not self._budget_ok():
                # Store init alone consumed the budget: inject only, no persist (as in the glue).
                adm["info"] = {"skipped": "store_init_budget", "admitted": 0}
                return _ctx.format_active_context(orch.store, orch.cycle_count) if orch else None

            store = orch.store
            pcfg = self._flags()                          # Track P switches (cheap JSON read; {} -> SPEC defaults)
            recall_scores, stim_scores, recalled_now = {}, {}, False
            protect = _ctx.protect_settings(pcfg)

            if user_msg and self._budget_ok():
                self._ensure_journal_ready()
            t = lap("journal_s", t)
            if user_msg and self._recall_bridge and self._budget_ok():
                rb = self._recall_bridge
                candidates = rb.recall(user_msg, store, top_k=15)
                admitted_snippets = []
                for c in candidates:
                    if c.cluster_id not in store:
                        if _ctx.is_duplicate_topic(c.content, admitted_snippets):
                            continue
                        origin_ts = rb.get_cluster_timestamp(c.cluster_id)
                        it = store.admit(
                            c.cluster_id, c.content,
                            source_type='recalled',
                            initial_sti=max(c.score * 10, 1.0),
                            origin_timestamp=origin_ts,
                        )
                        if protect:
                            it.mark_recalled(orch.cycle_count)
                        recall_scores[c.cluster_id] = c.score
                        admitted_snippets.append(c.content)
                t = lap("recall_s", t)
                stim_scores = _ctx.relevance_stimulus(store, rb, user_msg, orch) or {}
                for iid, sc in stim_scores.items():   # Track P: residents matching this request count as recalled now
                    it = store.get(iid)
                    if protect and sc > 0 and it is not None:
                        it.mark_recalled(orch.cycle_count)
                recalled_now = True
                t = lap("relevance_s", t)
            if user_msg and self._budget_ok():
                _ctx.admit_request_item(store, user_msg, orch.cycle_count, pcfg,
                                        source=self._request_source(source, user_msg, pcfg))   # Track P (c) + Q

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
                _ctx.cleanup_stale_items(store, orch.cycle_count, protect=protect)
            if recalled_now and _ctx.setting(pcfg, "context_rank"):
                orch.context_rel = _ctx.request_relevance(store, self._recall_bridge, user_msg, recall_scores,
                                                          stim_scores, orch.cycle_count)
            t = lap("derives_cleanup_s", t)
            timing["elapsed_before_cycle_s"] = round(t - t_turn, 4)

            if self._budget_ok(limit=self.config.cycle_budget):
                if self.config.use_goalchainer:
                    orch.goalchainer_request = user_msg
                journal = self.journal
                res = orch.cycle(append_fn=lambda note: journal.append(note))
                t = lap("cycle_s", t)
                if res.reasoner == "pettachainer":
                    adm["info"] = dict(res.reasoner_info or {}, admitted=res.pc_admitted)
                else:
                    adm["path"] = None
            else:
                # rc2: the full cycle is skipped for budget, but PeTTaChainer admission is cheap (no PLN): run it
                # anyway, so a fresh admit.json is not lost on a busy host.  Then tick as before.
                adm["path"] = "budget-skipped"
                adm["info"] = self._admit_outside_cycle(orch)
                t = lap("admit_s", t)
            if adm["path"] == "budget-skipped" and self._budget_ok():
                evicted = store.tick()
                for ev in evicted:
                    orch.forget_log.record(ev, orch._cycle)
                orch.utility.tick(store, orch._cycle)
                orch._cycle += 1
                t = lap("tick_s", t)

            context, shown = _ctx.format_context(orch.store, orch.cycle_count, pcfg, orch.context_rel,
                                                 request=user_msg)
            if context:
                # F17: passive utility for displayed items (Track P: the items actually shown).
                for iid in shown:
                    orch.utility.record_use(iid, orch._cycle)

        except _ObserveFailed:
            pass
        except Exception as e:
            print(f"[wmtm_context] WARNING: {type(e).__name__}: {e}", file=sys.stderr)
            if adm["info"] is None:
                adm["info"] = {"skipped": "error:" + type(e).__name__, "admitted": 0}
        finally:
            tl.t0 = None
            timing["total_s"] = round(time.time() - t_turn, 4)
            self._log_admission(adm, timing)

        self.save()
        return context

    def _request_source(self, source, user_msg, pcfg):
        """Track Q: normalised request source for the request item, or None.  Never raises."""
        try:
            from . import request_source as _rs
            if source is not None:
                return _rs.normalise(source) or None
            if (pcfg or {}).get("speaker_link"):
                return _rs.from_iter_env(user_msg)
        except Exception:
            pass
        return None

    def _flags(self):
        """Resolved flags file (Track P switches).  Never raises; {} means SPEC defaults."""
        try:
            from . import runtime_config as _rc
            return _rc.resolve(str(self.state_dir))
        except Exception:
            return {}

    def _reasoner_cfg(self):
        """-> (flags cfg, effective reasoner mode).  Never raises."""
        try:
            from . import runtime_config as _rc
            from .pc_admit import mode
            cfg = _rc.resolve(str(self.state_dir))
            return cfg, mode(cfg, self.config.reasoner)
        except Exception:
            return {}, "off"

    def _admit_outside_cycle(self, orch):
        """rc2: PeTTaChainer admission on a user turn whose full cycle was skipped for budget."""
        cfg, m = self._reasoner_cfg()
        if m != "pettachainer" or not self.config.use_pln:
            return None
        try:
            items, info = orch.admit_reasoner(cfg)
            return info
        except Exception as e:
            return {"skipped": "error:" + type(e).__name__, "admitted": 0}

    def _log_admission(self, adm, timing):
        """Append the user-turn record (path, run, counts, skip reason, phase timing) when reasoner=pettachainer."""
        try:
            if adm.get("path") is None:
                return
            cfg, m = self._reasoner_cfg()
            if m != "pettachainer":
                return
            from .pc_admit import log_admission
            log_admission(cfg, adm["path"], adm.get("info") or {"skipped": "not_reached", "admitted": 0}, timing)
        except Exception:
            pass

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
