"""Parse-call budget with fixed shares, counted across every log that belongs to a share.

andy (2026-11-10, fixed shares): the live feed gets ``parse_share_live_per_hour`` (default 10) gateway parse calls
per rolling hour and all hive tasks together get ``parse_share_tasks_per_hour`` (default 10).  Before this module
each ParseCache counted only its own parse_log.jsonl, so live plus tasks reached 53 calls in one hour.

Shares and the logs each one counts
  * live: ``<live root>/parse_log.jsonl`` + ``ctx1/`` + ``spk1/`` (every live sub-cache together) and the live
    share ledger ``<live root>/share_ledger.jsonl``.  The live root is ``parse_live_dir`` when set, else the live
    cache's own base dir.  Only a caller with ``parse_role = live`` ever writes there.
  * tasks: the host-wide task ledger ``<parse_budget_dir>/tasks/ledger.jsonl`` plus every task log registered in
    ``<parse_budget_dir>/tasks/logs.d/`` (each task ParseCache's parse_log.jsonl, each measure_parse run's
    parse_log.jsonl).  A task never counts only its own log.  A task caller never writes inside ``parse_live_dir``
    (refused with LiveDirWriteRefused).

Counting: one gateway call = one ledger row with a ``call_id``, written atomically (under the share lock) before the
call is made.  Log rows that carry ``call_ids`` are joined to the ledger (no double count); a log row without
``call_ids`` (rc2 live code, older tools) counts as one call; rows marked ``"mocked": true`` (no gateway call) count
as none.  Only the last LOG_TAIL_BYTES of each file are read: rows are appended in time order, so a tail that does
not reach back an hour already holds more rows than any share.

When a share is full the caller either waits (``acquire(wait=True)``, bounded by ``parse_share_max_wait_s``) or
gets ShareFull, whose message starts with SHARE_FULL so loops can stop with a clear status without recording a
parse attempt.  Both shares are config values (runtime_config SPEC), so they can be raised later.
"""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import time
import uuid

HOUR = 3600.0
SHARE_FULL = "parse share full"
LOG_TAIL_BYTES = 1 << 20
LEDGER_MAX_BYTES = 1 << 20          # the ledger is rewritten (rows older than 2 h dropped) above this size
SUBCACHES = ("", "ctx1", "spk1")    # live sub-caches (parse_cache.CTX_VERSION, SPK_VERSION)
ROLES = ("live", "task")


class ShareFull(RuntimeError):
    """The share has no room in the rolling hour (and waiting was not allowed or timed out)."""


class LiveDirWriteRefused(RuntimeError):
    """A task-role caller tried to use a cache or log inside the live semparse dir."""


def _real(p):
    return os.path.realpath(os.path.expanduser(str(p)))


def _inside(path, root):
    if not root:
        return False
    p, r = _real(path), _real(root)
    return p == r or p.startswith(r.rstrip(os.sep) + os.sep)


def tail_rows(path, max_bytes=LOG_TAIL_BYTES):
    """Rows of a jsonl file (only its last max_bytes); torn or corrupt lines are skipped.  Read-only."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            start = max(0, size - max_bytes)
            fh.seek(start)
            data = fh.read()
    except OSError:
        return []
    if start:
        data = data.split(b"\n", 1)[1] if b"\n" in data else b""
    out = []
    for line in data.splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict):
            out.append(r)
    return out


def _ts(r):
    t = r.get("ts")
    return float(t) if isinstance(t, (int, float)) and not isinstance(t, bool) else None


def live_root(cache_dir):
    d = os.path.normpath(str(cache_dir))
    return os.path.dirname(d) if os.path.basename(d) in ("ctx1", "spk1") else d


class ParseBudget:
    """One share (``live`` or ``task``) of the parse-call budget, counted across all of its logs."""

    def __init__(self, role, cfg=None, own_log=None, share=None, budget_dir=None, live_dir=None, cache_dir=None):
        if cfg is None:
            from . import runtime_config as rc
            cfg = rc.resolve()
        role = str(role or "task").strip().lower()
        if role not in ROLES:
            raise ValueError("parse_role must be live or task, not %r" % role)
        self.role = role
        ld = live_dir if live_dir is not None else (cfg.get("parse_live_dir") or "")
        self.live_dir = _real(ld) if ld else ""
        bd = budget_dir if budget_dir is not None else (cfg.get("parse_budget_dir") or "~/.wmtm/parse_budget")
        self.budget_dir = _real(bd)
        key = "parse_share_live_per_hour" if role == "live" else "parse_share_tasks_per_hour"
        self.share = max(0, int(share if share is not None else cfg.get(key, 10)))
        self.max_wait_s = float(cfg.get("parse_share_max_wait_s", HOUR))
        self.own_log = os.path.abspath(own_log) if own_log else None
        if role == "live":
            root = self.live_dir or (live_root(cache_dir) if cache_dir else
                                     (os.path.dirname(self.own_log) if self.own_log else None))
            if not root:
                raise ValueError("a live budget needs parse_live_dir or the live cache dir")
            self.share_dir = _real(live_root(root))
            self.ledger = os.path.join(self.share_dir, "share_ledger.jsonl")
            self.lockfile = os.path.join(self.share_dir, ".share.lock")
            self.registry = None
        else:
            for p in (cache_dir, self.own_log):
                if p and _inside(p, self.live_dir):
                    raise LiveDirWriteRefused("task caller inside the live semparse dir %s: %s" % (self.live_dir, p))
            self.share_dir = os.path.join(self.budget_dir, "tasks")
            self.ledger = os.path.join(self.share_dir, "ledger.jsonl")
            self.lockfile = os.path.join(self.share_dir, ".lock")
            self.registry = os.path.join(self.share_dir, "logs.d")

    # ------------------------------------------------------------ logs of the share
    def register_log(self, path):
        """Task share: make ``path`` a counted log of the task share (idempotent)."""
        if self.role != "task" or not path:
            return
        path = os.path.abspath(path)
        if _inside(path, self.live_dir):
            raise LiveDirWriteRefused("task log inside the live semparse dir: %s" % path)
        os.makedirs(self.registry, exist_ok=True)
        f = os.path.join(self.registry, hashlib.sha256(path.encode()).hexdigest()[:20] + ".json")
        if not os.path.exists(f):
            tmp = "%s.%d.tmp" % (f, os.getpid())
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"path": path, "registered": time.time()}, fh)
            os.replace(tmp, f)

    def logs(self):
        """Every log counted for this share (ledger first)."""
        out = [self.ledger]
        if self.role == "live":
            out += [os.path.join(self.share_dir, s, "parse_log.jsonl") for s in SUBCACHES]
        else:
            try:
                names = sorted(os.listdir(self.registry))
            except OSError:
                names = []
            for n in names:
                if not n.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(self.registry, n), encoding="utf-8") as fh:
                        p = json.load(fh).get("path")
                except (OSError, ValueError, AttributeError):
                    continue
                if p and p not in out:
                    out.append(p)
            if self.own_log and self.own_log not in out:
                out.append(self.own_log)
        return [os.path.normpath(p) for p in out]

    # ------------------------------------------------------------ counting
    def _recent(self, now):
        """(ledger call ids, extra calls from logs, oldest counted ts) in the rolling hour ending at now."""
        ids, stamps, extra = set(), [], 0
        for r in tail_rows(self.ledger):
            t = _ts(r)
            if t is not None and now - t < HOUR and r.get("call_id"):
                if r["call_id"] not in ids:
                    ids.add(r["call_id"]); stamps.append(t)
        seen = set(ids)
        for p in self.logs()[1:]:
            for r in tail_rows(p):
                t = _ts(r)
                if t is None or now - t >= HOUR or r.get("mocked") is True:
                    continue
                cids = r.get("call_ids")
                if isinstance(cids, list):
                    for c in cids:
                        if c not in seen:
                            seen.add(c); extra += 1; stamps.append(t)
                else:
                    extra += 1; stamps.append(t)
        return ids, extra, (min(stamps) if stamps else None)

    def used(self, now=None):
        now = time.time() if now is None else now
        ids, extra, _ = self._recent(now)
        return len(ids) + extra

    def remaining(self, now=None):
        return max(0, self.share - self.used(now))

    def status(self, now=None):
        now = time.time() if now is None else now
        u = self.used(now)
        return {"role": self.role, "share_per_hour": self.share, "used_last_hour": u,
                "remaining": max(0, self.share - u), "logs": len(self.logs())}

    # ------------------------------------------------------------ reservation
    @contextlib.contextmanager
    def _lock(self):
        os.makedirs(self.share_dir, exist_ok=True)
        with open(self.lockfile, "a") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)

    def _trim_ledger(self, now):
        try:
            if os.path.getsize(self.ledger) <= LEDGER_MAX_BYTES:
                return
        except OSError:
            return
        keep = [r for r in tail_rows(self.ledger, LEDGER_MAX_BYTES * 2) if (_ts(r) or 0) > now - 2 * HOUR]
        tmp = self.ledger + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.writelines(json.dumps(r) + "\n" for r in keep)
        os.replace(tmp, self.ledger)

    def reserve(self, meta=None, now=None):
        """Atomically count the share and, if there is room, write one ledger row.  -> call_id or None."""
        if self.role == "task":
            self.register_log(self.own_log)
        with self._lock():
            t = time.time() if now is None else now
            ids, extra, _ = self._recent(t)
            if len(ids) + extra >= self.share:
                return None
            self._trim_ledger(t)
            cid = uuid.uuid4().hex[:16]
            row = {"ts": t, "call_id": cid, "role": self.role, "pid": os.getpid()}
            if self.own_log:
                row["log"] = self.own_log
            row.update({k: v for k, v in (meta or {}).items() if k not in row})
            with open(self.ledger, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
            return cid

    def seconds_until_room(self, now=None):
        now = time.time() if now is None else now
        ids, extra, oldest = self._recent(now)
        if len(ids) + extra < self.share:
            return 0.0
        if oldest is None:              # share 0: never any room
            return None
        return max(0.0, oldest + HOUR - now) + 1.0

    def acquire(self, meta=None, wait=False, max_wait_s=None, clock=time.time, sleep=time.sleep):
        """Reserve one call; if the share is full, wait (bounded by max_wait_s) when wait, else raise ShareFull."""
        limit = self.max_wait_s if max_wait_s is None else float(max_wait_s)
        t0 = clock()
        while True:
            cid = self.reserve(meta, now=clock())
            if cid:
                return cid
            if self.share <= 0 or not wait:
                raise ShareFull("%s: %s share %d/h used" % (SHARE_FULL, self.role, self.share))
            dt = self.seconds_until_room(clock())
            left = limit - (clock() - t0)
            if dt is None or left <= 0:
                raise ShareFull("%s: %s share %d/h, waited %.0f s" % (SHARE_FULL, self.role, self.share, clock() - t0))
            sleep(max(0.5, min(dt, left)))


def for_cache(cache_dir, cfg, own_log=None):
    """The share a ParseCache at cache_dir belongs to (parse_role from the config; default task)."""
    role = str(cfg.get("parse_role") or "task").strip().lower()
    return ParseBudget(role, cfg=cfg, own_log=own_log or os.path.join(cache_dir, "parse_log.jsonl"),
                       cache_dir=cache_dir)


def default_budget(cfg=None):
    """Budget for a provider built without one: the task share unless the config says live."""
    if cfg is None:
        from . import runtime_config as rc
        cfg = rc.resolve()
    role = str(cfg.get("parse_role") or "task").strip().lower()
    if role == "live":
        return ParseBudget("live", cfg=cfg, cache_dir=cfg.get("semparse_dir"))
    return ParseBudget("task", cfg=cfg)


def gated(fn, budget, meta=None, wait=False, max_wait_s=None):
    """Wrap llm(system, user) so every call first reserves one call in budget (a counted ledger row).
    The wrapper exposes last_call_id and appends each id to call_ids (callers reset it per item)."""
    def call(system, user):
        call.last_call_id = None
        cid = budget.acquire(meta, wait=wait, max_wait_s=max_wait_s)
        call.last_call_id = cid
        call.call_ids.append(cid)
        return fn(system, user)

    call.last_call_id, call.call_ids, call.budget = None, [], budget
    return call


def is_share_full(err):
    return bool(err) and SHARE_FULL in str(err)


def host_status(cfg=None, now=None):
    """Both shares as seen from this host (the live dir is only read)."""
    if cfg is None:
        from . import runtime_config as rc
        cfg = rc.resolve()
    out = {"tasks": ParseBudget("task", cfg=cfg).status(now)}
    if cfg.get("parse_live_dir"):
        out["live"] = ParseBudget("live", cfg=cfg).status(now)
    return out
