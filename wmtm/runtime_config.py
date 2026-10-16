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
import resource
import subprocess
import sys
import time

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
    "parse_cap_per_hour":  ("WMTM_SEMPARSE_PER_HOUR", int, 20, None),
    "parse_max_chars":     ("WMTM_SEMPARSE_MAX_CHARS", int, 1500, None),
    "parse_max_attempts":  ("WMTM_SEMPARSE_MAX_ATTEMPTS", int, 2, None),
    "shadow_k":            ("WMTM_PC_SHADOW_K", int, 200, None),
    "shadow_max_goals":    ("WMTM_PC_SHADOW_MAX_GOALS", int, 60, None),
    "shadow_full_kb":      ("WMTM_PC_SHADOW_FULL_KB", bool, False, None),
    "shadow_skolem_goals": ("WMTM_PC_SHADOW_SKOLEM_GOALS", bool, False, None),
    "shadow_timeout_s":    ("WMTM_PC_SHADOW_TIMEOUT", float, 2.0, None),
    "shadow_budget_s":     ("WMTM_PC_SHADOW_BUDGET", float, 20.0, None),
    "shadow_steps":        ("WMTM_PC_SHADOW_STEPS", int, 30, None),
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
        val = default
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
    lim = int(mb) * 1024 * 1024
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        if hard != resource.RLIM_INFINITY:
            lim = min(lim, hard)
        resource.setrlimit(resource.RLIMIT_AS, (lim, hard))
        return lim
    except (ValueError, OSError):
        return None


def lower_priority(cfg):
    """Worker side: make this process (and its children) background-only.  `nice` alone is not enough on hosts
    whose scheduler daemon rewrites nice values (e.g. system76-scheduler); SCHED_IDLE is kept by such daemons
    and only gets CPU no other task wants.  -> {"nice": n, "policy": "idle"|"other"}; never raises."""
    out = {}
    try:
        want = int(cfg.get("worker_nice", 19))
        cur = os.getpriority(os.PRIO_PROCESS, 0)
        if want > cur:
            os.setpriority(os.PRIO_PROCESS, 0, want)
        out["nice"] = os.getpriority(os.PRIO_PROCESS, 0)
    except (OSError, ValueError, TypeError):
        pass
    if cfg.get("worker_sched_idle", True) and hasattr(os, "SCHED_IDLE"):
        try:
            os.sched_setscheduler(0, os.SCHED_IDLE, os.sched_param(0))
        except OSError:
            pass
    try:
        out["policy"] = "idle" if os.sched_getscheduler(0) == getattr(os, "SCHED_IDLE", -1) else "other"
    except OSError:
        pass
    return out


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
    cmd = [cfg.get("python") or sys.executable, "-u", "-m", module] + list(args)
    pre = ["nice", "-n", str(int(cfg.get("worker_nice", 19)))]
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
