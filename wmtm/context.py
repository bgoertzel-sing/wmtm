"""Generic WMTM turn logic, moved from Iter's transformations/wmtm_context.py.

Snapshot 83ea611. Everything here is runtime-independent: it works on a
WMTMStore / orchestrator / state snapshot and plain text. Chat-message
parsing (finding the last user message, spotting automated prompts) stays
in each runtime's adapter (see adapters/iter_transformation.py).

The function bodies are kept verbatim from the Iter glue so behaviour is
identical; only signatures changed where the glue read module globals.
"""
import json as _json
import os as _os
import sys


def parse_item_id_timestamp(item_id):
    """Parse a date from an item ID and return a Unix timestamp, or 0.0.

    F26b: Mirrors the recall_bridge._parse_cluster_timestamp logic but runs
    in the fast path without importing wmtm. Handles:
    - ISO compact: ep-note-20250101T120000Z
    - Date-only: fact-example-2025-01-01
    - Compact YYYYMMDD: ep-20250101120000000000
    """
    import re
    # Format 1: ISO compact
    m = re.search(r'(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z', item_id)
    if m:
        try:
            import calendar, datetime
            dt = datetime.datetime(
                int(m.group(1)), int(m.group(2)), int(m.group(3)),
                int(m.group(4)), int(m.group(5)), int(m.group(6)),
            )
            return calendar.timegm(dt.timetuple())
        except (ValueError, OverflowError):
            pass

    # Format 2: YYYY-MM-DD
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', item_id)
    if m:
        try:
            import calendar, datetime
            dt = datetime.datetime(
                int(m.group(1)), int(m.group(2)), int(m.group(3)),
                12, 0, 0,
            )
            ts = calendar.timegm(dt.timetuple())
            if 1577836800 < ts < 1893456000:  # 2020-2030
                return ts
        except (ValueError, OverflowError):
            pass

    # Format 3: Compact YYYYMMDD prefix
    m = re.search(r'(20\d{2})(\d{2})(\d{2})\d{6,}', item_id)
    if m:
        try:
            import calendar, datetime
            dt = datetime.datetime(
                int(m.group(1)), int(m.group(2)), int(m.group(3)),
                12, 0, 0,
            )
            ts = calendar.timegm(dt.timetuple())
            if 1577836800 < ts < 1893456000:
                return ts
        except (ValueError, OverflowError):
            pass

    return 0.0


def is_duplicate_topic(content, existing_snippets, threshold=0.6):
    """Return True if content is too similar to any existing snippet.
    
    Uses Jaccard similarity on word sets to detect topically redundant items.
    This prevents the WMTM from being filled with 15 variations of the same
    observation (e.g., "send() fails because processing/ is empty").
    """
    if not existing_snippets:
        return False
    content_words = set(content.lower().split())
    if len(content_words) < 3:
        return False
    for snippet in existing_snippets:
        snippet_words = set(snippet.lower().split())
        if not snippet_words:
            continue
        intersection = content_words & snippet_words
        union = content_words | snippet_words
        jaccard = len(intersection) / len(union) if union else 0
        if jaccard >= threshold:
            return True
    return False

def cleanup_stale_items(store, cycle_count, max_zero_utility_cycles=10, protect=None):
    """Evict stale items based on utility, wall-clock age, and content quality.
    
    F14b+F15+F16: Multi-tier cleanup using WALL-CLOCK TIME, not cycle count.
    
    The iter process restarts every step, so cycle-based age never exceeds 1.
    Wall-clock timestamps (item.created_at) are the only reliable staleness
    measure.
    
    F16 FIX: Recalled journal items (source_type='recalled') use much longer
    thresholds than derived items. The old 1-hour Tier 2 evicted recalled items
    before they could accumulate utility, causing an infinite evict→re-admit
    loop: cleanup evicts zero-utility items after 1hr → journal recall re-admits
    them with fresh timestamps → next restart they're >1hr old → evicted again.
    Items never accumulated utility because they were constantly being reset.
    
    Thresholds:
    DERIVED items:
      1. Operational noise with zero utility → evict immediately
      2. Zero-utility derived items older than 1 hour → evict
      3. Low-utility derived items (util < 3.0) older than 24 hours → evict
      4. Derived items older than 72 hours with util < 5.0 → evict
      5. Trivially short derived content (< 20 chars) → evict
    
    RECALLED items (journal knowledge — the base context):
      1. Operational noise → evict immediately (even recalled noise is noise)
      2. Zero-utility recalled items → keep for 48 hours (not 1 hour!)
      3. Low-utility recalled items → keep for 7 days
      4. Hard cap: 14 days without high utility → evict
    
    BOTH:
      - Legacy items with created_at=0 and zero utility → evict

    Track P: ``protect`` = {"turns": N, "s": S} (from protect_settings(cfg)) spares items recalled for / matching a
    real user request within the last N cycles or S seconds (item.recalled_cycle / recalled_at) from every
    age/utility tier; only the operational-noise tier still applies.  rc2 (protect=None) evicted freshly recalled
    journal notes in the same turn, before the block was rendered: their journal age is >= 48 h and utility 0.
    """
    import time as _t
    now = _t.time()
    
    to_evict = []
    for item in list(store.get_active_set()):
        # F25: Use effective_age_seconds which considers origin_timestamp
        # (the journal entry's real date) instead of just created_at
        # (re-admission time). This prevents 23-day-old entries from
        # appearing "41 minutes old" after re-admission.
        if hasattr(item, 'effective_age_seconds'):
            wall_age_hours = item.effective_age_seconds / 3600.0
        else:
            wall_age_hours = (now - item.created_at) / 3600.0 if item.created_at > 0 else float('inf')
        is_recalled = (item.source_type == 'recalled')
        
        # Tier 0: Operational noise with zero utility → immediate eviction
        # (applies to ALL items, including recalled — noise is noise)
        if item.utility <= 0.0 and is_operational_noise(item.content):
            to_evict.append(item.id)
            continue

        if protect and is_recent_recall(getattr(item, "recalled_at", 0.0), getattr(item, "recalled_cycle", -1),
                                        cycle_count, now, protect):
            continue

        # Tier 1: Legacy items with no timestamp (created_at=0) and zero utility
        if item.created_at == 0.0 and item.utility <= 0.0:
            to_evict.append(item.id)
            continue
        
        if is_recalled:
            # F16: Recalled items get MUCH longer thresholds.
            # They're journal knowledge, not ephemeral operational state.
            # The old 1-hour threshold caused the evict-readmit loop.
            
            # Recalled Tier 2: Zero utility after 48 hours → stale recall
            if item.utility <= 0.0 and wall_age_hours >= 48.0:
                to_evict.append(item.id)
                continue
            
            # Recalled Tier 3: Low utility after 7 days → outlived relevance
            if item.utility < 3.0 and wall_age_hours >= 168.0:  # 7 * 24
                to_evict.append(item.id)
                continue
            
            # Recalled Tier 4: Hard cap — 14 days without high utility
            if wall_age_hours >= 336.0 and item.utility < 5.0:  # 14 * 24
                to_evict.append(item.id)
                continue
        else:
            # Derived items keep the original aggressive thresholds
            
            # Derived Tier 2: Zero utility + older than 1 hour = stale noise
            if item.utility <= 0.0 and wall_age_hours >= 1.0:
                to_evict.append(item.id)
                continue
            
            # Derived Tier 3: Low utility + older than 24 hours
            if item.utility < 3.0 and wall_age_hours >= 24.0:
                to_evict.append(item.id)
                continue
            
            # Derived Tier 4: 72 hours without high utility
            if wall_age_hours >= 72.0 and item.utility < 5.0:
                to_evict.append(item.id)
                continue
            
            # Derived Tier 5: Trivially short content (garbage inference output)
            if len(item.content) < 20:
                to_evict.append(item.id)
                continue
    
    for item_id in set(to_evict):
        store.evict(item_id)

def is_operational_noise(content):
    """Return True if content is clearly operational noise, not useful knowledge.
    
    Detects patterns like repeated ChannelContractError observations,
    "no additional user input" status updates, and similar ephemeral
    operational state that should not persist in working memory.
    """
    lower = content.lower()
    noise_patterns = [
        "channelcontracterror",
        "processing/ directory is empty",
        "processing/ is empty",
        "no active user request",
        "no additional user input",
        "send() fails by design",
        "send() correctly refuses",
        "send() requires exactly 1",
        "awaiting user input",
        "no pending user task",
        "all autonomous work complete",
        "task complete",
        "nothing left to do",
        # F16b: PeTTa batch monitoring noise
        "consolidation pass",
        "memory consolidation",
        "pass 52",
        "pass 56",
        "pass 79",
        "pass 48",
        "pass 73",
        "pass 80",
        "swipl processes",
        "state t (stopped",
        "run_manifest.json",
        "watchdog relaunch",
        "petta-memory state",
        "system critical",
        # F16b: Iter channel mechanics noise
        "channel mechanics verified",
        "send is request-bound",
        "receive moves inbox->processing",
    ]
    matches = sum(1 for pat in noise_patterns if pat in lower)
    # If content matches 2+ noise patterns, it's operational noise
    # F16b: Also flag single-match items that are clearly dated operational logs
    if matches >= 2:
        return True
    # Single-match items that start with timestamps or pass numbers
    if matches >= 1 and (lower.startswith("pass ") or lower.startswith("consolidation") 
                         or "petta" in lower and ("state" in lower or "memory" in lower)):
        return True
    return False



def check_response_feedback(texts_to_check, store, orchestrator):
    """Boost WMTM items referenced by the LLM response or the user query.

    texts_to_check: list of (source_type, text) with source_type
    "response" (assistant reply to a real user message; boost 3.0) or
    "query" (the real user message; boost 1.5). The adapter decides which
    texts qualify (F30: replies on automated ticks must not count).

    F15b thresholds: 20% distinctive-word overlap with 2+ matches, or a
    distinctive phrase substring match.
    """
    if not texts_to_check:
        return
    
    for item in store.get_active_set():
        content = item.content
        if len(content) < 20:
            continue
        
        # Extract distinctive words from the item
        item_words = set(w.strip(".,;:!?()[]{}\"'").lower()
                        for w in content.split() if len(w) > 3)
        distinctive = item_words - COMMON_WORDS
        if not distinctive:
            continue
        
        matched = False
        for source_type, text_content in texts_to_check:
            if matched:
                break
            text_lower = text_content.lower()
            text_words = set(text_lower.split())
            
            # Strategy 1: Distinctive keyword overlap (lowered thresholds)
            overlap = distinctive & text_words
            overlap_ratio = len(overlap) / len(distinctive)
            # F15b: 20% overlap with 2+ matches (was 30%/3)
            if overlap_ratio >= 0.20 and len(overlap) >= 2:
                boost = 3.0 if source_type == "response" else 1.5
                item.attention.boost(boost)
                orchestrator.utility.record_use(item.id, orchestrator._cycle)
                matched = True
                break
            
            # Strategy 2: Substring match on distinctive phrases
            for phrase in extract_distinctive_phrases(content):
                if phrase in text_lower:
                    boost = 3.0 if source_type == "response" else 1.5
                    item.attention.boost(boost)
                    orchestrator.utility.record_use(item.id, orchestrator._cycle)
                    matched = True
                    break


# Common words filtered from response-feedback matching
COMMON_WORDS = {
    # English
    "the", "this", "that", "with", "from", "have", "been", "will", "would",
    "could", "should", "about", "after", "before", "into", "over", "under",
    "between", "through", "during", "without", "also", "just", "only",
    "very", "more", "most", "some", "each", "every", "other", "another",
    "such", "much", "many", "still", "already", "even", "back", "then",
    "when", "where", "what", "which", "while", "since", "because", "like",
    "make", "made", "does", "done", "need", "needs", "used", "using",
    "work", "working", "check", "checked", "checking", "found", "find",
    # Tech generic
    "file", "files", "path", "data", "code", "test", "tests", "item",
    "items", "value", "values", "state", "store", "error", "status",
    "result", "results", "function", "method", "class", "module", "system",
    "process", "running", "active", "current", "updated", "update",
    "fixed", "added", "removed", "changed", "config", "memory", "cycle",
}


def extract_distinctive_phrases(content):
    """Extract distinctive phrases from content for substring matching.
    
    Yields short, specific substrings that are unlikely to appear by
    coincidence: commit hashes, error names, specific identifiers,
    file paths, numeric values with context.
    """
    import re
    # Commit hashes (7+ hex chars)
    for m in re.finditer(r'\b([0-9a-f]{7,40})\b', content.lower()):
        yield m.group(1)
    # Error/class names (CamelCase or UPPER_CASE)
    for m in re.finditer(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b', content):
        yield m.group(1).lower()
    for m in re.finditer(r'\b([A-Z_]{4,})\b', content):
        yield m.group(1).lower()
    # File paths
    for m in re.finditer(r'(?:[a-zA-Z_][a-zA-Z0-9_]*/){2,}[a-zA-Z_][a-zA-Z0-9_.]*', content):
        yield m.group(0).lower()
    # Specific numbers with context (e.g., "276 receipts", "g1025")
    for m in re.finditer(r'\b(g\d{4}|\d{3,}/\d{3,}|pid\s*\d+)\b', content.lower()):
        yield m.group(1)


def relevance_stimulus(store, bridge, user_msg, orch=None, rent=0.5):
    """F33b: ECAN-style stimulus for items already in working memory.

    recall() skips clusters already active, so resident items never saw the
    current message and old-topic items kept their STI. For a real user
    message: score every resident recalled item against it, inject STI scaled
    to the current attention scale (top relevance -> max resident STI + 1), and
    charge non-matching items rent (they lose a rent fraction of STI). Items
    whose cluster left the resolved journal (superseded) are evicted. Ranking
    stays ECAN-driven: nothing bypasses STI.
    """
    try:
        qterms = bridge._tokenize(user_msg)
        if not qterms:
            return {}
        items = [it for it in store.get_active_set() if it.source_type == 'recalled']
        active_ids = {it.id for it in store.get_active_set()}
        scores = {}
        for it in items:
            cl = bridge._by_id.get(it.origin_cluster or it.id)
            if cl is None:
                ev = store.evict(it.id)
                if ev is not None and orch is not None:
                    orch.forget_log.record(ev, orch._cycle)
                continue
            scores[it.id] = bridge._score_cluster(cl, qterms, active_ids, store)
        if not scores:
            return {}
        smax = max(scores.values())
        top_sti = max((it.attention.sti for it in store.get_active_set()), default=1.0)
        for it in items:
            s = scores.get(it.id)
            if s is None:
                continue
            if s > 0 and smax > 0:
                it.attention.boost((s / smax) * (top_sti + 1.0))
            else:
                it.attention.penalty(it.attention.sti * rent)
        return scores
    except Exception as e:
        import sys
        print(f"[wmtm_context] WARN relevance stimulus: {type(e).__name__}: {e}", file=sys.stderr)
        return {}


def format_active_context(store, cycle):
    """Format the WMTM active set as a context message for the LLM.
    
    F14c+F15: Shows wall-clock age (hours/days) instead of cycle-based age
    since cycle count never exceeds 1 due to process restarts. Items capped
    at 15 to reduce context noise.
    """
    import time as _t
    now = _t.time()
    items = store.get_active_set()
    if not items:
        return None
    
    display_items = items[:15]
    
    lines = []
    for item in display_items:
        source_tag = "derived" if item.source_type == "derived" else "recalled"
        sti = item.attention.sti
        util = item.utility
        # F25: Show wall-clock age based on effective age (considers origin_timestamp)
        if hasattr(item, 'effective_age_seconds'):
            age_secs = item.effective_age_seconds
        elif item.created_at > 0:
            age_secs = now - item.created_at
        else:
            age_secs = -1
        if age_secs >= 0:
            if age_secs < 3600:
                age_str = f"{age_secs/60:.0f}m"
            elif age_secs < 86400:
                age_str = f"{age_secs/3600:.1f}h"
            else:
                age_str = f"{age_secs/86400:.1f}d"
        else:
            age_str = "?"
        content = item.content[:200]
        lines.append(f"  [{source_tag} sti={sti:.1f} util={util:.1f} age={age_str}] {content}")
    
    total = len(items)
    shown = len(display_items)
    header = f"[WMTM Active Working Memory ({total} items, showing top {shown}, cycle {cycle})]"
    body = "\n".join(lines)
    return f"{header}\n{body}"


def _att_total(item_data):
    att = item_data.get("attention") or {}
    return att.get("sti", 0.0) * 1.0 + att.get("ati", 0.0) * 0.5 + att.get("lti", 0.0) * 0.2   # AttentionValue.total


def automated_hooks(state_dir, items_dict, cycle, cfg=None):
    """Track G/H background hooks for automated turns (rc2).

    The orchestrator runs pc_shadow.maybe_launch / parse_cache.maybe_feed only
    inside cycle(), i.e. on real user turns; most live cycles are automated and
    take the fast path, so without this the hooks never fire between user
    messages. Same gates as the cycle hooks (flags file, single-worker busy
    guard, hourly parse cap, shadow rate limit) plus ``hooks_on_automated``.
    Only light modules are imported (runtime_config, pc_shadow, parse_cache:
    stdlib + json); the workers build snapshots from the raw item fields.
    Never raises. -> {"shadow": pid|None, "feed": pid|None} or None if off.
    """
    try:
        if cfg is None:
            from . import runtime_config as rc
            cfg = rc.resolve(state_dir)
        if not cfg.get("hooks_on_automated") or not (cfg.get("pc_shadow") or cfg.get("semparse_feed")):
            return None
        k = int(cfg["shadow_k"])
        top = sorted(items_dict.values(), key=_att_total, reverse=True)[:k]     # active-set order
        out = {"shadow": None, "feed": None}
        if cfg.get("pc_shadow"):
            try:
                from . import pc_shadow
                out["shadow"] = pc_shadow.maybe_launch_raw([pc_shadow.raw_item_from_dict(d) for d in top], cycle, cfg,
                                                           source="automated")
            except Exception:
                pass
        if cfg.get("semparse_feed"):
            try:
                from . import parse_cache
                out["feed"] = parse_cache.feed_rows(
                    [(d.get("id"), d.get("content", ""), (d.get("attention") or {}).get("sti", 0.0))
                     + ((dict(d["source_meta"]),) if isinstance(d.get("source_meta"), dict) else ()) for d in top], cfg,
                    skip_unchanged=True)
            except Exception:
                pass
        return out
    except Exception as e:
        print(f"[wmtm_context] WARN automated hooks: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def automated_admit(state_dir, snapshot, cfg=None, default_reasoner="pettachainer"):
    """v0.4 rc2: admit PeTTaChainer conclusions on an automated turn (in place on the snapshot dict).

    Only with reasoner=pettachainer and flag ``reasoner_admit_on_automated``.  Same guards/caps as the cycle
    (pc_admit.admit_on_snapshot); every attempt is logged to admit_log.jsonl.  Never raises.  -> info or None."""
    try:
        import time as _t
        t0 = _t.perf_counter()
        if cfg is None:
            from . import runtime_config as rc
            cfg = rc.resolve(state_dir)
        from . import pc_admit
        if pc_admit.mode(cfg, default_reasoner) != "pettachainer":
            return None
        if not cfg.get("reasoner_admit_on_automated"):
            info = {"skipped": "automated_off", "admitted": 0}
        else:
            try:
                info = pc_admit.admit_on_snapshot(snapshot, cfg)
            except Exception as e:
                info = {"skipped": "error:" + type(e).__name__, "admitted": 0}
        pc_admit.log_admission(cfg, "automated", info, timing={"admit_s": _t.perf_counter() - t0})
        return info
    except Exception as e:
        print(f"[wmtm_context] WARN automated admit: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def fast_path_automated(state_file, run_hooks=True, default_reasoner="pettachainer", admit=True):
    """Ultra-lightweight turn for automated prompts (F20).

    Reads the persisted state JSON directly (no engine objects), returns the
    formatted context block (or None), applies STI decay + wall-clock stale
    cleanup to the snapshot, increments the cycle and saves it back.
    rc2: then runs the Track G/H hooks (automated_hooks) unless run_hooks=False.
    v0.4 rc2: first admits PeTTaChainer conclusions (automated_admit) unless admit=False, so they show this turn.
    """
    context = None
    try:
        if not _os.path.exists(state_file):
            return None

        with open(state_file) as f:
            snapshot = _json.load(f)

        store_data = snapshot.get("store", {})
        items_dict = store_data.get("items", {})
        if not items_dict:
            return None

        state_dir = _os.path.dirname(_os.path.abspath(state_file))
        cfg = None
        if admit or run_hooks:
            try:
                from . import runtime_config as _rc
                cfg = _rc.resolve(state_dir)
            except Exception:
                cfg = None                      # hooks/admit resolve again (and fail safe) themselves
        if admit:
            automated_admit(state_dir, snapshot, cfg, default_reasoner)
            store_data = snapshot.get("store", {})
            items_dict = store_data.get("items", {})

        # Format active context directly from JSON (no wmtm objects needed)
        import time as _t
        now = _t.time()
        cycle = snapshot.get("cycle", 0)
        if cfg is None:
            try:
                from . import runtime_config as _rc
                cfg = _rc.resolve(state_dir)
            except Exception:
                cfg = {}
        protect = protect_settings(cfg)

        if setting(cfg, "context_rank"):
            # Track P: same ranking/rendering as the user path, relevance = the last real request's (persisted).
            context, _shown = render_ranked(_entries_from_dicts(items_dict, now), snapshot.get("context_rel"),
                                            cycle, cfg)
        else:
            context = _render_rc2_from_dicts(items_dict, now, cycle)

        # Minimal state update: decay STI, increment cycle, cleanup stale items
        # F23: Wall-clock cleanup in fast path. Without this, stale items
        # persist forever because cleanup only ran in the full path (real
        # user messages), and nearly all cycles are automated.
        evict_ids = []
        for item_id, item_data in items_dict.items():
            att = item_data.get("attention", {})
            decay = att.get("sti_decay", 0.9)
            att["sti"] = att.get("sti", 0) * decay

            # F25+F26b: Wall-clock staleness check.
            # Priority: origin_timestamp > ID-parsed date > created_at.
            # origin_timestamp is the journal entry's real date; created_at is the
            # re-admission time. F26b adds ID-based date parsing as fallback for
            # items admitted before F25 (no origin_timestamp in state file).
            created = item_data.get("created_at", 0)
            origin_ts = item_data.get("origin_timestamp", 0)
            util = item_data.get("utility", 0)
            is_recalled = item_data.get("source_type") == "recalled"

            # F26b: Parse date from item ID when origin_timestamp is missing
            if origin_ts <= 0:
                origin_ts = parse_item_id_timestamp(item_id)

            # Use the oldest known timestamp for age calculation
            effective_ts = created
            if origin_ts > 0:
                effective_ts = min(origin_ts, created) if created > 0 else origin_ts
            
            if effective_ts > 0:
                age_hours = (now - effective_ts) / 3600.0
            else:
                age_hours = float('inf')

            # Track P: spare items recalled for / matching a recent real request (not noise: see cleanup_stale_items)
            if protect and is_recent_recall(item_data.get("recalled_at", 0.0), item_data.get("recalled_cycle", -1),
                                            cycle, now, protect):
                continue

            # Same thresholds as _cleanup_stale_items:
            if is_recalled:
                # 14-day hard cap for recalled items with utility < 5.0
                if age_hours >= 336.0 and util < 5.0:
                    evict_ids.append(item_id)
                # F26b: 7-day threshold for low-utility recalled items
                # (was missing from fast path — only _cleanup_stale_items had it)
                elif util < 3.0 and age_hours >= 168.0:
                    evict_ids.append(item_id)
                # 48h zero-utility recalled items
                elif util <= 0.0 and age_hours >= 48.0:
                    evict_ids.append(item_id)
            else:
                # 72h hard cap for derived items with utility < 5.0
                if age_hours >= 72.0 and util < 5.0:
                    evict_ids.append(item_id)
                # 1h zero-utility derived items
                elif util <= 0.0 and age_hours >= 1.0:
                    evict_ids.append(item_id)

        for eid in evict_ids:
            del items_dict[eid]
        crel = snapshot.get("context_rel")
        if evict_ids and isinstance(crel, dict) and isinstance(crel.get("scores"), dict):
            for eid in evict_ids:
                crel["scores"].pop(eid, None)

        snapshot["cycle"] = cycle + 1

        # Save updated state
        with open(state_file, "w") as f:
            _json.dump(snapshot, f)

        if run_hooks and items_dict:
            automated_hooks(state_dir, items_dict, cycle, cfg)

    except Exception as e:
        print(f"[wmtm_context] WARN fast-path: {type(e).__name__}: {e}", file=sys.stderr)

    return context


# ── Track P: recall/context plumbing ─────────────────────────────────

def setting(cfg, key):
    """Flags value with the runtime_config SPEC default when cfg lacks it (cfg may be {} after a failed resolve)."""
    if cfg and key in cfg:
        return cfg[key]
    from .runtime_config import SPEC
    return SPEC[key][2]


def protect_settings(cfg):
    """-> {"turns", "s"} for cleanup_stale_items / the fast path, or None (rc2 behaviour) when the flag is off."""
    try:
        if not setting(cfg, "cleanup_protect_recent"):
            return None
        return {"turns": max(0, int(setting(cfg, "cleanup_grace_turns"))),
                "s": max(0.0, float(setting(cfg, "cleanup_grace_s")))}
    except (TypeError, ValueError):
        return None


def is_recent_recall(recalled_at, recalled_cycle, cycle, now, protect):
    """True if an item recalled at (recalled_at, recalled_cycle) is still within the grace window.  The current
    cycle always counts (grace_turns 0 still protects the turn that recalled it)."""
    if not protect or not recalled_at or recalled_at <= 0:
        return False
    try:
        if recalled_cycle is not None and int(recalled_cycle) >= 0 and cycle - int(recalled_cycle) <= protect["turns"]:
            return True
    except (TypeError, ValueError):
        pass
    return (now - float(recalled_at)) <= protect["s"]


def _weights(cfg):
    try:
        w = [float(x) for x in str(setting(cfg, "context_rank_weights")).split(",")]
        if len(w) == 2 and all(x >= 0 for x in w) and sum(w) > 0:
            return w[0], w[1]
    except (TypeError, ValueError):
        pass
    return 0.7, 0.3


def _age_str(age_secs):
    if age_secs is None or age_secs < 0:
        return "?"
    if age_secs < 3600:
        return f"{age_secs/60:.0f}m"
    if age_secs < 86400:
        return f"{age_secs/3600:.1f}h"
    return f"{age_secs/86400:.1f}d"


def _entries_from_items(items, now):
    """Plain display entries from WMTMItem objects (active-set order)."""
    out = []
    for it in items:
        if hasattr(it, "effective_age_seconds"):
            age = it.effective_age_seconds
        elif it.created_at > 0:
            age = now - it.created_at
        else:
            age = -1
        out.append({"id": it.id, "src": it.source_type, "sti": float(it.attention.sti), "util": float(it.utility),
                    "age": age, "content": it.content or "", "total": float(it.attention.total)})
    return out


def _display_ts(d):
    created = d.get("created_at", 0)
    origin_ts = d.get("origin_timestamp", 0)
    display_ts = created
    if origin_ts > 0:
        display_ts = min(origin_ts, created) if created > 0 else origin_ts
    return display_ts


def _entries_from_dicts(items_dict, now):
    """Plain display entries from persisted item dicts (fast path)."""
    out = []
    for d in items_dict.values():
        ts = _display_ts(d)
        att = d.get("attention", {}) or {}
        out.append({"id": d.get("id"), "src": d.get("source_type", "unknown"), "sti": float(att.get("sti", 0) or 0),
                    "util": float(d.get("utility", 0) or 0), "age": (now - ts) if ts > 0 else -1,
                    "content": d.get("content", "") or "", "total": _att_total(d)})
    return out


def _render_rc2_from_dicts(items_dict, now, cycle):
    """rc2 fast-path block (context_rank off): top 15 by STI, 200 chars each."""
    sorted_items = sorted(items_dict.values(), key=lambda it: it.get("attention", {}).get("sti", 0),
                          reverse=True)[:15]
    lines = []
    for item in sorted_items:
        src = item.get("source_type", "unknown")
        att = item.get("attention", {})
        sti = att.get("sti", 0)
        util = item.get("utility", 0)
        ts = _display_ts(item)
        age_str = _age_str(now - ts) if ts > 0 else "?"
        content = item.get("content", "")[:200]
        lines.append(f"  [{src} sti={sti:.1f} util={util:.1f} age={age_str}] {content}")
    header = f"[WMTM Active Working Memory ({len(items_dict)} items, showing top {len(sorted_items)}, cycle {cycle})]"
    return header + "\n" + "\n".join(lines)


_REQ_TERMS_MAX = 60


def lexical_relevance(text, terms, tokenize=None):
    """Request relevance of a text without a journal cluster (derived conclusions): sum of the request terms'
    weights it contains (terms = {term: idf}).  Compound tokens (a_b_c) also match by part."""
    if not terms or not text:
        return 0.0
    if tokenize is None:
        from .recall_bridge import RecallBridge
        tokenize = RecallBridge._tokenize
    toks = tokenize(text.replace("_", " ")) | tokenize(text)
    return float(sum(w for t, w in terms.items() if t in toks))


def request_relevance(store, bridge, user_msg, recall_scores=None, stim_scores=None, cycle=0):
    """Track P: per-item relevance (0-1) to the current request.

    Recalled items: their recall / relevance-stimulus score (RecallBridge._score_cluster; the higher of the two).
    Other items (derived conclusions, tool derives): IDF-weighted overlap of their text with the request terms,
    on the same scale.  Normalised by the best score.  -> the dict persisted as snapshot["context_rel"], also read
    by the automated fast path: {"cycle", "scores": {id: rel}, "terms": {term: idf}, "smax"}."""
    try:
        qterms = bridge._tokenize(user_msg) if bridge is not None else set()
    except Exception:
        qterms = set()
    if not qterms:
        return {"cycle": cycle, "scores": {}, "terms": {}, "smax": 0.0}
    terms = {}
    for t in qterms:
        try:
            terms[t] = float(bridge._idf(t))
        except Exception:
            terms[t] = 1.0
    terms = dict(sorted(terms.items(), key=lambda kv: -kv[1])[:_REQ_TERMS_MAX])
    raw = {}
    for src in (recall_scores or {}), (stim_scores or {}):
        for k, v in src.items():
            if v and v > 0:
                raw[k] = max(raw.get(k, 0.0), float(v))
    for it in store.get_active_set():
        if it.id in raw or it.source_type in ("recalled", "user"):
            continue
        s = lexical_relevance(it.content, terms, bridge._tokenize)
        if s > 0:
            raw[it.id] = s
    smax = max(raw.values(), default=0.0)
    scores = {k: round(v / smax, 4) for k, v in raw.items()} if smax > 0 else {}
    return {"cycle": cycle, "scores": scores, "terms": {k: round(v, 3) for k, v in terms.items()},
            "smax": round(smax, 4)}


def rank_entries(entries, context_rel, cfg):
    """Track P: order display entries by w_rel*relevance + w_sti*STI/max STI (source_type=user items, the request
    itself, are never shown).  The best context_min_request_items entries by relevance come first; when a request
    is known, other entries scoring below context_min_score are dropped."""
    rel = dict(((context_rel or {}).get("scores") or {}))
    terms = (context_rel or {}).get("terms") or {}
    smax = float((context_rel or {}).get("smax") or 0.0)
    ents = [e for e in entries if e["src"] != "user"]
    if terms and smax > 0:                       # derived items admitted after the request (automated admit)
        for e in ents:
            if e["id"] not in rel and e["src"] not in ("recalled", "user"):
                try:
                    s = lexical_relevance(e["content"], terms)
                except Exception:
                    s = 0.0
                if s > 0:
                    rel[e["id"]] = min(1.0, s / smax)
    w_rel, w_sti = _weights(cfg)
    top_sti = max((e["sti"] for e in ents), default=0.0) or 1.0
    for e in ents:
        e["rel"] = float(rel.get(e["id"], 0.0))
        e["score"] = w_rel * e["rel"] + w_sti * max(0.0, e["sti"]) / top_sti
    n_req = max(0, int(setting(cfg, "context_min_request_items")))
    by_rel = sorted((e for e in ents if e["rel"] > 0), key=lambda e: (-e["rel"], -e["score"]))[:n_req]
    pinned = {e["id"] for e in by_rel}
    rest = sorted((e for e in ents if e["id"] not in pinned), key=lambda e: (-e["score"], -e["total"]))
    if by_rel:                                   # a request is known: drop weak, irrelevant filler (frees budget)
        floor = float(setting(cfg, "context_min_score"))
        rest = [e for e in rest if e["score"] >= floor]
    return by_rel + rest


def _clip(text, n, terms=None):
    """Whitespace-collapsed text cut to n chars.  With request terms ({term: weight}), a long text shows its opening
    (date/kind) plus the window that holds the most request-term weight, so the fact the request needs is not lost
    past the cut."""
    text = " ".join(str(text).split())
    if len(text) <= n:
        return text
    plain = text[:max(0, n - 1)].rstrip() + "…"
    if not terms or n < 160:
        return plain
    low = text.lower()

    def weight(a, b):
        seg = low[a:b]
        return sum(w for t, w in terms.items() if t in seg)
    cut = low.find(". ", 0, 90)
    head = text[:cut + 1] if 20 <= cut else text[:60].rsplit(" ", 1)[0]
    span = n - len(head) - 4                       # head + " … " + window + "…" <= n
    best, best_w = 0, weight(0, n - 1)
    starts = [0] + [i + 1 for i in range(len(head), len(text) - 40) if text[i] == " "]
    for a in starts[::3]:
        w = weight(a, a + span)
        if w > best_w + 1e-9:
            best, best_w = a, w
    if best < n // 3:
        return plain
    # the first window with the best weight ends at a term: start it shortly before the first term instead
    hits = [low.find(t, best, best + span) for t in terms]
    first = min((h for h in hits if h >= 0), default=best)
    for a in starts:
        if a >= max(best, first - 60):
            if weight(a, a + span) >= best_w - 1e-9:
                best = a
            break
    window = text[best:best + span].rstrip()
    return head + " … " + window + ("…" if best + span < len(text) else "")


def render_ranked(entries, context_rel, cycle, cfg):
    """Track P block: ranked entries, at most context_max_items, context_total_chars of item text in all; each item
    gets an equal share of the budget, capped at context_item_chars (floor 250).  Long items show their
    request-relevant window (_clip).  Same header as rc2 (adapters key on "[WMTM Active Working Memory").
    -> (text | None, shown ids)."""
    ranked = rank_entries(entries, context_rel, cfg)
    if not ranked:
        return None, []
    max_items = max(1, int(setting(cfg, "context_max_items")))
    budget = max(250, int(setting(cfg, "context_total_chars")))
    n = min(max_items, len(ranked))
    per = max(250, min(int(setting(cfg, "context_item_chars")), budget // n))
    terms = (context_rel or {}).get("terms") or None
    lines, shown, used = [], [], 0
    for e in ranked:
        if len(shown) >= max_items:
            break
        room = budget - used
        if room < 120 and shown:
            break
        text = _clip(e["content"], min(per, room), terms if e.get("rel") else None)
        used += len(text)
        rel_tag = f" rel={e['rel']:.2f}" if e.get("rel") else ""
        lines.append(f"  [{e['src']} sti={e['sti']:.1f} util={e['util']:.1f} age={_age_str(e['age'])}{rel_tag}] {text}")
        shown.append(e["id"])
    total = sum(1 for e in entries if e["src"] != "user")
    header = f"[WMTM Active Working Memory ({total} items, showing top {len(shown)}, cycle {cycle})]"
    return header + "\n" + "\n".join(lines), shown


def format_context(store, cycle, cfg=None, context_rel=None):
    """User-path block: Track P ranking when context_rank is on, else rc2 format_active_context.
    -> (text | None, shown ids) (shown ids get F17 passive utility)."""
    if not setting(cfg, "context_rank"):
        text = format_active_context(store, cycle)
        return text, [it.id for it in store.get_active_set()[:15]] if text else []
    import time as _t
    items = store.get_active_set()
    if not items:
        return None, []
    return render_ranked(_entries_from_items(items, _t.time()), context_rel, cycle, cfg)


def admit_request_item(store, user_msg, cycle, cfg, source=None):
    """Track P: the current real request as a source_type=user item (feeds request-overlap goal ranking in the
    shadow worker; never displayed, never written back).  Earlier request items are evicted.  -> item or None.
    Track Q: the item carries source_meta = the normalised request source (wmtm.request_source.normalise) plus
    first_person="speaker" (it is the human's own text: I/me/my = the requester, never the bot)."""
    if not setting(cfg, "request_item") or not user_msg:
        return None
    import hashlib
    text = " ".join(user_msg.split())[:max(20, int(setting(cfg, "request_item_chars")))]
    if not text:
        return None
    iid = "user-" + hashlib.md5(text.encode("utf-8")).hexdigest()[:12]
    for it in list(store.get_active_set()):
        if it.source_type == "user" and it.id != iid:
            store.evict(it.id)
    item = store.admit(iid, text, source_type="user", initial_sti=5.0)
    item.mark_recalled(cycle)
    meta = dict(source) if isinstance(source, dict) else {}
    meta["first_person"] = "speaker"
    item.source_meta = meta
    return item
