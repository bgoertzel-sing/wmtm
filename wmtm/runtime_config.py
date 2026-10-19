"""Runtime flags for the background reasoner shadow (Track G) and the semantic-parse feed (Track H).

Source order (later wins):
  1. defaults below (everything OFF);
  2. ``<state_dir>/_wmtm_flags.json`` - a JSON object, re-read on every cycle, so a bot can be switched on/off
     without restarting its host (Iter runs each turn in a fresh process anyway);
  3. environment variables (set and non-empty) - kept for development and tests.
A missing, unreadable or non-object flags file counts as absent: the features stay OFF.

Relative paths:
  * vendor paths (``petta_dir``, ``pettachainer_dir``, ``semparse_prompt``, ``swipl_bin``, ``llm_env_file``)
    resolve against the *vendor root*, the directory that holds this package's distribution directory
    (``<bot>/vendor/`` when the package is vendored as ``<bot>/vendor/wmtm-<tag>/wmtm``);
  * data dirs (``runtime_dir``, ``shadow_dir``, ``semparse_dir``) resolve against ``state_dir``.
Default runtime data dir: ``<state_dir>/_wmtm_shadow`` (inside the bot's memory dir; the ``_`` prefix keeps it
out of memory listings), or ``<dist>/.local-data`` when no state_dir is known (development).
Machine-specific paths (swipl, the LLM env file) belong in the deploy-time flags file, never in this repo.
The LLM env file is only referenced by path; its contents are read by the parse worker at call time.
"""
from __future__ import annotations

import json
import os
import sys
import time
# resource / subprocess are imported where used: this module is on the automated fast path (rc2), where every
# import is paid once per Iter invocation.

FLAGS_FILENAME = "_wmtm_flags.json"
RUNTIME_SUBDIR = "_wmtm_shadow"
PKG_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_ROOT = os.path.dirname(PKG_DIR)            # <...>/wmtm-<tag>  (or the repo checkout)
VENDOR_ROOT = os.path.dirname(DIST_ROOT)        # <bot>/vendor      (when vendored)

SEMPARSE_PROMPT_SHA256 = "2ed18b934e28afac75b1d6c7c47b7b7413ed778c4c2916441274fb42933d9d1e"  # hitl @3ec15bd1

_V, _D = "vendor", "data"
# key: (env var, type, default, path base or None)
SPEC = {
    "pc_shadow":           ("WMTM_PC_SHADOW", bool, False, None),
    "semparse_feed":       ("WMTM_SEMPARSE_FEED", bool, False, None),
    "reasoner":            ("WMTM_REASONER", str, "", None),       # pettachainer|off; "" = API default (pettachainer); anything else = off
    "reasoner_max_age_s":  ("WMTM_REASONER_MAX_AGE", float, 900.0, None),
    "reasoner_max_admit":  ("WMTM_REASONER_MAX_ADMIT", int, 5, None),
    # Track O: derived strength is a probability; below reasoner_min_strength it means "probably not"
    "reasoner_min_strength": ("WMTM_REASONER_MIN_STRENGTH", float, 0.5, None),
    "reasoner_negation":   ("WMTM_REASONER_NEGATION", str, "skip", None),        # skip | unlikely ("unlikely: <text>")
    # Track O: CONTEXT coreference (off by default; results go to <semparse_dir>/ctx1, the old cache is kept)
    "semparse_context":    ("WMTM_SEMPARSE_CONTEXT", bool, False, None),
    "context_max_notes":   ("WMTM_CONTEXT_MAX_NOTES", int, 3, None),
    "context_max_atoms":   ("WMTM_CONTEXT_MAX_ATOMS", int, 40, None),
    "context_max_chars":   ("WMTM_CONTEXT_MAX_CHARS", int, 4000, None),
    "context_passage_chars": ("WMTM_CONTEXT_PASSAGE_CHARS", int, 600, None),
    # Track Q: speaker linking (off by default; new parses go to <semparse_dir>/spk1, old caches are kept).
    # speaker_map: Telegram user id / username -> canonical name; speaker_self: the bot's own name.  Flags file only.
    "speaker_link":        ("WMTM_SPEAKER_LINK", bool, False, None),
    "speaker_map":         ("WMTM_SPEAKER_MAP", dict, {}, None),
    "speaker_self":        ("WMTM_SPEAKER_SELF", str, "", None),
    # v0.4: write PeTTaChainer-admitted conclusions back to the long-term journal (derived_promotion)?  Off = they
    # live in working memory only.  Python-PLN / tool-derived items are not affected.
    "reasoner_writeback":  ("WMTM_REASONER_WRITEBACK", bool, False, None),
    # v0.4 rc2: also admit PeTTaChainer conclusions on automated (fast-path) turns
    "reasoner_admit_on_automated": ("WMTM_REASONER_ADMIT_ON_AUTOMATED", bool, True, None),
    "admit_log_max_bytes": ("WMTM_ADMIT_LOG_MAX_BYTES", int, 1_000_000, None),   # <shadow_dir>/admit_log.jsonl (+ .1)
    # Track J parse-quality gate (wmtm/parse_gate.py); applies to PeTTaChainer conclusions only
    "gate_on":             ("WMTM_GATE", bool, True, None),
    "gate_min_conf":       ("WMTM_GATE_MIN_CONF", float, 0.3, None),
    "gate_broad_terms":    ("WMTM_GATE_BROAD_TERMS", str, "thing,things,entity,entities,object,objects,something,anything,everything,stuff,item,items,concept,trivial,important,relevant,useful,ok,fine,good,bad", None),
    "gate_placeholder_terms": ("WMTM_GATE_PLACEHOLDERS", str, "it,this,that,they,them,thing,something,someone,somebody,x,y,z", None),
    "gate_hedged_quantifiers": ("WMTM_GATE_HEDGED", str, "mostly,most,some,often,usually,sometimes,many,few,several,rarely,partly,generally,typically,maybe,probably", None),
    "gate_negative_quantifiers": ("WMTM_GATE_NEGATIVE", str, "no,none,nothing,never,not,nobody,neither", None),
    "gate_broad_action":   ("WMTM_GATE_BROAD_ACTION", str, "reject", None),      # reject | discount | keep
    "gate_hedged_action":  ("WMTM_GATE_HEDGED_ACTION", str, "reject", None),     # reject | discount | keep
    "gate_discount":       ("WMTM_GATE_DISCOUNT", float, 0.5, None),             # strength factor for discount
    "gate_identifier_action": ("WMTM_GATE_IDENTIFIER_ACTION", str, "reject", None),  # reject | discount | keep (Track M)
    "gate_identifier_bad_categories": ("WMTM_GATE_IDENTIFIER_BAD", str, "branch,dir,directory,folder,path,file,repo,repository,worktree,tree,remote,fork", None),  # an id subject may not be typed as these (also *_<term>)
    "gate_max_per_fact":   ("WMTM_GATE_MAX_PER_FACT", int, 3, None),             # admitted conclusions per KB fact per cycle; 0 = no cap
    "gate_review_min":     ("WMTM_GATE_REVIEW_MIN", int, 3, None),               # log facts behind >= N proved conclusions
    "parse_cap_per_hour":  ("WMTM_SEMPARSE_PER_HOUR", int, 20, None),
    "semparse_preamble":   ("WMTM_SEMPARSE_PREAMBLE", bool, True, None),          # Track M: prepend semparse_preamble.PREAMBLE to the (pinned, unedited) prompt
    "parse_max_chars":     ("WMTM_SEMPARSE_MAX_CHARS", int, 1500, None),
    "parse_max_attempts":  ("WMTM_SEMPARSE_MAX_ATTEMPTS", int, 2, None),
    "shadow_k":            ("WMTM_PC_SHADOW_K", int, 200, None),
    "shadow_max_goals":    ("WMTM_PC_SHADOW_MAX_GOALS", int, 60, None),
    "shadow_full_kb":      ("WMTM_PC_SHADOW_FULL_KB", bool, False, None),
    "shadow_skolem_goals": ("WMTM_PC_SHADOW_SKOLEM_GOALS", bool, False, None),
    "shadow_goal_rank":    ("WMTM_PC_SHADOW_GOAL_RANK", bool, True, None),       # Track N: Design A ranked goal pool (off = Track M 2-step goals)
    "shadow_max_hops":     ("WMTM_PC_SHADOW_MAX_HOPS", int, 3, None),            # Track N: longest chain in the pool (derivation steps)
    "shadow_min_hops":     ("WMTM_PC_SHADOW_MIN_HOPS", int, 1, None),            # Track N: only ask goals needing >= N steps
    "shadow_goal_weights": ("WMTM_PC_SHADOW_GOAL_WEIGHTS", str, "2,1,1,0.5", None),  # Track N: w_req,w_depth,w_info,w_sti
    "shadow_timeout_s":    ("WMTM_PC_SHADOW_TIMEOUT", float, 2.0, None),
    "shadow_budget_s":     ("WMTM_PC_SHADOW_BUDGET", float, 20.0, None),
    "shadow_steps":        ("WMTM_PC_SHADOW_STEPS", int, 30, None),
    "shadow_min_interval_s": ("WMTM_PC_SHADOW_MIN_INTERVAL", float, 300.0, None),
    # Track P: recall/context plumbing (wmtm/context.py).  Each switch off = the rc2 behaviour.
    "cleanup_protect_recent": ("WMTM_CLEANUP_PROTECT_RECENT", bool, True, None),  # stale cleanup spares fresh recalls
    "cleanup_grace_turns": ("WMTM_CLEANUP_GRACE_TURNS", int, 10, None),   # ... recalled/relevant within N cycles
    "cleanup_grace_s":     ("WMTM_CLEANUP_GRACE_S", float, 1800.0, None), # ... or within N seconds
    "context_rank":        ("WMTM_CONTEXT_RANK", bool, True, None),       # block ranked by request relevance + STI
    "context_rank_weights": ("WMTM_CONTEXT_RANK_WEIGHTS", str, "0.7,0.3", None),  # w_rel, w_sti (both normalised 0-1)
    "context_item_chars":  ("WMTM_CONTEXT_ITEM_CHARS", int, 600, None),   # per item cap (rc2: 200); share = total/items
    "context_total_chars": ("WMTM_CONTEXT_TOTAL_CHARS", int, 6000, None), # all item texts together (rc2: <= 3000)
    "context_max_items":   ("WMTM_CONTEXT_MAX_ITEMS", int, 15, None),
    "context_min_request_items": ("WMTM_CONTEXT_MIN_REQUEST_ITEMS", int, 5, None),  # best-matching items always shown
    "context_min_score":   ("WMTM_CONTEXT_MIN_SCORE", float, 0.2, None),  # with a known request: hide weaker filler
    "request_item":        ("WMTM_REQUEST_ITEM", bool, True, None),       # admit the request as a source_type=user item
    "request_item_chars":  ("WMTM_REQUEST_ITEM_CHARS", int, 600, None),
    "hooks_on_automated":  ("WMTM_HOOKS_ON_AUTOMATED", bool, True, None),
    "runtime_dir":         ("WMTM_RUNTIME_DIR", str, "", _D),
    "shadow_dir":          ("WMTM_PC_SHADOW_DIR", str, "", _D),
    "semparse_dir":        ("WMTM_SEMPARSE_DIR", str, "", _D),
    "petta_dir":           ("WMTM_PC_PETTA", str, "petta-v1.0.6", _V),
    "pettachainer_dir":    ("WMTM_PC_VENDOR", str, "pettachainer-36b3fe6-dedup", _V),
    "semparse_prompt":     ("SEMPARSE_PROMPT", str, "semparse-hitl-3ec15bd1/prompt.txt", _V),
    "semparse_prompt_sha256": ("WMTM_SEMPARSE_PROMPT_SHA256", str, SEMPARSE_PROMPT_SHA256, None),
    "swipl_bin":           ("WMTM_SWIPL_BIN", str, "", _V),
    "llm_env_file":        ("WMTM_LLM_ENV_FILE", str, "", _V),
    "python":              ("WMTM_WORKER_PYTHON", str, "", None),
    "worker_nice":         ("WMTM_WORKER_NICE", int, 19, None),
    "worker_sched_idle":   ("WMTM_WORKER_SCHED_IDLE", bool, True, None),
    "worker_prio_refresh_s": ("WMTM_WORKER_PRIO_REFRESH", float, 1.0, None),   # Track P: 1 s (was 5 s; the host scheduler resets it)
    "worker_mem_mb":       ("WMTM_WORKER_MEM_MB", int, 3072, None),
    "jsonl_max_bytes":     ("WMTM_JSONL_MAX_BYTES", int, 10_000_000, None),
    "cache_max_bytes":     ("WMTM_SEMPARSE_CACHE_MAX_BYTES", int, 20_000_000, None),
}


def _coerce(typ, v):
    if typ is bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        s = str(v).strip().lower()
        if s in ("1", "true", "yes", "on"):
            return True
        if s in ("0", "false", "no", "off", ""):
            return False
        raise ValueError(v)
    if typ is int:
        if isinstance(v, bool):
            raise ValueError(v)
        return int(v)
    if typ is float:
        if isinstance(v, bool):
            raise ValueError(v)
        return float(v)
    if typ is dict:
        if isinstance(v, str):
            v = json.loads(v)
        if not isinstance(v, dict):
            raise ValueError(v)
        return dict(v)
    if not isinstance(v, str):
        raise ValueError(v)
    return v


def read_flags_file(state_dir):
    """-> (dict, info).  Never raises; a bad file is reported in info and treated as absent."""
    info = {"flags_file": None, "loaded": False}
    if not state_dir:
        return {}, info
    path = os.path.join(str(state_dir), FLAGS_FILENAME)
    info["flags_file"] = path
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}, info
    except (OSError, ValueError) as e:
        info["error"] = "%s: %s" % (type(e).__name__, str(e)[:120])
        return {}, info
    if not isinstance(data, dict):
        info["error"] = "flags file is not a JSON object"
        return {}, info
    info["loaded"] = True
    return data, info


def resolve(state_dir=None, environ=None):
    """Effective runtime config for one cycle: defaults < flags file < env.  Never raises."""
    env = os.environ if environ is None else environ
    raw, info = read_flags_file(state_dir)
    cfg, bad = {}, []
    for key, (ename, typ, default, _) in SPEC.items():
        val = dict(default) if isinstance(default, dict) else default
        if key in raw:
            try:
                val = _coerce(typ, raw[key])
            except (TypeError, ValueError):
                bad.append(key)
        ev = env.get(ename)
        if ev is not None and ev != "":
            try:
                val = _coerce(typ, ev)
            except (TypeError, ValueError):
                bad.append(ename)
        cfg[key] = val
    if bad:
        info["invalid"] = bad
    unknown = sorted(k for k in raw if k not in SPEC and not k.startswith("_"))
    if unknown:
        info["unknown_keys"] = unknown
    sd = os.path.abspath(str(state_dir)) if state_dir else None

    def path(key):
        v = cfg[key]
        if not v:
            return ""
        v = os.path.expanduser(v)
        if os.path.isabs(v):
            return v
        base = VENDOR_ROOT if SPEC[key][3] == _V else (sd or DIST_ROOT)
        return os.path.normpath(os.path.join(base, v))

    for key, (_, _, _, base) in SPEC.items():
        if base:
            cfg[key] = path(key)
    if not cfg["runtime_dir"]:
        cfg["runtime_dir"] = os.path.join(sd, RUNTIME_SUBDIR) if sd else os.path.join(DIST_ROOT, ".local-data")
    cfg["shadow_dir"] = cfg["shadow_dir"] or os.path.join(cfg["runtime_dir"], "pc_shadow")
    cfg["semparse_dir"] = cfg["semparse_dir"] or os.path.join(cfg["runtime_dir"], "semparse_cache")
    cfg["python"] = cfg["python"] or sys.executable
    cfg["parse_cap_per_hour"] = max(0, cfg["parse_cap_per_hour"])
    cfg["reasoner"] = str(cfg["reasoner"] or "").strip().lower()
    if cfg["reasoner"] and cfg["reasoner"] not in ("pettachainer", "off"):
        info.setdefault("invalid", []).append("reasoner"); cfg["reasoner"] = "off"
    cfg["state_dir"] = sd
    cfg["_source"] = info
    return cfg


def write_json_atomic(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)
    os.replace(tmp, path)


def load_worker_config(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ------------------------------------------------------------------ JSONL size cap
def rotate_jsonl(path, max_bytes):
    """If path is larger than max_bytes, move it to path.1 (replacing the previous .1).  Total <= ~2x cap."""
    try:
        if max_bytes and max_bytes > 0 and os.path.getsize(path) > max_bytes:
            os.replace(path, path + ".1")
            return True
    except OSError:
        pass
    return False


def append_jsonl(path, rec, max_bytes=None):
    rotate_jsonl(path, max_bytes)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")


# ------------------------------------------------------------------ workers
def apply_mem_cap(mb):
    """Worker side: cap this process (and children) to mb MB of address space.  0/None = no cap."""
    if not mb or mb <= 0:
        return None
    import resource
    lim = int(mb) * 1024 * 1024
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        if hard != resource.RLIM_INFINITY:
            lim = min(lim, hard)
        resource.setrlimit(resource.RLIMIT_AS, (lim, hard))
        return lim
    except (ValueError, OSError):
        return None


def _tids(pid="self"):
    try:
        return [int(t) for t in os.listdir("/proc/%s/task" % pid)]
    except (OSError, ValueError):
        return [0]


def _descendants(pid):
    """pid's descendant processes (via /proc/<pid>/task/*/children); [] if unknown."""
    out, todo = [], [pid]
    while todo:
        p = todo.pop()
        for t in _tids(p):
            try:
                with open("/proc/%d/task/%d/children" % (p, t)) as fh:
                    kids = [int(x) for x in fh.read().split()]
            except (OSError, ValueError):
                continue
            for k in kids:
                if k not in out:
                    out.append(k); todo.append(k)
    return out


def priority_of(tid=0):
    """-> {"nice": n, "policy": "idle"|"batch"|"other"|...} for one thread/process (0 = calling thread)."""
    out = {}
    try:
        out["nice"] = os.getpriority(os.PRIO_PROCESS, tid)
    except OSError:
        pass
    try:
        pol = os.sched_getscheduler(tid)
        out["policy"] = {getattr(os, "SCHED_IDLE", -1): "idle", getattr(os, "SCHED_BATCH", -2): "batch",
                         os.SCHED_OTHER: "other"}.get(pol, str(pol))
    except OSError:
        pass
    return out


def _apply_priority(cfg, tid):
    """Set nice + SCHED_IDLE on one thread/process (Linux: both are per-thread).  -> True if it had drifted."""
    drift = False
    try:
        want = int(cfg.get("worker_nice", 19))
        if os.getpriority(os.PRIO_PROCESS, tid) < want:
            drift = True
            os.setpriority(os.PRIO_PROCESS, tid, want)
    except (OSError, ValueError, TypeError):
        pass
    if cfg.get("worker_sched_idle", True) and hasattr(os, "SCHED_IDLE"):
        try:
            if os.sched_getscheduler(tid) != os.SCHED_IDLE:
                drift = True
                os.sched_setscheduler(tid, os.SCHED_IDLE, os.sched_param(0))
        except OSError:
            pass
    return drift


def lower_priority(cfg, children=False):
    """Worker side, called in the child itself at startup: make this process (every thread; with children=True
    also its descendants) background-only.  `nice` alone is not enough on hosts whose scheduler daemon rewrites
    nice values and policy (system76-scheduler re-assigns e.g. nice 12 / SCHED_OTHER to system.slice processes
    every refresh); SCHED_IDLE only gets CPU no other task wants.  -> the *actual* {"nice", "policy"} afterwards;
    never raises."""
    try:
        pids = _tids("self") + (_descendants(os.getpid()) if children else [])
        for t in pids:
            _apply_priority(cfg, t)
    except Exception:
        pass
    return priority_of(0)


class PriorityGuard:
    """Re-asserts lower_priority() every cfg["worker_prio_refresh_s"] seconds from a daemon thread (covering the
    worker's threads and child processes), because a scheduler daemon can reset it mid-run.  Records what it saw:
    start()/stats() -> {"nice", "policy", "resets", "checks"}; stats() also re-reads the actual values (pass it to
    the worker's output record).  never raises."""

    def __init__(self, cfg):
        self.cfg = dict(cfg or {})
        self.interval = float(self.cfg.get("worker_prio_refresh_s", 1.0) or 0)
        self.resets = 0
        self.checks = 0
        self.start_prio = {}
        self._stop = None

    def check(self):
        try:
            self.checks += 1
            hit = False
            for t in _tids("self") + _descendants(os.getpid()):
                hit = _apply_priority(self.cfg, t) or hit
            if hit:
                self.resets += 1
        except Exception:
            pass

    def start(self):
        self.start_prio = lower_priority(self.cfg)
        if self.interval > 0:
            import threading
            self._stop = threading.Event()

            def loop():
                while not self._stop.wait(self.interval):
                    self.check()
            th = threading.Thread(target=loop, name="wmtm-prio-guard", daemon=True)
            th.start()
            _apply_priority(self.cfg, getattr(th, "native_id", 0) or 0)
        return dict(self.start_prio)

    def stats(self):
        end = priority_of(0)                             # what the scheduler left us with at the end of the run
        self.check()                                     # (counted as a reset if it had drifted)
        out = dict(self.start_prio)
        out["end"] = end
        out["resets"] = self.resets
        out["checks"] = self.checks
        return out

    def stop(self):
        if self._stop is not None:
            self._stop.set()


def worker_env(cfg, base=None):
    env = dict(os.environ if base is None else base)
    env["PYTHONPATH"] = DIST_ROOT + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    if cfg.get("swipl_bin"):
        env["PATH"] = cfg["swipl_bin"] + os.pathsep + env.get("PATH", "")
    if cfg.get("petta_dir"):
        env["PETTA_PATH"] = cfg["petta_dir"]
    return env


def spawn_worker(cfg, module, args, pidfile):
    """Start `python -m <module> args` detached (new session), niced, from DIST_ROOT.  Returns pid.  Never waits."""
    import subprocess
    cmd = [cfg.get("python") or sys.executable, "-u", "-m", module] + list(args)
    pre = ["nice", "-n", str(int(cfg.get("worker_nice", 19)))]
    if cfg.get("worker_sched_idle", True) and os.path.exists("/usr/bin/chrt"):
        pre = ["/usr/bin/chrt", "-i", "0"] + pre      # idle from exec on; the worker re-asserts it itself
    if os.path.exists("/usr/bin/ionice"):
        pre += ["ionice", "-c", "3"]
    p = subprocess.Popen(pre + cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         cwd=DIST_ROOT, env=worker_env(cfg), start_new_session=True, close_fds=True)
    with open(pidfile, "w") as fh:
        fh.write(str(p.pid))
    return p.pid


def _proc_state(pid):
    """-> (state letter, cmdline) from /proc, or (None, "") if unknown."""
    try:
        with open("/proc/%d/stat" % pid) as fh:
            st = fh.read().rsplit(")", 1)[1].split()[0]
        with open("/proc/%d/cmdline" % pid, "rb") as fh:
            cmd = fh.read().replace(b"\0", b" ").decode("utf-8", "replace")
        return st, cmd
    except (OSError, IndexError):
        return None, ""


def busy(pidfile, max_age=None):
    """True if the worker named in pidfile is still running.  A zombie counts as finished.  A worker older than
    max_age seconds (pidfile mtime) is presumed hung: its process group is SIGKILLed and False is returned."""
    try:
        with open(pidfile) as fh:
            pid = int(fh.read().strip())
        os.kill(pid, 0)
    except (OSError, ValueError):
        return False
    st, cmd = _proc_state(pid)
    if st == "Z":
        return False
    if max_age:
        try:
            age = time.time() - os.path.getmtime(pidfile)
        except OSError:
            age = 0
        if age > max_age and "wmtm.workers." in cmd:
            try:
                os.killpg(pid, 9)
            except OSError:
                pass
            return False
    return True
