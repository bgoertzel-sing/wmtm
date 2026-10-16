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


MAX_GOALS = 60
_FACTS_MEMO = {}
SP_HEADS = ("Inheritance", "Member", "Implies", "Similarity", "Evaluation")


def _cache_lookup(items):
    """item.id -> validated semparse atom strings (Track H cache), only for items that have a cached parse."""
    try:
        from .parse_cache import ParseCache
        c = ParseCache(); ent = c.entries()
    except Exception:
        return {}
    out = {}
    for it in items:
        try:
            a = c.atoms_for(it.content, ent)
        except Exception:
            a = None
        if a is not None:
            out[it.id] = a
    return out


def semparse_facts(atom_strs):
    """Binary facts (head, a, b, s, c) from validated semparse atoms (Interpretation wrappers unwrapped)."""
    from .semparse_adapter import split_toplevel
    out = []
    for src, node, err in split_toplevel("\n".join(atom_strs)):
        if err or not isinstance(node, list):
            continue
        if node and node[0] == "Interpretation" and len(node) == 3:
            node = node[2]
        if len(node) != 4 or node[0] != ":":
            continue
        c, tv = node[2], node[3]
        if (isinstance(c, list) and len(c) == 3 and c[0] in SP_HEADS and all(isinstance(x, str) for x in c[1:])
                and isinstance(tv, list) and len(tv) == 3):
            try:
                out.append((c[0], c[1], c[2], float(tv[1]), float(tv[2])))
            except ValueError:
                pass
    return out


def build_goals(rel, max_goals=None):
    """2-step Inheritance / Implies chains plus Member x Inheritance joins, not already asserted."""
    max_goals = int(max_goals or os.environ.get("WMTM_PC_SHADOW_MAX_GOALS", MAX_GOALS))
    have = {(h, a, b) for (h, a, b) in rel}
    by = {}
    for (h, a, b) in sorted(rel):
        by.setdefault((h, a), []).append(b)
    goals = []
    def add(t):
        g = "(%s %s %s)" % t
        if t not in have and t[1] != t[2] and g not in goals:
            goals.append(g)
    for (h, a, b) in sorted(rel):
        if h in TRANSITIVE:
            for c in by.get((h, b), []):
                add((h, a, c))
        if h == "Member":
            for c in by.get(("Inheritance", b), []):
                add(("Member", a, c))
    return goals[:max_goals]


def python_derived(facts, goals):
    """Run the Python PLN over the same facts.  Member is fed as Inheritance (Python has no Member) and mapped back."""
    from .pln import pln_inference_over_atoms, PLNAtom, TruthValue
    sym, back = {}, {}
    def tok(x):
        if x not in sym:
            sym[x] = "s%d" % len(sym); back[sym[x]] = x
        return sym[x]
    atoms, members = [], set()
    for (h, a, b, s, c) in facts:
        t = {"Inheritance": "Inheritance", "Member": "Inheritance", "Implies": "Implication"}.get(h)
        if not t:
            continue
        if h == "Member":
            members.add(a)
        atoms.append(PLNAtom(t, "%s(%s,%s)" % (t, tok(a), tok(b)), TruthValue(strength=s, confidence=c)))
    # Python sees Member as Inheritance, so it can also chain Member x Member (not valid).  Re-type each
    # derivation by the valid chain that supports it; derivations with no valid chain are marked invalid.
    rel = {(h, a, b) for (h, a, b, _, _) in facts}
    succ = {}
    for (h, a, b) in rel:
        succ.setdefault((h, a), set()).add(b)
    def chain(h1, a, c, h2="Inheritance"):
        return any(c in succ.get((h2, b), ()) for b in succ.get((h1, a), ()))
    py = []
    for d in pln_inference_over_atoms(atoms):
        m = _NAME.match(d.name)
        if not m or m.group(2) not in back or m.group(3) not in back:
            continue
        a, b = back[m.group(2)], back[m.group(3)]
        rec = {"s": round(d.truth.strength, 4), "c": round(d.truth.confidence, 4)}
        if m.group(1) == "Implication":
            rec["goal"] = "(Implies %s %s)" % (a, b)
        elif chain("Inheritance", a, b):
            rec["goal"] = "(Inheritance %s %s)" % (a, b)
        elif chain("Member", a, b):
            rec["goal"] = "(Member %s %s)" % (a, b)
        else:  # still asked of PeTTaChainer, so a Python-only conclusion is measured, not hidden
            rec["invalid_chain"] = rec["goal"] = "(Inheritance %s %s)" % (a, b)
        py.append(rec)
    return py


def build_snapshot(store, cycle=0, k=None):
    """-> dict spec.  Per item: cached semparse atoms (Track H) when available, else the regex PLN mapping."""
    from .pln_bridge import wmtm_item_to_pln_atoms
    k = int(k or os.environ.get("WMTM_PC_SHADOW_K", "200"))
    items = store.get_active_set()[:k]
    cached = _cache_lookup(items)
    metta, facts, n_sp, n_fb, i = [], [], 0, 0, 0
    for it in items:
        if it.id in cached:
            n_sp += 1
            key = (it.id, len(cached[it.id]), hash(tuple(cached[it.id])))
            fs = _FACTS_MEMO.get(key)
            if fs is None:  # parsing cached atoms costs ~20 ms/item; cached entries are immutable, so memoise
                fs = semparse_facts(cached[it.id])
                if len(_FACTS_MEMO) > 4096:
                    _FACTS_MEMO.clear()
                _FACTS_MEMO[key] = fs
            facts.extend(fs)
            if os.environ.get("WMTM_PC_SHADOW_FULL_KB", "0") == "1":
                metta.extend(cached[it.id])
            else:  # only the binary facts the goals are built from: a 700-atom KB makes each query ~7-10 s
                for (h, x, y, sv, cv) in fs:
                    metta.append("(: sp%d (%s %s %s) (STV %.4f %.4f))" % (i, h, x, y, min(1.0, max(0.0, sv)), min(0.99, max(0.0, cv)))); i += 1
            continue
        for a in wmtm_item_to_pln_atoms(it):
            if a.atom_type == "Concept":
                continue
            st = atom_to_metta(a, i); i += 1
            if st:
                n_fb += 1; metta.append(st); m = _NAME.match(a.name)
                facts.append((HEAD[m.group(1)], m.group(2), m.group(3), a.truth.strength, a.truth.confidence))
    rel = {(h, a, b) for (h, a, b, _, _) in facts}
    goals = build_goals(rel)
    try:
        py = python_derived(facts, goals)
    except Exception as e:  # Python PLN failure is recorded, not raised
        py = [{"error": type(e).__name__}]
    # also ask PeTTaChainer about what only Python derived, so one-engine-only conclusions are measured both ways
    cap = int(os.environ.get("WMTM_PC_SHADOW_MAX_GOALS", MAX_GOALS))
    for d in py:
        g = d.get("goal")
        if g and g not in goals and len(goals) < 2 * cap:
            goals.append(g)
    return {"cycle": cycle, "ts": time.time(), "k": k, "items": len(items), "atoms": metta, "goals": goals,
            "python_derived": py, "semparse_items": n_sp, "fallback_atoms": n_fb, "facts": len(facts)}


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
