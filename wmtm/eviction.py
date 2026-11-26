"""M-05 (design s7.1c / s7.1b / s12.1): composite capacity-eviction score, behind the composite_eviction flag.

composite = STI * w_sti + utility * w_util + LTI * w_lti      (design s7.1c, docs/wmtm_design_doc.txt l.270-274)
derived items: composite / derived_eviction_penalty           (s7.1c "1.5x penalty multiplier"; s10 default 1.5)
The lowest composite is evicted first.  Both capacity paths (store.admit overflow and
ForgettingPolicy._evict_over_capacity) rank with composite_score when the flag is on.

With the flag off, eviction_cfg() returns None and every caller keeps its pre-M-05 code path unchanged.
"""
from __future__ import annotations

from typing import Optional

DEFAULT_WEIGHTS = (0.4, 0.4, 0.2)     # s7.1c: STI, utility, LTI
DEFAULT_DERIVED_PENALTY = 1.5         # s10 derived_eviction_penalty
DEFAULT_MIN_UTILITY = 2.0             # s10 min_utility (s7.1b age review)


def _weights(raw) -> tuple:
    try:
        if isinstance(raw, (list, tuple)):
            parts = [float(x) for x in raw]
        else:
            parts = [float(x) for x in str(raw).split(",")]
        if len(parts) == 3:
            return tuple(parts)
    except (TypeError, ValueError):
        pass
    return DEFAULT_WEIGHTS


def _num(raw, default: float) -> float:
    try:
        v = float(raw)
        return v if v == v and v not in (float("inf"), float("-inf")) else default
    except (TypeError, ValueError):
        return default


def eviction_cfg(cfg) -> Optional[dict]:
    """Resolved runtime config (or {}) -> normalised eviction settings, or None when composite_eviction is off."""
    from .runtime_config import SPEC

    def get(key):
        return cfg[key] if cfg and key in cfg else SPEC[key][2]

    if not get("composite_eviction"):
        return None
    pen = _num(get("derived_eviction_penalty"), DEFAULT_DERIVED_PENALTY)
    return {
        "weights": _weights(get("eviction_weights")),
        "derived_penalty": pen if pen > 0 else DEFAULT_DERIVED_PENALTY,
        "min_utility": _num(get("eviction_min_utility"), DEFAULT_MIN_UTILITY),
    }


def composite_score(item, cfg: Optional[dict] = None) -> float:
    """s7.1c composite of one item (lower = evicted first).  cfg: eviction_cfg() output; None -> design defaults."""
    if cfg is None:
        cfg = {"weights": DEFAULT_WEIGHTS, "derived_penalty": DEFAULT_DERIVED_PENALTY}
    w_sti, w_util, w_lti = cfg["weights"]
    av = item.attention
    score = av.sti * w_sti + item.utility * w_util + av.lti * w_lti
    if item.source_type == "derived":
        score = score / cfg["derived_penalty"]
    return score


def lowest(items, cfg: dict):
    """The item to evict under capacity pressure: lowest composite; ties -> first in insertion order."""
    return min(items, key=lambda it: composite_score(it, cfg))
