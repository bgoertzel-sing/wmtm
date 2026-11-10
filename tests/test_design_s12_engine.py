"""t-2026-11-10-wmtm-design-gap-check: s12 tests on the real reasoner (PeTTaChainer b6aacc68 on PeTTa 3681b9b).

Synthetic data only.  The notes are parsed by the test semparse fake (tests/_fake_semparse.py), as in
tests/test_pc_shadow.py; the PeTTaChainer worker (wmtm.workers.pc_shadow) runs for real.  Point WMTM_PC_PETTA /
WMTM_PC_VENDOR (and WMTM_SWIPL_BIN) at the vendored runtime; without it the tests skip ("not run: environment").
Set WMTM_GAPCHECK_ENGINE_OUT to a file to keep the worker record.
"""
import hashlib
import json
import os
import subprocess
import sys

import pytest

from wmtm import pc_admit, pc_shadow, runtime_config as rc
from wmtm.orchestrator import WMTMOrchestrator
from wmtm.store import WMTMStore

_CFG = rc.resolve()
HAVE_PC = os.path.isdir(os.path.join(_CFG["petta_dir"], "python")) and \
    os.path.isdir(os.path.join(_CFG["pettachainer_dir"], "pettachainer"))
pytestmark = pytest.mark.skipif(not HAVE_PC, reason="not run: environment (vendored PeTTa / PeTTaChainer not present)")

SYN = ["cat is a mammal", "mammal is a animal", "rain -> wet", "wet -> slippery"]


@pytest.fixture(autouse=True)
def _semparse(monkeypatch):
    import _fake_semparse; _fake_semparse.install(monkeypatch)


def _store(texts):
    st = WMTMStore()
    for i, t in enumerate(texts):
        st.admit("s%d" % i, t, source_type="recalled", initial_sti=5.0 - i * 0.01)
    return st


_SKIP_DIRS = {"__pycache__", ".pytest_cache", ".git"}


def tree_sha256(root):
    """Content hash of a source tree: sha256 over sorted 'relpath\\0sha256(file)\\n' lines.  Byte caches
    (__pycache__, *.pyc) and .git are left out, so a tree that has been run hashes the same as a fresh extract of
    the same tarball.  reports/t-2026-11-10-wmtm-design-gap-check/tree_sha256.py computes the same value."""
    h = hashlib.sha256()
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x not in _SKIP_DIRS)
        for fn in sorted(files):
            if fn.endswith(".pyc"):
                continue
            p = os.path.join(d, fn)
            if os.path.islink(p):
                data = ("link:" + os.readlink(p)).encode()
            else:
                with open(p, "rb") as f:
                    data = f.read()
            h.update(("%s\0%s\n" % (os.path.relpath(p, root), hashlib.sha256(data).hexdigest())).encode())
    return h.hexdigest()


def _engine_identity():
    """Which engine trees the worker was given (pc_shadow.py:33 and :50 take them from this config)."""
    return {"pettachainer_dir": os.path.realpath(_CFG["pettachainer_dir"]),
            "pettachainer_tree_sha256": tree_sha256(_CFG["pettachainer_dir"]),
            "petta_dir": os.path.realpath(_CFG["petta_dir"]),
            "petta_tree_sha256": tree_sha256(_CFG["petta_dir"]),
            "swipl_bin": _CFG.get("swipl_bin"),
            "stated_pins": {"pettachainer": os.environ.get("WMTM_GAPCHECK_PC_SHA"),
                            "petta": os.environ.get("WMTM_GAPCHECK_PETTA_SHA")}}


def _dump_round(rec, items, info):
    return {"rec": rec, "admit_info": info,
            "admitted": [{"id": i.id, "content": i.content, "derived_from": i.derived_from,
                          "provenance": i.provenance} for i in items]}


def _run_worker(tmp_path, spec, tag):
    sp = tmp_path / ("spec-%s.json" % tag); sp.write_text(json.dumps(spec)); out = tmp_path / ("shadow-%s.jsonl" % tag)
    code = subprocess.run([sys.executable, "-m", "wmtm.workers.pc_shadow", "--spec", str(sp), "--out", str(out)],
                          env=rc.worker_env(_CFG), cwd=rc.DIST_ROOT, timeout=300).returncode
    return code, json.loads(out.read_text().strip().splitlines()[-1])


def _admit_round(orch, tmp_path, tag):
    spec = pc_shadow.build_snapshot(orch.store, cycle=orch._cycle)
    code, rec = _run_worker(tmp_path, spec, tag)
    assert code == 0 and rec["status"] == "ok" and rec["canary"]["ok"], rec.get("status")
    d = tmp_path / ("shadow-dir-%s" % tag); d.mkdir()
    pc_admit.write_admit_file(str(d), rec, spec)
    orch.pc_admit_state = {}
    items, info = orch.admit_reasoner(dict(_CFG, shadow_dir=str(d), reasoner="pettachainer"))
    return rec, items or [], info


def test_engine_s12_2_full_cycle_and_no_rederivation(tmp_path):
    """s12.2 on the engine: deduction proved by PeTTaChainer -> admitted as derived with derived_from = store ids ->
    unused -> decays and is forgotten -> the next engine run proves it again, and the forgetting log keeps it out."""
    orch = WMTMOrchestrator(_store(SYN))
    rec, items, info = _admit_round(orch, tmp_path, "1")
    out = os.environ.get("WMTM_GAPCHECK_ENGINE_OUT")
    record = {"engine": _engine_identity(), "round1": _dump_round(rec, items, info)}
    if out:
        with open(out, "w") as f:
            json.dump(record, f, indent=1, default=str)
    proved = {q["goal"] for q in rec["queries"] if q["ok"]}
    assert "(Inheritance cat animal)" in proved                                     # deduction runs
    ded = [i for i in items if "cat" in i.content and "animal" in i.content]
    assert ded, (info, [i.content for i in items])
    d = ded[0]
    assert d.source_type == "derived" and set(d.derived_from) <= {"s0", "s1", "s2", "s3"} and d.derived_from
    assert d.provenance["reasoner"] == "pettachainer" and d.id in orch.store        # back in the active set
    for iid in ("s0", "s1", "s2", "s3"):                                           # keep the premises alive
        orch.store.get(iid).attention.sti = 50.0
    for _ in range(60):
        orch.forget_phase()
        if d.id not in orch.store:
            break
    assert d.id not in orch.store and orch.forget_log.is_forgotten(d.content, list(d.derived_from))
    rec2, items2, info2 = _admit_round(orch, tmp_path, "2")
    if out:                                     # round 2 (re-proved, then dropped as known) kept in the artifact too
        record["between_rounds"] = {"forgotten_item": d.id, "forgotten_content": d.content,
                                    "forgotten_sources": list(d.derived_from),
                                    "in_forget_log": orch.forget_log.is_forgotten(d.content, list(d.derived_from))}
        record["round2"] = _dump_round(rec2, items2, info2)
        with open(out, "w") as f:
            json.dump(record, f, indent=1, default=str)
    assert "(Inheritance cat animal)" in {q["goal"] for q in rec2["queries"] if q["ok"]}
    assert not any(i.content == d.content for i in items2), info2
    assert (info2.get("dropped") or {}).get("known", 0) >= 1 or info2.get("skipped") == "no_candidates"


def test_engine_s3_4_which_inference_kinds_run(tmp_path):
    """s3.4 / s9.1: record which rule kinds appear in the engine's proofs.  Deduction must; induction and abduction
    are reported, not asserted (the report says whether they appear)."""
    orch = WMTMOrchestrator(_store(SYN))
    spec = pc_shadow.build_snapshot(orch.store, cycle=0)
    code, rec = _run_worker(tmp_path, spec, "k")
    assert code == 0 and rec["status"] == "ok"
    proofs = " ".join(str(q.get("proof") or "") for q in rec["queries"] if q["ok"]).lower()
    kinds = {k: (k in proofs) for k in ("deduction", "induction", "abduction", "modusponens", "revision")}
    out = os.environ.get("WMTM_GAPCHECK_ENGINE_OUT")
    if out:
        with open(out + ".kinds.json", "w") as f:
            json.dump({"kinds_in_proofs": kinds, "proved": [(q["goal"], q.get("proof")) for q in rec["queries"]
                                                             if q["ok"]]}, f, indent=1, default=str)
    assert any(q["ok"] for q in rec["queries"])
