"""F1 section 11 (t-2026-11-06-wmtm-f1-memory): integration with premises BELOW strength 1.0.

PR #5's integration tests fed every premise at (1.0, 0.9), which hid the engine's confidence loss: two premises at
(0.9, 0.8) / (0.8, 0.7) give the conclusion c ~ 0.02.  These tests run the real worker (vendored PeTTa/PeTTaChainer;
skipped without it) and check that such an answer is proved, keeps the engine TV, and is admitted.
Control: the same pipeline with premises at 1.0 yields c far above the old MIN_CONFIDENCE 0.05 cutoff, so a 1.0-only
test cannot catch that regression; the sub-1.0 test does."""
import json, os, re, subprocess, sys
import pytest
from wmtm import pc_admit, pc_shadow, runtime_config as rc
from wmtm.store import WMTMStore

_CFG = rc.resolve()
HAVE_PC = os.path.isdir(os.path.join(_CFG["petta_dir"], "python")) and os.path.isdir(os.path.join(_CFG["pettachainer_dir"], "pettachainer"))
SYN = ["cat is a mammal", "mammal is a animal"]
OLD_MIN_CONFIDENCE = 0.05            # the cutoff removed by F1 item 3 (5a8f0c0)
_PAT = re.compile(r"^\s*(\w+) is an? (\w+)\s*$")


def _install(monkeypatch, tvs):
    def lookup(items, cache_dir=None):
        out = {}
        for k, it in enumerate(items):
            m = _PAT.match(it.content)
            if m:
                s, c = tvs[k % len(tvs)]
                out[it.id] = ["(: f_%s_%s (Inheritance %s %s) (STV %s %s))" % (m.group(1), m.group(2), m.group(1), m.group(2), s, c)]
        return out
    monkeypatch.setattr(pc_shadow, "_cache_lookup", lookup)


def _store():
    st = WMTMStore()
    for i, t in enumerate(SYN):
        st.admit("s%d" % i, t, source_type="recalled", initial_sti=1.0 - i * 0.01)
    return st


def _run(tmp_path, monkeypatch, tvs):
    _install(monkeypatch, tvs)
    st = _store()
    spec = pc_shadow.build_snapshot(st, cycle=1)
    sp = tmp_path / "spec.json"; sp.write_text(json.dumps(spec)); out = tmp_path / "shadow.jsonl"
    code = subprocess.run([sys.executable, "-m", "wmtm.workers.pc_shadow", "--spec", str(sp), "--out", str(out)],
                          env=rc.worker_env(_CFG), cwd=rc.DIST_ROOT, timeout=300).returncode
    rec = json.loads(out.read_text().strip().splitlines()[-1])
    assert code == 0 and rec["status"] == "ok" and rec["canary"]["ok"] and not rec["neg"]["ok"], rec.get("status")
    q = {x["goal"]: x for x in rec["queries"]}["(Inheritance cat animal)"]
    assert q["ok"] and pc_admit.is_derivation(q["proof"]) and "inh_trans" not in q["proof"]   # F3 v2: engine-native chain, no wmtm rule
    cands, info = pc_admit.load_candidates({"shadow_dir": str(tmp_path), "reasoner_max_admit": 5}, st)
    return q["stv"], {c.content: c for c in (cands or [])}


@pytest.mark.skipif(not HAVE_PC, reason="vendored PeTTa / PeTTaChainer not present")
def test_sub_unit_premises_low_confidence_answer_admitted(tmp_path, monkeypatch):
    stv, cands = _run(tmp_path, monkeypatch, [(0.6, 0.4), (0.6, 0.3)])   # F3 v2: native chain keeps more c ((0.9,0.8)/(0.8,0.7) -> 0.195); these premises pass gate_min_conf 0.3 and give s 0.56 c ~0.021
    assert stv[1] < OLD_MIN_CONFIDENCE                       # the engine's confidence loss is visible
    c = cands["cat is a animal"]
    assert c.provenance["stv"] == stv and c.confidence == stv[1] and sorted(c.derived_from) == ["s0", "s1"]   # engine TV kept (F3 v2: native proof lists premises in engine order)
    # this test catches the regression: the old cutoff would have dropped the answer
    assert not (c.confidence >= OLD_MIN_CONFIDENCE)


@pytest.mark.skipif(not HAVE_PC, reason="vendored PeTTa / PeTTaChainer not present")
def test_control_unit_premises_hide_the_regression(tmp_path, monkeypatch):
    stv, cands = _run(tmp_path, monkeypatch, [(1.0, 0.9)])
    c = cands["cat is a animal"]
    # with premises at 1.0 the answer clears the old 0.05 cutoff: a 1.0-only test passes with or without the regression
    assert c.provenance["stv"] == stv and c.confidence >= OLD_MIN_CONFIDENCE
