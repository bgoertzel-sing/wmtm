"""Track G: PeTTaChainer *shadow* run alongside the Python PLN phase.

Off by default (env WMTM_PC_SHADOW=1 enables).  The orchestrator calls maybe_launch(store, cycle) after the
Python PLN phase; this builds a top-K snapshot (K = WMTM_PC_SHADOW_K, default 200) of PLN atoms, records what
the Python PLN derived from the same atoms, writes a spec under .local-data/pc_shadow/ and launches a detached,
niced worker (scripts/pettachainer/pc_shadow_worker.py).  It NEVER waits on the worker, never admits anything
into WMTM and never raises: the shadow cannot change or slow down the live cycle beyond snapshot building.
At most one worker runs at a time (pidfile guard); a busy worker means the cycle is skipped, not queued.
"""
from __future__ import annotations
import json, os, re, subprocess, sys, tempfile, time

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.environ.get("WMTM_PC_SHADOW_DIR", os.path.join(W, ".local-data", "pc_shadow"))
WORKER = os.path.join(W, "scripts", "pettachainer", "pc_shadow_worker.py")
_NAME = re.compile(r"^(\w+)\(([a-z_][a-z0-9_-]*),([a-z_][a-z0-9_-]*)\)$")
# PLN relation -> MeTTa head.  Python "Implication" facts become (Implies a b): a bare (Implication a b)
# would be read by PeTTaChainer as a *rule*, not a fact.
HEAD = {"Inheritance": "Inheritance", "Implication": "Implies", "Similarity": "Similarity", "Evaluation": "Evaluation"}
TRANSITIVE = ("Inheritance", "Implies")


def enabled() -> bool:
    return os.environ.get("WMTM_PC_SHADOW", "0") == "1"


def atom_to_metta(atom, i):
    m = _NAME.match(atom.name)
    if not m or m.group(1) not in HEAD:
        return None
    s = min(1.0, max(0.0, float(atom.truth.strength))); c = min(0.99, max(0.0, float(atom.truth.confidence)))
    return "(: wm%d (%s %s %s) (STV %.4f %.4f))" % (i, HEAD[m.group(1)], m.group(2), m.group(3), s, c)


def build_snapshot(store, cycle=0, k=None):
    """-> dict spec (pure; no I/O).  Goals = 2-step chains over the transitive heads, plus what Python PLN derived."""
    from .pln_bridge import wmtm_to_pln_atoms
    from .pln import pln_inference_over_atoms
    k = int(k or os.environ.get("WMTM_PC_SHADOW_K", "200"))
    items = store.get_active_set()[:k]
    atoms = [a for a in wmtm_to_pln_atoms(items) if a.atom_type != "Concept"]
    metta, rel = [], set()
    for i, a in enumerate(atoms):
        s = atom_to_metta(a, i)
        if s:
            metta.append(s); m = _NAME.match(a.name); rel.add((HEAD[m.group(1)], m.group(2), m.group(3)))
    goals = []
    for h in TRANSITIVE:
        for (h1, a, b) in sorted(rel):
            for (h2, b2, c) in sorted(rel):
                g = "(%s %s %s)" % (h, a, c)
                if h1 == h2 == h and b == b2 and a != c and (h, a, c) not in rel and g not in goals:
                    goals.append(g)
    py = []
    try:
        for d in pln_inference_over_atoms(atoms):
            m = _NAME.match(d.name)
            if m and m.group(1) in HEAD:
                py.append({"goal": "(%s %s %s)" % (HEAD[m.group(1)], m.group(2), m.group(3)),
                           "s": round(d.truth.strength, 4), "c": round(d.truth.confidence, 4)})
    except Exception as e:  # Python PLN failure is recorded, not raised
        py = [{"error": type(e).__name__}]
    return {"cycle": cycle, "ts": time.time(), "k": k, "items": len(items), "atoms": metta, "goals": goals, "python_derived": py}


def _busy(pidfile):
    try:
        pid = int(open(pidfile).read().strip()); os.kill(pid, 0); return True
    except (OSError, ValueError):
        return False


def launch(spec, out_dir=None, worker=None):
    """Write spec, start a detached niced worker, return its pid (or None if skipped).  Never waits."""
    out_dir = out_dir or OUT; os.makedirs(out_dir, exist_ok=True)
    pidfile = os.path.join(out_dir, "worker.pid")
    if _busy(pidfile):
        return None
    fd, path = tempfile.mkstemp(prefix="spec_c%d_" % spec.get("cycle", 0), suffix=".json", dir=out_dir)
    with os.fdopen(fd, "w") as f:
        json.dump(spec, f)
    cmd = [sys.executable, "-u", worker or WORKER, "--spec", path, "--out", os.path.join(out_dir, "shadow.jsonl")]
    pre = ["nice", "-n", "19"] + (["ionice", "-c", "3"] if os.path.exists("/usr/bin/ionice") else [])
    p = subprocess.Popen(pre + cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         cwd=W, start_new_session=True, close_fds=True)
    with open(pidfile, "w") as f:
        f.write(str(p.pid))
    return p.pid


def maybe_launch(store, cycle=0):
    """Orchestrator hook.  Returns pid or None; swallows every error."""
    if not enabled():
        return None
    try:
        spec = build_snapshot(store, cycle)
        if not spec["atoms"]:
            return None
        return launch(spec)
    except Exception:
        return None
