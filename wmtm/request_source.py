"""Track Q: where the current request came from (for speaker linking).

The host passes the request source to ``WMTM.context_for(..., source=...)``.  When it does not (the Iter adapter
calls ``context_for(user_msg)`` only), ``from_iter_env`` reads it the way Iter's own tools do: the turn's bound
request id from ``ITER_REQUEST_IDS`` (JSON {channel: request_id}, set by Iter for every tool/transformation
subprocess while request binding is on), else the single open request, under
``$ITER_OUTER_CHANNEL_ROOT/processing/<request_id>.json``.  Read only; never raises; None when anything is off.

Only what speaker linking needs is kept (``normalise``):
  * private chat (Telegram chat_id > 0 is the sender's user id): {"user_id": <chat_id>, "chat_type": "private"};
  * group chat (chat_id < 0): {"chat_type": "group"} -- the envelope has no sender, so the speaker comes from the
    text routes only (see wmtm.semparse_speaker);
  * sender fields a richer envelope may carry (user_id / sender_id / from_id / sender_username / username) are
    passed through as they are.
A request file whose prompt does not contain the start of the user message is ignored (request_mismatch), so a
stale or foreign request never names the speaker.
"""
import json
import os
import re

RID_RX = re.compile(r"^[0-9a-f]{16,128}$")
PASS_KEYS = ("user_id", "sender_id", "from_id", "sender_username", "username")


def normalise(src):
    """Raw request source envelope -> the minimal dict speaker linking uses ({} when nothing usable)."""
    if not isinstance(src, dict):
        return {}
    out = {}
    for k in PASS_KEYS:
        v = src.get(k)
        if isinstance(v, bool) or v is None:
            continue
        if isinstance(v, (int, str)) and str(v).strip():
            out[k] = v if isinstance(v, int) else str(v).strip()[:64]
    cid = src.get("chat_id")
    if isinstance(cid, int) and not isinstance(cid, bool):
        if cid > 0:
            out.setdefault("user_id", cid)
            out["chat_type"] = "private"
        elif cid < 0:
            out["chat_type"] = "group"
    return out


def _request_path(environ):
    root = environ.get("ITER_OUTER_CHANNEL_ROOT") or ""
    if not root:
        return None
    proc = os.path.join(root, "processing")
    raw = environ.get("ITER_REQUEST_IDS")
    if raw is not None:
        try:
            ids = json.loads(raw)
        except ValueError:
            return None
        vals = sorted({v for v in (ids.values() if isinstance(ids, dict) else []) if isinstance(v, str)})
        if len(vals) != 1 or not RID_RX.match(vals[0]):
            return None
        return os.path.join(proc, vals[0] + ".json")
    try:
        open_ = sorted(f for f in os.listdir(proc) if f.endswith(".json"))
    except OSError:
        return None
    if len(open_) != 1 or not RID_RX.match(open_[0][:-5]):
        return None
    return os.path.join(proc, open_[0])


def _matches(prompt, user_msg):
    """The adapter's user message is the direct-request tail of the prompt: its start must occur in the prompt."""
    if not user_msg:
        return True
    head = " ".join(user_msg.split())[:40]
    if "[attached document" in head:
        head = head.split("[attached document", 1)[0].strip()
    if len(head) < 8:
        return True
    return head in " ".join((prompt or "").split())


def from_iter_env(user_msg=None, environ=None, stats=None):
    """-> normalised source dict of the current Iter request, or None.  stats (dict) gets "how"."""
    env = os.environ if environ is None else environ
    st = stats if isinstance(stats, dict) else {}
    try:
        p = _request_path(env)
        if not p:
            st["how"] = "no_request"
            return None
        with open(p, encoding="utf-8") as fh:
            req = json.load(fh)
        if not isinstance(req, dict) or not isinstance(req.get("source"), dict):
            st["how"] = "no_source"
            return None
        if not _matches(req.get("prompt"), user_msg):
            st["how"] = "request_mismatch"
            return None
        out = normalise(req["source"])
        st["how"] = "iter_env"
        return out or None
    except Exception:                               # noqa: BLE001
        st["how"] = "error"
        return None
