"""Build scratch Iter trees (original glue vs new adapter+package) and replay steps.

Original tree: transformations/wmtm_context.py, _petta_journal.py,
tools/wmtm_derive.py and the wmtm/ package exactly as at snapshot 83ea611.
New tree: adapters/iter_transformation.py installed as
transformations/wmtm_context.py, adapters/iter_tool_wmtm_derive.py as
tools/wmtm_derive.py, and this repo's wmtm package on sys.path.
Both trees get their own copy of memory/ (state + journal); live paths are
never touched (runner.py refuses any root under iter-port/).
"""
import json, os, re, shutil, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNNER = Path(__file__).resolve().parent / "runner.py"


def build_original_tree(dest, orig_src):
    dest, orig_src = Path(dest), Path(orig_src)
    for rel in ("transformations/wmtm_context.py", "_petta_journal.py", "tools/wmtm_derive.py"):
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(orig_src / rel, dest / rel)
    shutil.copytree(orig_src / "wmtm", dest / "wmtm", ignore=shutil.ignore_patterns("__pycache__"))
    return dest


def build_new_tree(dest):
    dest = Path(dest)
    (dest / "transformations").mkdir(parents=True, exist_ok=True)
    (dest / "tools").mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO / "adapters" / "iter_transformation.py", dest / "transformations" / "wmtm_context.py")
    shutil.copy(REPO / "adapters" / "iter_tool_wmtm_derive.py", dest / "tools" / "wmtm_derive.py")
    return dest


def seed_memory(root, state_text, journal_text):
    mem = Path(root) / "memory"
    (mem / "_journal").mkdir(parents=True, exist_ok=True)
    if state_text is not None:
        (mem / "_wmtm_state.json").write_text(state_text, encoding="utf-8")
    (mem / "_journal" / "journal.metta").write_text(journal_text, encoding="utf-8")
    (mem / "_wmtm_pending_derives.jsonl").write_text("")
    return len(journal_text)


def run(root, steps, mode, extra_path="", journal_base=0):
    """mode 'fresh': one process per step (how Iter runs transforms);
    'single': all steps in one process (singletons persist)."""
    root = Path(root)
    env = dict(os.environ, PYTHONHASHSEED="0", WMTM_REPLAY_JOURNAL_BASE=str(journal_base))
    env.pop("JOURNAL_DIR", None)
    env.pop("PYTHONPATH", None)
    batches = [[s] for s in steps] if mode == "fresh" else [steps]
    results = []
    for i, batch in enumerate(batches):
        sp, op = root / f".steps{i}.json", root / f".out{i}.json"
        sp.write_text(json.dumps(batch))
        p = subprocess.run([sys.executable, str(RUNNER), str(root), str(sp), str(op), str(extra_path)],
                           env=env, capture_output=True, text=True, timeout=600)
        if p.returncode != 0:
            raise RuntimeError(f"runner failed ({root}):\n{p.stdout}\n{p.stderr}")
        results += json.loads(op.read_text())
        sp.unlink(); op.unlink()
    return results


_HDR = re.compile(r"^\[WMTM Active Working Memory \((\d+) items, showing top (\d+), cycle (\d+)\)\]$")
_LINE = re.compile(r"^  \[(recalled|derived|unknown) sti=-?\d+\.\d util=-?\d+\.\d age=(\d+m|\d+\.\dh|\d+\.\dd|\?)\] ")


def structural_check(steps, results, seed_state, strict_cycle=True):
    """Experiment-sanity-gate check 2: refuse malformed per-step results.

    strict_cycle: every turn advances the persisted cycle by exactly 1.
    True for one-process-per-turn (how Iter runs). In single-process mode
    the original glue (and the API, identically) keeps a cached engine that
    does not see fast-path writes to the state file, so the cycle can step
    back; see README "Known quirks"."""
    prev_cycle = json.loads(seed_state)["cycle"] if seed_state else None
    for i, (st, r) in enumerate(zip(steps, results)):
        state_txt = r["files"]["memory/_wmtm_state.json"]
        state = json.loads(state_txt) if state_txt else None
        if st["kind"] == "derive":
            assert r["out"].startswith("Registered derived belief derived-"), (i, r["out"])
            assert json.loads(r["files"]["memory/_wmtm_pending_derives.jsonl"].splitlines()[-1])["note"] == st["note"]
            continue
        n_in = len(st["messages"])
        out = r["out"]
        assert out[:n_in] == st["messages"], f"step {i}: input messages altered"
        assert len(out) in (n_in, n_in + 1), f"step {i}: unexpected message count"
        if len(out) == n_in + 1:
            blk = out[-1]
            assert blk["role"] == "user"
            lines = blk["content"].split("\n")
            m = _HDR.match(lines[0])
            assert m, f"step {i}: bad header {lines[0]!r}"
            total, shown, cyc = map(int, m.groups())
            assert shown == min(total, 15) and len(lines) - 1 == shown, f"step {i}: shown/lines mismatch"
            assert all(_LINE.match(l) for l in lines[1:]), f"step {i}: malformed item line"
            assert "Traceback" not in r["stderr"]
        if strict_cycle and state is not None and prev_cycle is not None:
            assert state["cycle"] == prev_cycle + 1, f"step {i}: cycle {prev_cycle}->{state['cycle']}"
            assert len(state["store"]["items"]) <= state["store"]["capacity"]
        if state is not None:
            prev_cycle = state["cycle"]


def diff_results(a, b):
    """Return a list of human-readable differences between two result lists."""
    diffs = []
    if len(a) != len(b):
        return [f"length {len(a)} != {len(b)}"]
    for i, (x, y) in enumerate(zip(a, b)):
        for key in ("out", "stderr"):
            if x[key] != y[key]:
                diffs.append(f"step {i}: {key} differs")
        for k in x["files"]:
            if x["files"][k] != y["files"][k]:
                diffs.append(f"step {i}: file {k} differs")
    return diffs
