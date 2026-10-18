"""Track L test helper: feed a PeTTaChainer admit file to an orchestrator (replaces the removed Python PLN derivations)."""
import json, time
from wmtm import pc_admit, pc_shadow


def chain(a, b, c, s1, s2, stv=(0.9, 0.6)):
    """PeTTaChainer result for a -> b, b -> c  |-  a -> c, sourced from WMTM items s1, s2."""
    return {"goal": f"(Implies {a} {c})", "stv": list(stv), "proof": f"(imp_trans {s1} {s2})", "s": 0.1, "sources": [s1, s2]}


def enable_pc(orch, tmp_path, monkeypatch, results):
    monkeypatch.setenv("WMTM_REASONER", "pettachainer")
    monkeypatch.setenv("WMTM_PC_SHADOW_DIR", str(tmp_path))
    monkeypatch.delenv("WMTM_PC_SHADOW", raising=False)
    monkeypatch.setattr(pc_shadow, "maybe_launch", lambda *a, **k: None)
    orch.runtime_state_dir = str(tmp_path)
    doc = {"ts": time.time(), "spec_ts": time.time(), "cycle": 0, "status": "ok", "canary_ok": True, "results": results}
    (tmp_path / pc_admit.ADMIT_FILE).write_text(json.dumps(doc))
    return orch
