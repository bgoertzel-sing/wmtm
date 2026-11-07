"""GoalChainer Bridge: GoalChainer decisions -> WMTM candidates.

F2 (review section 10): the v1 feed is removed.  It sent the active set as {id, content, sti} memory_items to
GoalChainer v1 (goal_chainer.pipeline.solve_incident), whose parse_memory_evidence reads only items with a
goalchainer_slot and an (Acceptable <action>) STV / EvidencePacket EC atom: it read 0 of the items sent.  WMTM notes
are not action-acceptability evidence, so encoding them as such would invent truth values.  run_goalchainer_over_wmtm
(the orchestrator's use_goalchainer phase, off by default) now sends nothing and returns no candidates.  WMTM goals
run on GoalChainer v2 in wmtm/goals.  goalchainer_result_to_candidates stays (live_tool_bridge uses it).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Optional

from .store import WMTMStore
from .candidate import InferenceCandidate


@dataclass
class GoalChainerDecision:
    """A single decision from GoalChainer, normalized for WMTM consumption."""
    action_id: str
    label: str
    status: str           # recommended, permitted, forbidden, obligated
    score: float
    motivation: str = ""
    evidence_ids: list = None

    def __post_init__(self):
        """Initialize evidence_ids list if not provided."""
        if self.evidence_ids is None:
            self.evidence_ids = []


def goalchainer_result_to_candidates(
    result: dict,
    cycle: int = 0,
    source_ids: Optional[list] = None,
) -> list:
    """Convert GoalChainer decisions into WMTM InferenceCandidates.

    Each ranked action becomes a candidate with:
    - content: human-readable decision summary
    - confidence: from score
    - inference_type: goalchainer_decision
    - initial_sti: proportional to score
    - derived_from: evidence IDs from WMTM
    """
    if source_ids is None:
        source_ids = []

    candidates = []
    decisions = result.get('decisions', [])

    for i, dec in enumerate(decisions):
        action_id = dec.get('action_id', f'action-{i}')
        label = dec.get('label', action_id)
        status = dec.get('status', 'unregulated')
        score = float(dec.get('score', 0.5))

        # Build content string
        content = f"GoalChainer decision: {action_id} ({label}) -- status={status}, score={score:.3f}"

        # Confidence from score (clamped to [0, 1])
        confidence = max(0.0, min(1.0, score))

        # Initial STI: recommended/obligated get boost
        sti_boost = 1.0
        if status in ('recommended', 'obligated'):
            sti_boost = 2.0
        elif status == 'forbidden':
            sti_boost = 0.3

        initial_sti = score * sti_boost * 10.0  # scale to WMTM STI range

        candidates.append(InferenceCandidate(
            content=content,
            confidence=confidence,
            derived_from=list(source_ids),
            inference_type='goalchainer_decision',
            triple=None,
            initial_sti=initial_sti,
        ))

    return candidates


def run_goalchainer_over_wmtm(
    store: WMTMStore,
    request: str,
    max_evidence: int = 20,
) -> list:
    """Removed v1 feedback loop (F2, review section 10): sends nothing to GoalChainer v1 and returns [] (see the
    module docstring).  Kept so WMTMOrchestrator(use_goalchainer=True) still runs."""
    return []
