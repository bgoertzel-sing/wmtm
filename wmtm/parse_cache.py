"""Track H: background semantic-parse cache that feeds the PeTTaChainer shadow (Track G).

Off by default (env WMTM_SEMPARSE_FEED=1 enables).  Each cycle the orchestrator calls maybe_feed(store, cycle):
the top-K items (K = WMTM_PC_SHADOW_K, default 200) are *enqueued* by content hash; nothing is parsed in-cycle.
A detached, niced worker (scripts/pettachainer/semparse_feed_worker.py) drains the queue with the Track C
SemParseAdapter (LLM via the existing gateway, PeTTa load check) and appends validated atoms to the cache.

Guarantees
  * keyed by sha256(content): the same content is never parsed twice (an LLM/transport error may be retried,
    at most WMTM_SEMPARSE_MAX_ATTEMPTS=2 attempts in total, then cached as failed);
  * cost cap: at most WMTM_SEMPARSE_PER_HOUR (default 20) parse attempts in any rolling hour;
  * order: longest-waiting first, then highest STI;
  * items longer than WMTM_SEMPARSE_MAX_CHARS (default 1500) are skipped, not truncated;
  * tokens and time are logged per parse (parse_log.jsonl);
  * everything lives in .local-data/ (gitignored: real memory text never goes to git);
  * maybe_feed never raises and never waits; one worker at a time (pidfile guard).
"""
from __future__ import annotations
import contextlib, fcntl, hashlib, json, os, subprocess, sys, time

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.environ.get("WMTM_SEMPARSE_DIR", os.path.join(W, ".local-data", "semparse_cache"))
WORKER = os.path.join(W, "scripts", "pettachainer", "semparse_feed_worker.py")


def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def enabled() -> bool:
    return os.environ.get("WMTM_SEMPARSE_FEED", "0") == "1"


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:24]


class ParseCache:
    def __init__(self, d=None, per_hour=None, max_chars=None, max_attempts=None):
        self.d = d or DIR
        self.per_hour = per_hour if per_hour is not None else _env_int("WMTM_SEMPARSE_PER_HOUR", 20)
        self.max_chars = max_chars if max_chars is not None else _env_int("WMTM_SEMPARSE_MAX_CHARS", 1500)
        self.max_attempts = max_attempts if max_attempts is not None else _env_int("WMTM_SEMPARSE_MAX_ATTEMPTS", 2)
        self.entries_path = os.path.join(self.d, "cache.jsonl")
        self.queue_path = os.path.join(self.d, "queue.json")
        self.log_path = os.path.join(self.d, "parse_log.jsonl")
        self.reject_log = os.path.join(self.d, "rejects.jsonl")
        self.pidfile = os.path.join(self.d, "worker.pid")

    # ------------------------------------------------------------ storage
    @contextlib.contextmanager
    def _lock(self):
        os.makedirs(self.d, exist_ok=True)
        with open(os.path.join(self.d, ".lock"), "a") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)

    @staticmethod
    def _jsonl(path):
        out = []
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        out.append(json.loads(line))
                    except ValueError:          # a torn/corrupt line is skipped, never fatal
                        continue
        except OSError:
            pass
        return out

    def entries(self) -> dict:
        return {e["hash"]: e for e in self._jsonl(self.entries_path) if isinstance(e, dict) and "hash" in e}

    def _queue(self) -> dict:
        try:
            q = json.load(open(self.queue_path, encoding="utf-8"))
            return q if isinstance(q, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_queue(self, q):
        tmp = self.queue_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(q, fh)
        os.replace(tmp, self.queue_path)

    # ------------------------------------------------------------ lookup (shadow side, read-only)
    def atoms_for(self, content, entries=None):
        """Validated atoms for this content, [] if parsed with no atoms, None if not (successfully) cached."""
        e = (entries if entries is not None else self.entries()).get(content_hash(content))
        if not e or e.get("status") not in ("ok", "empty"):
            return None
        return list(e.get("atoms", []))

    # ------------------------------------------------------------ queue (cycle side)
    def enqueue(self, items, now=None) -> dict:
        """items: iterable of (item_id, content, sti).  Returns counts; never parses."""
        now = time.time() if now is None else now
        st = {"cached": 0, "queued_new": 0, "queued_known": 0, "skipped_long": 0}
        with self._lock():
            ent, q = self.entries(), self._queue()
            for iid, content, sti in items:
                if not isinstance(content, str) or not content.strip():
                    continue
                h = content_hash(content)
                if h in ent:
                    st["cached"] += 1; continue
                if len(content) > self.max_chars:
                    st["skipped_long"] += 1; continue
                if h in q:
                    q[h]["sti"] = max(float(sti), q[h].get("sti", 0.0)); st["queued_known"] += 1
                else:
                    q[h] = {"item_id": str(iid), "content": content, "sti": float(sti), "first_seen": now,
                            "attempts": 0, "chars": len(content)}
                    st["queued_new"] += 1
            self._save_queue(q)
        st["queue_len"] = len(q)
        return st

    def used_last_hour(self, now=None) -> int:
        now = time.time() if now is None else now
        return sum(1 for r in self._jsonl(self.log_path) if now - r.get("ts", 0) < 3600)

    def budget(self, now=None) -> int:
        return max(0, self.per_hour - self.used_last_hour(now))

    def next_batch(self, n):
        q, ent = self._queue(), self.entries()
        rows = [(h, v) for h, v in q.items() if h not in ent]
        rows.sort(key=lambda kv: (kv[1].get("first_seen", 0), -kv[1].get("sti", 0.0)))
        return rows[:max(0, n)]

    def pending(self) -> int:
        return len(self.next_batch(10 ** 9))

    def record(self, h, q, status, atoms, cost):
        """Log one attempt; cache the result unless it was a retryable LLM error."""
        with self._lock():
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(cost) + "\n")
            qq = self._queue(); cur = qq.get(h, q); cur["attempts"] = cur.get("attempts", 0) + 1
            if status == "llm_error" and cur["attempts"] < self.max_attempts:
                qq[h] = cur
            else:
                with open(self.entries_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"hash": h, "item_id": q["item_id"], "status": status, "atoms": atoms,
                                         "ts": cost.get("ts"), "attempts": cur["attempts"]}) + "\n")
                qq.pop(h, None)
            self._save_queue(qq)


# ---------------------------------------------------------------- worker body (pure; tests call it directly)
def process_queue(cache: ParseCache, llm, loader=None, n=None, adapter=None, now=time.time):
    """Parse up to min(n, hourly budget) queued items.  Returns the list of per-parse cost records."""
    from .semparse_adapter import SemParseAdapter
    ad = adapter or SemParseAdapter(llm, loader=loader, reject_log=cache.reject_log, max_chars=cache.max_chars)
    n = cache.per_hour if n is None else n
    out = []
    for h, q in cache.next_batch(min(n, cache.budget(now()))):
        if cache.budget(now()) <= 0:
            break
        if hasattr(llm, "last_usage"):
            llm.last_usage = {}
        t = time.time()
        try:
            res = ad.parse_item(q["item_id"], q["content"])
            err = res.error
        except Exception as e:                      # adapter bug: treat as a failed parse, keep going
            res, err = None, "adapter error: %s" % type(e).__name__
        dt = round(time.time() - t, 3)
        if err and (err.startswith("llm error") or err.startswith("adapter error")):
            status = "llm_error"
        elif err:
            status = "failed"
        else:
            status = "ok" if res.accepted else "empty"
        u = dict(getattr(llm, "last_usage", None) or {})
        cost = {"ts": now(), "hash": h, "item_id": q["item_id"], "chars": q.get("chars"), "secs": dt, "status": status,
                "wait_s": round(now() - q.get("first_seen", now()), 1),
                "prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens"),
                "total_tokens": u.get("total_tokens"),
                "accepted": len(res.accepted) if res else 0, "rejected": len(res.rejected) if res else 0}
        if err:
            cost["error"] = err[:160]
        cache.record(h, q, status, list(res.accepted) if res and status in ("ok", "empty") else [], cost)
        out.append(cost)
    return out


def gateway_llm_usage(timeout=300.0, env_file=None):
    """Like semparse_adapter.gateway_llm, but keeps the reply's token usage in call.last_usage."""
    import urllib.request
    env_file = env_file or os.environ.get("WMTM_LLM_ENV_FILE", "")
    env = {}
    if env_file and os.path.exists(os.path.expanduser(env_file)):
        for line in open(os.path.expanduser(env_file), encoding="utf-8"):
            if "=" in line and not line.startswith("#"):
                k, v = line.rstrip("\n").split("=", 1); env[k] = v.strip()
    base = os.environ.get("BASE_URL") or env.get("BASE_URL")
    model = os.environ.get("LLM_MODEL") or env.get("LLM_MODEL")
    key = os.environ.get("AI_API_KEY") or env.get("AI_API_KEY")

    def call(system, user):
        body = {"model": model, "temperature": 0,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        r = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        call.last_usage = r.get("usage") or {}
        return r["choices"][0]["message"]["content"]
    call.last_usage = {}
    call.model = model
    return call


# ---------------------------------------------------------------- cycle hook
def _busy(pidfile):
    try:
        pid = int(open(pidfile).read().strip()); os.kill(pid, 0); return True
    except (OSError, ValueError):
        return False


def launch_worker(cache: ParseCache, worker=None, extra=()):
    """Start the detached niced parse worker if there is work and budget.  Never waits.  -> pid or None."""
    if _busy(cache.pidfile) or cache.budget() <= 0 or cache.pending() == 0:
        return None
    cmd = [sys.executable, "-u", worker or WORKER, "--dir", cache.d] + list(extra)
    pre = ["nice", "-n", "19"] + (["ionice", "-c", "3"] if os.path.exists("/usr/bin/ionice") else [])
    p = subprocess.Popen(pre + cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         cwd=W, start_new_session=True, close_fds=True)
    with open(cache.pidfile, "w") as fh:
        fh.write(str(p.pid))
    return p.pid


def top_k_rows(store, k=None):
    k = int(k or os.environ.get("WMTM_PC_SHADOW_K", "200"))
    return [(it.id, it.content, it.attention.sti) for it in store.get_active_set()[:k]]


def maybe_feed(store, cycle=0, cache=None):
    """Orchestrator hook: enqueue top-K, maybe start the worker.  Returns pid or None; swallows every error."""
    if not enabled():
        return None
    try:
        cache = cache or ParseCache()
        cache.enqueue(top_k_rows(store))
        return launch_worker(cache)
    except Exception:
        return None
