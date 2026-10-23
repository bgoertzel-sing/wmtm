"""Request history for the goal engine's "addressee replied" check (v0.6.0-rc1; read-only).

Source: the channel's completed request files (``<goal_requests_dir>/*.json``, flags key ``goal_requests_dir``; empty
= no history, the engine then works from notes only).  Each file is the immutable request envelope the transport wrote
({"request_id", "prompt", "source": {chat_id, message_id, update_id[, user_id, sender_username]}, ...}); response
envelopes (no "prompt") are skipped.  Nothing here writes to that directory.

Per request the engine needs only: when (file mtime = claim time), who (the sender, resolved through the flags-file
``speaker_map`` from ``source.user_id`` / ``sender_username``, or ``chat_id`` of a private chat; never guessed from the
text) and a digest of the request text (``needs.request_digest``: topic keys, reply flag, "answers to HH:MM" times,
moot-word anchors).  The text is the prompt minus the quoted group context / document / authority blocks the
transport adds, capped at TEXT_CHARS.  Requests with no resolved sender cannot close anything and are kept as null.

Index: ``<runtime_dir>/goalchainer/requests_index.json`` (mode 600) maps file name -> [mtime, digest|null], so each
file is parsed once; it holds no raw text.  It is rebuilt when the directory or the speaker map changes.  Bounded:
files older than ``goal_requests_days`` are dropped, at most ``goal_requests_max`` newest files are considered, files
larger than MAX_FILE_BYTES are skipped.

rc2 (Track V): the window grows with the age of the oldest active item (``window_days``; at most
``goal_history_max_days``, default 45), and sender-less replies to the bot are kept as who=None (digest only) so a
group answer recorded before the transport added the sender can still close the item it answers
(``goal_close_unattributed``).  Text is alias-normalised through the speaker map before digesting.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import time

from . import needs

INDEX = "requests_index.json"
VERSION = 2           # rc2: unattributed requests kept (who=None), path anchors in the digest keys
TEXT_CHARS = 4000
MAX_FILE_BYTES = 2_000_000
_BLOCKS = re.compile(r"<(external_untrusted_[a-z_]+|current_request_authority)>.*?</\1>", re.S)


def request_text(prompt):
    """The sender's own words: transport-quoted blocks removed, whitespace trimmed, capped."""
    return _BLOCKS.sub(" ", str(prompt or "")).strip()[:TEXT_CHARS]


def sender(source, speaker_map, self_name=""):
    """Canonical name of the request's sender from the envelope only, else None."""
    from ..request_source import normalise
    from ..semparse_speaker import norm_map
    m = norm_map(speaker_map)
    if not m or not isinstance(source, dict):
        return None
    n = normalise(source)
    for k in ("user_id", "sender_id", "from_id", "sender_username", "username"):
        v = n.get(k)
        if v is None:
            continue
        name = m.get(str(v).strip().lower().lstrip("@"))
        if name and name != str(self_name or "").lower():
            return name
    return None


def _map_sha(cfg):
    return hashlib.sha256(json.dumps([cfg.get("speaker_map") or {}, cfg.get("speaker_self") or ""],
                                     sort_keys=True).encode()).hexdigest()[:16]


def _read(path, cfg):
    st = os.lstat(path)
    if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_FILE_BYTES:
        return None
    with open(path, encoding="utf-8", errors="replace") as fh:
        d = json.load(fh)
    if not isinstance(d, dict) or not isinstance(d.get("prompt"), str):
        return None
    who = sender(d.get("source"), cfg.get("speaker_map"), cfg.get("speaker_self"))
    txt = needs.canon_text(request_text(d["prompt"]), needs.alias_map(cfg.get("speaker_map")))
    if not who:
        dg = needs.request_digest(txt)
        # rc2: a sender-less reply to the bot (group envelopes before the transport recorded the sender) is kept as
        # who=None: it can close an item that it clearly answers, never address anyone or count as contact.
        return {"who": None, **dg} if dg.get("reply") else None
    return {"who": who, **needs.request_digest(txt)}


def window_days(cfg, oldest_ts=None, now=None):
    """rc2: the reply lookup covers the age of the oldest open item: max(goal_requests_days, its age + 1 d), capped
    at goal_history_max_days."""
    now = time.time() if now is None else now
    lo = float(cfg.get("goal_requests_days", 14.0))
    hi = max(lo, float(cfg.get("goal_history_max_days", 45.0)))
    if oldest_ts is None:
        return lo
    return min(hi, max(lo, (now - float(oldest_ts)) / 86400.0 + 1.0))


def load(cfg, now=None, stats=None, days=None):
    """-> [{ts, who, keys, reply, ans, moot}] oldest first, for requests from mapped senders in the window (rc2: and
    sender-less replies, who=None, when goal_close_unattributed).  days (rc2) = the window (default
    goal_requests_days; see window_days); the index keeps every file within goal_history_max_days, so a wider window
    later costs no re-parse.  Never raises; problems are reported in stats["error"]."""
    stats = {} if stats is None else stats
    d = str(cfg.get("goal_requests_dir") or "")
    if not d:
        stats["dir"] = "unset"
        return []
    now = time.time() if now is None else now
    t0 = time.time()
    rt = os.path.join(cfg.get("runtime_dir") or ".", "goalchainer")
    ipath = os.path.join(rt, INDEX)
    days = float(cfg.get("goal_requests_days", 14.0) if days is None else days)
    keep = max(days, float(cfg.get("goal_history_max_days", 45.0)))
    cap = int(cfg.get("goal_requests_max", 500))
    msha = _map_sha(cfg); ad = os.path.abspath(d)
    try:
        idx = json.load(open(ipath, encoding="utf-8"))
        if idx.get("v") != VERSION or idx.get("dir") != ad or idx.get("map") != msha:
            idx = None
    except (OSError, ValueError, AttributeError):
        idx = None
    files = dict((idx or {}).get("files") or {})
    try:
        names = [n for n in os.listdir(ad) if n.endswith(".json")]
    except OSError as e:
        stats["error"] = "%s: %s" % (type(e).__name__, "requests dir unreadable")
        return []
    cur = []
    for n in names:
        try:
            mt = os.lstat(os.path.join(ad, n)).st_mtime
        except OSError:
            continue
        if now - mt <= keep * 86400.0 and mt <= now + 60:
            cur.append((mt, n))
    cur.sort(); cur = cur[-cap:] if cap > 0 else []
    new = errs = 0; out = {}
    for mt, n in cur:
        e = files.get(n)
        if e is not None and abs(float(e[0]) - mt) < 1e-6:
            out[n] = e; continue
        try:
            rec = _read(os.path.join(ad, n), cfg)
        except (OSError, ValueError):
            rec = None; errs += 1
        out[n] = [mt, rec]; new += 1
    if new or len(out) != len(files) or idx is None:
        try:
            os.makedirs(rt, exist_ok=True)
            tmp = "%s.%d.tmp" % (ipath, os.getpid())
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            os.fchmod(fd, 0o600)        # rc2: explicit; umask / a default ACL on the dir must not widen it (seen: 640)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump({"v": VERSION, "dir": ad, "map": msha, "files": out}, fh)
            os.replace(tmp, ipath)
        except OSError:
            stats["index_write"] = "failed"
    una = bool(cfg.get("goal_close_unattributed", True))
    reqs = [dict(ts=mt, **r) for mt, r in (v for v in out.values()) if r and now - mt <= days * 86400.0
            and (r.get("who") or una)]
    reqs.sort(key=lambda r: r["ts"])
    stats.update(files=sum(1 for mt, _n in cur if now - mt <= days * 86400.0), indexed=len(cur), parsed=new,
                 read_errors=errs, with_sender=sum(1 for r in reqs if r.get("who")),
                 unattributed=sum(1 for r in reqs if not r.get("who")), days=round(days, 2),
                 s=round(time.time() - t0, 3))
    return reqs
