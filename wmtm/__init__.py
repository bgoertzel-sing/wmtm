"""Working Medium-Term Memory (WMTM) — mutable active layer between STM and LTM.

Modules:
  item:          WMTMItem dataclass
  attention:     ECAN AttentionValue with decay
  store:         WMTMStore bounded-capacity mutable store
  forgetting:    ForgettingPolicy for eviction decisions
  candidate:     InferenceCandidate (reasoner output admitted into WMTM)
  utility:       UtilityTracker for use/miss tracking
  forgetting_log: ForgettingLog to prevent re-derivation
  writeback:     WritebackManager for LTM promotion
  orchestrator:  WMTMOrchestrator tying it all together
  recall_bridge: Bridge from LTM journal to WMTM
  api:           WMTM / WMTMConfig public interface
  context:       generic per-turn logic used by api
  journal:       default PeTTa journal (read_lines/append)
"""
# Lazy exports (PEP 562): importing wmtm (e.g. for wmtm.api's automated fast
# path) must not pull in heavy modules. Track L: the Python PLN engine is removed.
_EXPORTS = {
    "WMTMItem": ".item", "AttentionValue": ".attention", "WMTMStore": ".store",
    "ForgettingPolicy": ".forgetting",
    "InferenceCandidate": ".candidate",
    "UtilityTracker": ".utility", "UtilityRecord": ".utility",
    "ForgettingLog": ".forgetting_log", "ForgetRecord": ".forgetting_log",
    "WritebackManager": ".writeback", "WritebackCandidate": ".writeback",
    "WMTMOrchestrator": ".orchestrator", "CycleResult": ".orchestrator",
    "RecallBridge": ".recall_bridge", "LTMCluster": ".recall_bridge",
    "WMTM": ".api", "WMTMConfig": ".api",
}


def __getattr__(name):
    mod = _EXPORTS.get(name)
    if mod is None:
        raise AttributeError(f"module 'wmtm' has no attribute {name!r}")
    import importlib
    val = getattr(importlib.import_module(mod, __name__), name)
    globals()[name] = val
    return val


__all__ = [
    "WMTMItem",
    "AttentionValue",
    "WMTMStore",
    "ForgettingPolicy",
    "InferenceCandidate",
    "UtilityTracker",
    "UtilityRecord",
    "ForgettingLog",
    "ForgetRecord",
    "WritebackManager",
    "WritebackCandidate",
    "WMTMOrchestrator",
    "CycleResult",
    "RecallBridge",
    "LTMCluster",
    "WMTM",
    "WMTMConfig",
]
