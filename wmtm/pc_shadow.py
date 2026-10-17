"""Track G: PeTTaChainer *shadow* run alongside the Python PLN phase.

Off by default.  Enabled per bot by ``"pc_shadow": true`` in ``<state_dir>/_wmtm_flags.json`` (or env
WMTM_PC_SHADOW=1); see wmtm/runtime_config.py for every knob.  The orchestrator calls
maybe_launch(store, cycle, state_dir) after the Python PLN phase; the cycle side only copies the top-K item fields
(K = shadow_k, default 200) into a spec under ``<runtime_dir>/pc_shadow/`` and launches a detached, niced worker
(``python -m wmtm.workers.pc_shadow``) that builds the snapshot (cached semparse atoms only, goals)
and asks PeTTaChainer.  It NEVER waits on the worker, never admits anything into WMTM and never raises.
At most one worker runs at a time (pidfile guard); a busy worker means the cycle is skipped, not queued.
"""
from __future__ import annotations
import glob, os, re, time

from . import runtime_config as rc

WORKER_MODULE = "wmtm.workers.pc_shadow"
WORKER_MAX_AGE = 900          # s; an older worker is presumed hung and killed by the next launch
_NAME = re.compile(r"^(\w+)\(([a-z_][a-z0-9_-]*),([a-z_][a-z0-9_-]*)\)$")
# PLN relation -> MeTTa head.  Python "Implication" facts become (Implies a b): a bare (Implication a b)
# would be read by PeTTaChainer as a *rule*, not a fact.
HEAD = {"Inheritance": "Inheritance", "Implication": "Implies", "Similarity": "Similarity", "Evaluation": "Evaluation"}
TRANSITIVE = ("Inheritance", "Implies")


def enabled(cfg=None) -> bool:
    return bool((cfg or rc.resolve())["pc_shadow"])


def atom_to_metta(atom, i):
    m = _NAME.match(atom.name)
    if not m or m.group(1) not in HEAD:
        return None
    s = min(1.0, max(0.0, float(atom.truth.strength))); c = min(0.99, max(0.0, float(atom.truth.confidence)))
    return "(: wm%d (%s %s %s) (STV %.4f %.4f))" % (i, HEAD[m.group(1)], m.group(2), m.group(3), s, c)


MAX_GOALS = 60
_FACTS_MEMO = {}
SP_HEADS = ("Inheritance", "Member", "Implies", "Similarity", "Evaluation")


def _cache_lookup(items, cache_dir=None):
    """item.id -> validated semparse atom strings (Track H cache), only for items that have a cached parse."""
    try:
        from .parse_cache import ParseCache
        c = ParseCache(cache_dir); ent = c.entries()
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


def is_skolem(term) -> bool:
    """Parser-invented per-item placeholder entity (sk_* witness, scoped as sk_<x>__<item>)."""
    return isinstance(term, str) and term.startswith("sk_")


def goal_has_skolem(goal: str) -> bool:
    return any(is_skolem(t) for t in goal.strip("()").split()[1:])


def build_goals(rel, max_goals=None, skolem_goals=False):
    """2-step Inheritance / Implies chains plus Member x Inheritance joins, not already asserted.

    Goals about parser-invented placeholder entities (sk_*) are dropped unless skolem_goals=True: they are
    per-item witnesses ("some request"), so a conclusion about one is not a belief about anything nameable.
    The facts mentioning them stay in the KB (they can still support other chains)."""
    max_goals = int(max_goals or MAX_GOALS)
    have = {(h, a, b) for (h, a, b) in rel}
    by = {}
    for (h, a, b) in sorted(rel):
        by.setdefault((h, a), []).append(b)
    goals = []
    def add(t):
        g = "(%s %s %s)" % t
        if not skolem_goals and (is_skolem(t[1]) or is_skolem(t[2])):
            return
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


def build_snapshot(store, cycle=0, k=None, cfg=None):
    """-> dict spec.  Per item: cached semparse atoms (Track H) only.  Track K: no regex fallback - an item that has
    not been parsed yet contributes no facts this cycle (counted in unparsed_items)."""
    cfg = cfg or rc.resolve()
    k = int(k or cfg["shadow_k"])
    max_goals = int(cfg["shadow_max_goals"]); skolem_goals = bool(cfg["shadow_skolem_goals"])
    items = store.get_active_set()[:k]
    cached = _cache_lookup(items, cfg["semparse_dir"])
    metta, facts, n_sp, n_unparsed, i = [], [], 0, 0, 0
    src, fsrc = {}, []       # Track I provenance: KB label -> item id; (head, a, b, item id) per fact
    from . import parse_gate as _pg   # Track J: per-fact sanity rules before facts enter the KB
    gst = _pg.settings(cfg); gdec, lf = [], {}
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
            fs, dec = _pg.gate_facts(fs, _pg.quantifiers(cached[it.id]), gst, it.id); gdec.extend(dec)
            facts.extend(fs); fsrc.extend([h, x, y, it.id] for (h, x, y, _s, _c) in fs)
            if cfg["shadow_full_kb"]:
                metta.extend(cached[it.id])
            else:  # only the binary facts the goals are built from: a 700-atom KB makes each query ~7-10 s
                for (h, x, y, sv, cv) in fs:
                    metta.append("(: sp%d (%s %s %s) (STV %.4f %.4f))" % (i, h, x, y, min(1.0, max(0.0, sv)), min(0.99, max(0.0, cv)))); src["sp%d" % i] = it.id; lf["sp%d" % i] = "(%s %s %s)" % (h, x, y); i += 1
            continue
        n_unparsed += 1   # Track K: no regex fallback; an item without cached semparse atoms adds no facts
    rel = {(h, a, b) for (h, a, b, _, _) in facts}
    goals = build_goals(rel, max_goals, skolem_goals)
    return {"cycle": cycle, "ts": time.time(), "k": k, "items": len(items), "atoms": metta, "goals": goals,
            "semparse_items": n_sp, "unparsed_items": n_unparsed, "facts": len(facts),
            "skolem_goals": skolem_goals,
            "atom_src": src, "fact_src": fsrc, "label_fact": lf,
            "gate": dict(_pg.summary(gdec), on=gst["on"], decisions=gdec)}


def _cleanup_specs(out_dir, max_age=3600):
    for f in glob.glob(os.path.join(out_dir, "spec_c*.json")):
        try:
            if time.time() - os.path.getmtime(f) > max_age:
                os.unlink(f)
        except OSError:
            pass


def launch(spec, cfg=None, out_dir=None, module=None):
    """Write spec + worker config, start a detached niced worker, return its pid (or None if busy).  Never waits."""
    cfg = dict(cfg or rc.resolve())
    out_dir = out_dir or cfg["shadow_dir"]; cfg["shadow_dir"] = out_dir
    os.makedirs(out_dir, exist_ok=True)
    pidfile = os.path.join(out_dir, "worker.pid")
    if rc.busy(pidfile, WORKER_MAX_AGE):
        return None
    _cleanup_specs(out_dir)
    import tempfile, json
    fd, path = tempfile.mkstemp(prefix="spec_c%d_" % spec.get("cycle", 0), suffix=".json", dir=out_dir)
    with os.fdopen(fd, "w") as f:
        json.dump(spec, f)
    cpath = os.path.join(out_dir, "worker_config.json")
    rc.write_json_atomic(cpath, cfg)
    return rc.spawn_worker(cfg, module or WORKER_MODULE,
                           ["--spec", path, "--out", os.path.join(out_dir, "shadow.jsonl"), "--config", cpath], pidfile)


LAST_LAUNCH = "last_launch"    # stamp file in shadow_dir; its mtime is the last launch time (rate limit)


def rate_limited(cfg, now=None) -> bool:
    """True if a shadow worker was launched less than shadow_min_interval_s ago (0 = no limit)."""
    iv = float(cfg.get("shadow_min_interval_s") or 0)
    if iv <= 0:
        return False
    try:
        last = os.path.getmtime(os.path.join(cfg["shadow_dir"], LAST_LAUNCH))
    except OSError:
        return False
    now = time.time() if now is None else now
    return 0 <= now - last < iv


def _stamp(cfg):
    try:
        p = os.path.join(cfg["shadow_dir"], LAST_LAUNCH)
        with open(p, "w") as fh:
            fh.write("%.3f\n" % time.time())
    except OSError:
        pass


def maybe_launch_raw(raw, cycle=0, cfg=None, state_dir=None, source="cycle", force=False):
    """Launch from raw top-K item dicts (raw_item() shape, active-set order).  Shared by the orchestrator hook and
    the automated fast path (which has only the state JSON, no engine).  Gates, cheapest first: flag, single-worker
    busy guard, rate limit (shadow_min_interval_s).  Returns pid or None; swallows every error."""
    try:
        cfg = cfg or rc.resolve(state_dir)
        if not (cfg["pc_shadow"] or force):     # force: reasoner=pettachainer|both needs the worker (Track I)
            return None
        if rc.busy(os.path.join(cfg["shadow_dir"], "worker.pid"), WORKER_MAX_AGE):
            return None  # skip before doing any work
        if rate_limited(cfg):
            return None
        k = int(cfg["shadow_k"])
        raw = list(raw or [])[:k]
        if not raw:
            return None
        pid = launch({"cycle": cycle, "ts": time.time(), "k": k, "raw_items": raw, "atoms": [], "goals": [],
                      "source": source}, cfg)
        if pid:
            _stamp(cfg)
        return pid
    except Exception:
        return None


def maybe_launch(store, cycle=0, state_dir=None, cfg=None, force=False):
    """Orchestrator hook.  Returns pid or None; swallows every error."""
    try:
        cfg = cfg or rc.resolve(state_dir)
        if not (cfg["pc_shadow"] or force):     # force: reasoner=pettachainer needs the worker (Track I)
            return None
        if rc.busy(os.path.join(cfg["shadow_dir"], "worker.pid"), WORKER_MAX_AGE) or rate_limited(cfg):
            return None  # skip before doing any work
        # cycle side only copies the top-K item fields; the worker builds the snapshot (cache read, Python PLN)
        k = int(cfg["shadow_k"])
        return maybe_launch_raw([raw_item(it) for it in store.get_active_set()[:k]], cycle, cfg, force=force)
    except Exception:
        return None


def raw_item_from_dict(d):
    """raw_item() from a persisted item dict (the state JSON the automated fast path reads)."""
    return {"id": d.get("id"), "content": d.get("content", ""), "sti": (d.get("attention") or {}).get("sti", 0.0),
            "tv_strength": d.get("tv_strength", 0.0), "tv_confidence": d.get("tv_confidence", 0.0)}


def raw_item(it):
    return {"id": it.id, "content": it.content, "sti": it.attention.sti,
            "tv_strength": getattr(it, "tv_strength", 0.0), "tv_confidence": getattr(it, "tv_confidence", 0.0)}


class _RawStore:
    """Minimal store over raw item dicts (already in active-set order), for building a snapshot in the worker."""
    def __init__(self, raw):
        from types import SimpleNamespace as NS
        self._items = [NS(id=r["id"], content=r["content"], attention=NS(sti=r.get("sti", 0.0)),
                          tv_strength=r.get("tv_strength", 0.0), tv_confidence=r.get("tv_confidence", 0.0)) for r in raw]
    def get_active_set(self):
        return list(self._items)


def snapshot_from_raw(spec, cfg=None):
    """Worker side: turn a raw spec (from maybe_launch) into a full spec."""
    full = build_snapshot(_RawStore(spec["raw_items"]), spec.get("cycle", 0), spec.get("k"), cfg)
    full["source"] = spec.get("source")
    full["ts"] = spec.get("ts", full["ts"]); full["build_s"] = round(time.time() - full["ts"], 3)
    return full
