"""Track R: legitimacy as a VETO only.  Authority rules become GoalChainer deontic Norms (forbid) and are resolved
with goal_chainer.deontic.resolve_norms when that package is importable (flags key goalchainer_src = its src dir;
MesTTo's repo is not modified), else with an identical local resolver.  Discouragement product: 0 if blocked,
else the product of soft discounts (a repeat of a recently logged proposal: 0.5)."""
from __future__ import annotations

import sys
from collections import namedtuple

# (rule id, effect it forbids, reason, priority)
RULES = (
    ("no_live_change", "live_change", "no live changes without approval", 30),
    ("no_push", "push", "no push without approval", 30),
    ("no_git_memory", "git_memory", "no memories in git", 30),
    ("read_only", "write", "phase 1 is read-only", 20),
)
AUTONOMOUS_EFFECTS = ("message", "write", "live_change", "git_memory", "push")
REPEAT_DISCOUNT = 0.5

_Norm = namedtuple("_Norm", "id mode target_action reason priority")
_Res = namedtuple("_Res", "status reasons priority")


def _local_resolve(action_id, norms):
    app = [n for n in norms if n.target_action == action_id]
    if not app:
        return _Res("unregulated", (), 0)
    mp = max(n.priority for n in app); top = [n for n in app if n.priority == mp]
    modes = {n.mode for n in top}; reasons = tuple("%s:%s" % (n.mode, n.reason) for n in top)
    if "forbid" in modes and modes & {"permit", "oblige"}:
        return _Res("conflict", reasons, mp)
    if "forbid" in modes:
        return _Res("forbidden", reasons, mp)
    return _Res("obligated" if "oblige" in modes else "permitted", reasons, mp)


_CACHE = {}


def deontic_impl(cfg=None):
    src = str((cfg or {}).get("goalchainer_src") or "")
    if src in _CACHE:
        return _CACHE[src]
    if src and src not in sys.path:
        sys.path.append(src)
    try:
        from goal_chainer.deontic import resolve_norms
        from goal_chainer.models import Norm
        r = (resolve_norms, Norm, "goal_chainer")
    except Exception:
        r = (_local_resolve, _Norm, "local")
    _CACHE[src] = r
    return r


def evaluate(cand, ctx=None, cfg=None):
    ctx = ctx or {}
    resolve, Norm, impl = deontic_impl(cfg)
    aid = cand["key"]; eff = set(cand.get("effects") or ())
    approved = set(ctx.get("approved") or ())
    norms = []
    for rid, e, reason, prio in RULES:
        if e in eff and not (rid in ("no_live_change", "no_push") and aid in approved):
            norms.append(Norm(id=rid, mode="forbid", target_action=aid, reason=reason, priority=prio))
    if ctx.get("autonomous") and eff & set(AUTONOMOUS_EFFECTS):
        norms.append(Norm(id="no_autonomous_action", mode="forbid", target_action=aid,
                          reason="never act in autonomous turns", priority=40))
    res = resolve(aid, tuple(norms))
    blocked = res.status in ("forbidden", "conflict")
    disc = {}
    if aid in set(ctx.get("recent") or ()):
        disc["repeat"] = REPEAT_DISCOUNT
    d = 0.0 if blocked else 1.0
    for v in disc.values():
        d *= v
    return {"d": d, "status": res.status, "rules": [n.id for n in norms], "reasons": list(res.reasons),
            "discounts": disc, "impl": impl}
