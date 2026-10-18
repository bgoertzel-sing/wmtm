"""Derived-belief candidate passed from a reasoner (PeTTaChainer, GoalChainer) to WMTM admission.

Track L: moved here from the removed Python PLN module (wmtm/inference.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class InferenceCandidate:
    """A derived belief candidate for admission to WMTM."""
    content: str
    confidence: float
    derived_from: list[str]
    inference_type: str              # e.g. 'pc_deduction', 'goalchainer_decision'
    triple: Optional[Any] = None     # legacy field (regex triples are gone); always None now
    initial_sti: float = 0.0
    provenance: Optional[dict] = None   # reasoner provenance (PeTTaChainer STV + proof term)
