"""Track H: background semantic-parse cache that feeds the PeTTaChainer shadow (Track G).

Off by default.  Enabled per bot by ``"semparse_feed": true`` in ``<state_dir>/_wmtm_flags.json`` (or env
WMTM_SEMPARSE_FEED=1); knobs in wmtm/runtime_config.py.  Each cycle the orchestrator calls
maybe_feed(store, cycle, state_dir): the top-K items (K = shadow_k, default 200) are *enqueued* by content hash;
nothing is parsed in-cycle.  A detached, niced worker (``python -m wmtm.workers.semparse_feed``) drains the queue
with the Track C SemParseAdapter (LLM via the existing gateway, PeTTa load check) and appends validated atoms to
the cache.

Guarantees
  * keyed by sha256(content): the same content is never parsed twice (an LLM/transport error may be retried,
    at most parse_max_attempts=2 attempts in total, then cached as failed);
  * cost cap: at most parse_cap_per_hour (default 20) parse attempts in any rolling hour;
  * order: longest-waiting first, then highest STI;
  * items longer than parse_max_chars (default 1500) are skipped, not truncated;
  * tokens and time are logged per parse (parse_log.jsonl); logs are size-capped (rotated to .1);
  * everything lives in the runtime dir (default <state_dir>/_wmtm_shadow/, i.e. inside the bot's memory dir);
  * maybe_feed never raises and never waits; one worker at a time (pidfile guard).
"""
from __future__ import annotations
import contextlib, fcntl, json, os, time
try:    # the builtin sha256 avoids importing hashlib/OpenSSL (~3 ms) on the automated fast path (rc2); same digest
    from _sha256 import sha256 as _sha256
except ImportError:
    try:
        from _sha2 import sha256 as _sha256
    except ImportError:
        from hashlib import sha256 as _sha256

from . import runtime_config as rc

WORKER_MODULE = "wmtm.workers.semparse_feed"
WORKER_MAX_AGE = 3 * 3600     # s; an older worker is presumed hung and killed by the next launch


def enabled(cfg=None) -> bool:
    return bool((cfg or rc.resolve())["semparse_feed"])


def content_hash(text: str) -> str:
    return _sha256(text.encode("utf-8", "replace")).hexdigest()[:24]


class ParseCache:
    def __init__(self, d=None, per_hour=None, max_chars=None, max_attempts=None, cfg=None,
                 log_max_bytes=None, cache_max_bytes=None):
        cfg = cfg or rc.resolve()
        self.d = d or cfg["semparse_dir"]
        self.per_hour = per_hour if per_hour is not None else cfg["parse_cap_per_hour"]
        self.max_chars = max_chars if max_chars is not None else cfg["parse_max_chars"]
        self.max_attempts = max_attempts if max_attempts is not None else cfg["parse_max_attempts"]
        self.log_max_bytes = log_max_bytes if log_max_bytes is not None else cfg["jsonl_max_bytes"]
        self.cache_max_bytes = cache_max_bytes if cache_max_bytes is not None else cfg["cache_max_bytes"]
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
            fh.write(json.dumps(q))         # same text as json.dump, via the C encoder (~10x faster)
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
            st["pending"] = sum(1 for h in q if h not in ent)
        st["queue_len"] = len(q)
        return st

    def used_last_hour(self, now=None) -> int:
        now = time.time() if now is None else now
        return sum(1 for r in self._jsonl(self.log_path) if now - r.get("ts", 0) < 3600)

    def _trim_log(self, now):
        """Size cap for parse_log.jsonl that never loses the rolling hour the cost cap is computed from:
        records older than 1 h move to parse_log.jsonl.1 (replacing it); recent ones stay.  Caller holds the lock."""
        try:
            if not self.log_max_bytes or os.path.getsize(self.log_path) <= self.log_max_bytes:
                return False
        except OSError:
            return False
        rows = self._jsonl(self.log_path)
        old = [r for r in rows if now - r.get("ts", 0) >= 3600]
        new = [r for r in rows if now - r.get("ts", 0) < 3600]
        for path, rs in ((self.log_path + ".1", old), (self.log_path, new)):
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.writelines(json.dumps(r) + "\n" for r in rs)
            os.replace(tmp, path)
        return True

    def compact(self):
        """Size cap for cache.jsonl: keep the newest entry per hash; if still over cache_max_bytes, drop the oldest
        entries (they are re-parsed only if their content comes back, under the hourly cap).  Caller holds the lock."""
        if not self.cache_max_bytes or self.cache_max_bytes <= 0:
            return 0
        try:
            if os.path.getsize(self.entries_path) <= self.cache_max_bytes:
                return 0
        except OSError:
            return 0
        latest = {}
        for e in self._jsonl(self.entries_path):
            if isinstance(e, dict) and "hash" in e:
                latest.pop(e["hash"], None); latest[e["hash"]] = e        # dict keeps insertion order: newest last
        lines = [json.dumps(e) + "\n" for e in latest.values()]
        total, keep = 0, []
        for ln in reversed(lines):
            total += len(ln.encode("utf-8"))
            if total > self.cache_max_bytes // 2:                         # leave headroom so we do not compact every write
                break
            keep.append(ln)
        keep.reverse()
        tmp = self.entries_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.writelines(keep)
        os.replace(tmp, self.entries_path)
        return len(lines) - len(keep)

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
            self._trim_log(cost.get("ts") or time.time())
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(cost) + "\n")
            qq = self._queue(); cur = qq.get(h, q); cur["attempts"] = cur.get("attempts", 0) + 1
            if status == "llm_error" and cur["attempts"] < self.max_attempts:
                qq[h] = cur
            else:
                with open(self.entries_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"hash": h, "item_id": q["item_id"], "status": status, "atoms": atoms,
                                         "ts": cost.get("ts"), "attempts": cur["attempts"],
                                         "prompt_sha": cost.get("prompt_sha")}) + "\n")
                qq.pop(h, None)
                self.compact()
            self._save_queue(qq)


# ---------------------------------------------------------------- worker body (pure; tests call it directly)
def process_queue(cache: ParseCache, llm, loader=None, n=None, adapter=None, now=time.time, prompt_path=None,
                  preamble=None):
    """Parse up to min(n, hourly budget) queued items.  Returns the list of per-parse cost records.

    preamble: v0.5 (Track M) flag ``semparse_preamble`` (None = adapter default: on).  The cache stays keyed by
    content hash only, so entries parsed with an older prompt are reused, never re-parsed; each new attempt records
    the short sha of the prompt actually sent (``prompt_sha``) in parse_log.jsonl and cache.jsonl."""
    from .semparse_adapter import SemParseAdapter, DEFAULT_PROMPT
    ad = adapter or SemParseAdapter(llm, loader=loader, prompt_path=prompt_path or DEFAULT_PROMPT,
                                    reject_log=cache.reject_log, max_chars=cache.max_chars,
                                    reject_log_max_bytes=cache.log_max_bytes, preamble=preamble)
    psha = (getattr(ad, "prompt_sha256", None) or "")[:16] or None
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
                "accepted": len(res.accepted) if res else 0, "rejected": len(res.rejected) if res else 0,
                "prompt_sha": psha}
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
                k, v = line.rstrip("\n").split("=", 1); env[k.strip().replace("export ", "", 1).strip()] = v.strip().strip('"').strip("'")
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
def launch_worker(cache: ParseCache, cfg=None, module=None, extra=(), pending=None):
    """Start the detached niced parse worker if there is work and budget.  Never waits.  -> pid or None.
    pending: queue length already known from enqueue() (saves re-reading the cache)."""
    if rc.busy(cache.pidfile, WORKER_MAX_AGE) or cache.budget() <= 0:
        return None
    if (cache.pending() if pending is None else pending) == 0:
        return None
    cfg = dict(cfg or rc.resolve()); cfg["semparse_dir"] = cache.d
    cpath = os.path.join(cache.d, "worker_config.json")
    rc.write_json_atomic(cpath, cfg)
    return rc.spawn_worker(cfg, module or WORKER_MODULE, ["--dir", cache.d, "--config", cpath] + list(extra),
                           cache.pidfile)


def top_k_rows(store, k):
    return [(it.id, it.content, it.attention.sti) for it in store.get_active_set()[:int(k)]]


FEED_SIG = "last_feed.sig"     # automated fast path: top-K content signature of the last enqueue


def feed_rows(rows, cfg=None, state_dir=None, cache=None, skip_unchanged=False):
    """Enqueue (item_id, content, sti) rows (active-set order) and maybe start the worker.  Shared by the
    orchestrator hook and the automated fast path.  skip_unchanged=True (fast path): if the top-K contents are the
    ones enqueued last time, skip the enqueue (it would only re-read the whole cache to find nothing new) and
    use the queue length as the pending count.  Returns pid or None; swallows every error."""
    try:
        cfg = cfg or rc.resolve(state_dir)
        if not cfg["semparse_feed"]:
            return None
        cache = cache or ParseCache(cfg=cfg)
        rows = list(rows)[:int(cfg["shadow_k"])]
        if skip_unchanged:
            sig = _sha256("\n".join(content_hash(c) for _, c, _ in rows if isinstance(c, str)).encode()).hexdigest()
            sp = os.path.join(cache.d, FEED_SIG)
            try:
                with open(sp, encoding="utf-8") as fh:
                    same = fh.read().strip() == sig
            except OSError:
                same = False
            if same:
                return launch_worker(cache, cfg, pending=len(cache._queue()))
            st = cache.enqueue(rows)
            try:
                with open(sp, "w", encoding="utf-8") as fh:
                    fh.write(sig + "\n")
            except OSError:
                pass
        else:
            st = cache.enqueue(rows)
        return launch_worker(cache, cfg, pending=st.get("pending"))
    except Exception:
        return None


def maybe_feed(store, cycle=0, state_dir=None, cache=None, cfg=None):
    """Orchestrator hook: enqueue top-K, maybe start the worker.  Returns pid or None; swallows every error."""
    try:
        cfg = cfg or rc.resolve(state_dir)
        if not cfg["semparse_feed"]:
            return None
        return feed_rows(top_k_rows(store, cfg["shadow_k"]), cfg, cache=cache)
    except Exception:
        return None
