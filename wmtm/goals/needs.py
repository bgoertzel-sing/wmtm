"""Track R / R2: need estimation.  Pure functions over raw item dicts (pc_shadow.raw_item shape:
id, content, sti, source_type, optional origin_ts / queries).

R2 rules (from the Track R ratings):
 1. resolved detection: a newer note on the same topic supersedes older ones; an item closes when a later note says it
    is done / answered / decided (DECISION, RESOLVED, "answered", "delivered") or when the addressee sent a request
    after it that mentions the topic.  Status is evaluated at `now` (the proposal date), using everything up to now.
 2. explicit items only: open items come only from explicit markers ("Open question(s) for X:", "Blocked on X:",
    "PENDING:", "Still pending:", "Still open:", "waiting on X", "NOT delivered"), kept as whole sentences (never cut),
    deduped by topic.
 3. addressees: the owner is resolved via the speaker_map (never "user"); "the user" / "their" resolve to the person
    whose request came last before the note; the bot's own to-dos become self-tasks; unresolvable items are dropped.
 4. timing lives in actions.py / engine.py (remind after >= 1 day, no re-proposal within 3 days)."""
from __future__ import annotations

import re
import time

SELF = "self"
STOP = set("""that this with from have will what when which where would should could there their about into than then
them they were been being does done also only just more most some such very your ours note notes the and for are was
not but can its it's all any one two now yet still open question questions pending next after before over under
whether user asked ask waiting blocked""".split())
_ID_TS = re.compile(r"(\d{8})T(\d{6})Z")
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_SPLIT = re.compile(r"(?<=[.?!])\s+(?=[A-Z\"'(\[])|\n+")
_OWNER = r"(?P<o>the user|[A-Za-z][\w]*(?:/[A-Za-z]\w*)?)"
MARKERS = (
    ("question", re.compile(r"\bopen questions? (?:for|to) " + _OWNER + r"\s*:\s*", re.I)),
    ("question", re.compile(r"\bblocked on " + _OWNER + r"\s*:\s*", re.I)),
    ("pending", re.compile(r"\b(?:still )?waiting on " + _OWNER + r"(?:'s)?\b", re.I)),
    ("pending", re.compile(r"\b(?:still )?pending:\s*|\bstill open:\s*", re.I)),
    ("self", re.compile(r"\bNOT delivered\b")),
)
_FRAGMENT = re.compile(r"^\s*(that|it|this|these|those|they|he|she|LINK|SUPPORTS|CONTRADICTS)\b", re.I)
_RES = re.compile(r"\b(DECISION|RESOLVED|DECIDED|ANSWERED|answered|answers? (?:to|from)|decided|closed|settled|moot|"
                  r"delivered|(?:is|was|now|already) done)\b", re.I)
_NEG_BEFORE = re.compile(r"(n't|\bnot|\bnever|\bun|\byet to|\bno)\s*$", re.I)
_ASKS = re.compile(r"\b(questions?|approval|answers?|decide|decision|choice|choose|OK)\b")
_ANS_TIME = re.compile(r"\banswers? to (?:the |your |my |his |her )?(\d{1,2}:\d{2})", re.I)
_MOOT = re.compile(r"\b(gone|removed?|removing|drop(ped)?|retired?|no longer)\b", re.I)
_PRONOUN_OWNER = {"the user", "user", "their", "them", "they", "you", "your"}
_SELF_WORDS = {"me", "i", "myself"}
MAX_SENT = 400


_ENTITY = re.compile(r"\b([A-Za-z]*[a-z][A-Z][A-Za-z]*|[A-Z]{3,}[a-z]?|[a-z_]+(?=\.(?:py|metta|md|json)\b))\b")
_CAPS_STOP = {"PENDING", "DECISION", "RESOLVED", "DECIDED", "ANSWERED", "NOT", "LINK", "SUPPORTS", "CONTRADICTS", "DONE",
              "NEW", "LESSON", "CORRECTION", "USER", "PREFERENCE", "LTM", "OK"}


def keys(text):
    raw = text or ""
    t = re.sub(r"\btrack[ -]([a-z])\b(?!-)", r"track_\1", raw.lower())
    ks = {w for w in re.findall(r"[a-z0-9_]{4,}", t) if w not in STOP}
    for m in _ENTITY.finditer(raw):
        w = m.group(1)
        if w.upper() in _CAPS_STOP:
            continue
        ks.add("@" + w.lower())
    return ks


def plain(ks):
    return {k for k in ks if not k.startswith("@")}


def strong(ks):
    """Topic anchors: commit hashes and track letters."""
    return {k for k in ks if k.startswith("track_") or k.startswith("@") or (re.fullmatch(r"[0-9a-f]{7,40}", k) and re.search(r"\d", k)
                                                         and re.search(r"[a-f]", k))}


def topic_match(a, b):
    """Same topic: shared keys >= max(2, 40% of the smaller set), or a shared anchor plus 2 shared keys."""
    if not a or not b:
        return False
    pa, pb = plain(a), plain(b); sh = pa & pb
    if pa and pb and len(sh) >= max(2, 0.4 * min(len(pa), len(pb))):
        return True
    anch = strong(a) & strong(b)
    return bool(anch) and len(sh | {x for x in anch if x.startswith("@")}) >= 2 and len(sh) >= 1


def item_ts(raw, now):
    t = float(raw.get("origin_ts") or 0.0)
    if t > 0:
        return t
    m = _ID_TS.search(str(raw.get("id") or ""))
    if m:
        try:
            import calendar
            return float(calendar.timegm(time.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")))
        except ValueError:
            pass
    return float(raw.get("created_at") or now)


def people_patterns(speaker_map):
    """flags-file speaker_map (id/username -> canonical name) -> [(name, regex)]; numeric ids are skipped."""
    by = {}
    for k, v in (speaker_map or {}).items():
        for t in (str(k), str(v)):
            if t and not t.isdigit():
                by.setdefault(str(v), set()).add(re.escape(t.lower()))
    return [(n, re.compile(r"\b(" + "|".join(sorted(ts)) + r")\b", re.I)) for n, ts in by.items()]


def who_of(text, people=()):
    """First person named in text (canonical name), else None.  Never returns "user"."""
    best = None
    for name, pat in people:
        m = pat.search(text or "")
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), name)
    return best[1] if best else None


def sentences(text):
    text = _COMMENT.sub(" ", text or "")
    return [s.strip() for s in _SPLIT.split(text) if len(s.strip()) >= 12]


def res_hit(s):
    """Position of a non-negated resolution word in s, else -1."""
    for m in _RES.finditer(s or ""):
        if not _NEG_BEFORE.search(s[max(0, m.start() - 8):m.start()]):
            return m.start()
    return -1


def marker(sentence):
    """-> (kind, owner_token, match) for the first explicit marker, else None."""
    best = None
    for kind, pat in MARKERS:
        m = pat.search(sentence)
        if m and (best is None or m.start() < best[2].start()):
            best = (kind, (m.groupdict().get("o") or ""), m)
    return best


def classify(sentence):
    """-> 'question' | 'pending' | 'self' | None.  A resolution word before the marker = a report that it closed."""
    mk = marker(sentence)
    if not mk:
        return None
    r = res_hit(sentence)
    if 0 <= r < mk[2].start():
        return None
    return mk[0]


def requester_at(requests, ts):
    """Person whose request arrived last at or before ts (who the bot was talking to), else None."""
    best = None
    for r in requests or ():
        if r.get("who") and float(r["ts"]) <= ts and (best is None or float(r["ts"]) > float(best["ts"])):
            best = r
    return best["who"] if best else None


_NOT_OWNER = {"which", "whether", "what", "how", "when", "where", "a", "an", "the", "this", "that", "it", "two", "three",
              "review", "approval", "confirmation", "feedback", "input", "results"}


def resolve_owner(tok, body, people, self_name, requester):
    t = (tok or "").strip().lower()
    if t in _NOT_OWNER:
        t, tok = "", ""
    if t in _PRONOUN_OWNER:
        return requester
    if t in _SELF_WORDS or (self_name and t == self_name.lower()):
        return SELF
    if t:
        w = who_of(tok, people)
        if w:
            return w
    w = None
    for name, pat in people:
        m = pat.search(body or "")
        if m and (w is None or m.start() < w[0]):
            w = (m.start(), name)
    u = re.search(r"\b(the user|their|they)\b", body or "", re.I)
    if u and requester and (w is None or u.start() < w[0]):
        return requester
    if w:
        return w[1]
    if u:
        return requester
    if requester and _ASKS.search(body or ""):     # "Still open: the 4 questions / needs approval" -> the requester
        return requester
    return None


def candidate(sentence, people=(), self_name="", requester=None):
    """One sentence -> dict(kind, who, text, body) or (None, drop_reason)."""
    mk = marker(sentence)
    if not mk:
        return None, "no_marker"
    kind, tok, m = mk
    r = res_hit(sentence)
    if 0 <= r < m.start():
        return None, "resolution_report"
    text = sentence
    if _FRAGMENT.match(text):                      # "LINK: ... Still open: X" -> start at the marker's clause
        text = sentence[m.start():]
        if _FRAGMENT.match(text) or len(text) < 12:
            return None, "fragment"
    if len(text) > MAX_SENT:
        return None, "too_long"
    body = sentence[m.end():].strip() if kind == "question" else text
    if len(body) < 12:
        return None, "fragment"
    who = resolve_owner(tok, sentence[m.start():], people, self_name, requester)
    if kind == "self":
        who = SELF
    elif who is None:
        if kind == "pending" and not tok:          # "PENDING: diff these ..." with no person = the bot's own to-do
            who, kind = SELF, "self"
        else:
            return None, "no_owner"
    elif who == SELF:
        kind = "self"
    return {"kind": kind, "who": who, "text": text, "body": body}, None


def request_digest(text):
    """What the reply checks need from a request text (no raw text kept): topic keys, the reply flag,
    "answers to HH:MM" times and the anchors near moot words."""
    t = str(text or "")
    moot = set()
    for m in _MOOT.finditer(t):
        moot |= strong(keys(t[max(0, m.start() - 40):m.end() + 40]))
    return {"keys": sorted(keys(t)), "reply": t.lstrip().startswith("[reply to"),
            "ans": [m.group(1) for m in _ANS_TIME.finditer(t)], "moot": sorted(moot)}


def _req_view(r):
    """A request as {keys(set), reply, ans, moot(set)}: from a stored digest, or computed from its text."""
    if "keys" in r:
        return {"keys": set(r.get("keys") or ()), "reply": bool(r.get("reply")), "ans": list(r.get("ans") or ()),
                "moot": set(r.get("moot") or ())}
    v = request_digest(r.get("text"))
    v["keys"] = set(v["keys"]); v["moot"] = set(v["moot"])
    return v


def _req_moot_or_answered(sig, v):
    for t in v["ans"]:
        if re.search(r"\b" + re.escape(t) + r"\b", sig["text"]):
            return "closed_answers_to_time"
    if v["moot"] & strong(sig["keys"]):
        return "closed_moot"
    return None


def _moot_or_answered(sig, s):
    for m in _ANS_TIME.finditer(s or ""):
        if re.search(r"\b" + re.escape(m.group(1)) + r"\b", sig["text"]):
            return "closed_answers_to_time"
    for m in _MOOT.finditer(s or ""):
        near = keys(s[max(0, m.start() - 40):m.end() + 40])
        if strong(near) & strong(sig["keys"]):
            return "closed_moot"
    return None


def _closed(sig, later, requests, now):
    """-> reason string if a later note or an addressee request closes sig (status at `now`), else None."""
    for ts, ss in later:
        if ts <= sig["ts_last"] or ts > now:
            continue
        for s in ss:
            why = _moot_or_answered(sig, s)
            if why:
                return why + "_note"
    views = [(r, _req_view(r)) for r in requests or () if r.get("who") and sig["ts_last"] < float(r["ts"]) <= now]
    for r, v in views:
        why = _req_moot_or_answered(sig, v)
        if why:
            return why + "_reply"
    for ts, ss in later:
        if ts <= sig["ts_last"] or ts > now:
            continue
        for s in ss:
            p = res_hit(s)
            if p < 0:
                continue
            mk = marker(s)
            if mk and mk[2].start() <= p:          # a restatement that it's still open, not a closure
                continue
            if topic_match(sig["keys"], keys(s)):
                return "closed_by_note"
    if sig["who"] and sig["who"] != SELF:
        for r, v in views:
            if r.get("who") != sig["who"]:
                continue
            sh = len(sig["keys"] & v["keys"])
            if sh >= 2 or (sh >= 1 and v["reply"]):
                return "closed_by_reply"
    return None


def extract(raw_items, now=None, people=(), requests=(), self_name="", trace=None):
    """-> open signals {kind, need, text, body, keys, ts (oldest), ts_last, sal, items, who, origin, last_contact}.
    trace (optional list) receives (item_id, sentence, reason) for every dropped marker sentence / closed signal."""
    now = time.time() if now is None else now
    reqs = [r for r in requests or () if float(r.get("ts", 0)) <= now]
    items = [r for r in raw_items or [] if r.get("source_type", "recalled") == "recalled" and r.get("content")]
    items.sort(key=lambda r: item_ts(r, now))
    smax = max([float(r.get("sti") or 0.0) for r in items] + [1e-9])
    per, sigs = [], []
    for r in items:
        ts = item_ts(r, now); sal = max(0.0, min(1.0, float(r.get("sti") or 0.0) / smax))
        ss = sentences(r["content"]); per.append((ts, ss))
        req = requester_at(reqs, ts)
        cands = []
        for s in ss:
            c, why = candidate(s, people, self_name, req)
            if c:
                cands.append((c, "text"))
            elif trace is not None and why != "no_marker":
                trace.append((r.get("id"), s, why))
        for q in r.get("queries") or ():
            cands.append(({"kind": "question", "who": None, "text": str(q), "body": str(q)}, "parser"))
        for c, origin in cands:
            k = keys(c["body"] if c["kind"] == "question" else c["text"])
            if len(k) < 2:
                continue
            need = "unc" if c["kind"] == "question" else "comp"
            cur = next((g for g in sigs if g["need"] == need and g["origin"] == origin and topic_match(g["keys"], k)), None)
            if cur is None:
                sigs.append({"kind": c["kind"], "need": need, "text": c["text"], "body": c["body"], "keys": k, "ts": ts,
                             "ts_last": ts, "sal": sal, "items": [r.get("id")], "who": c["who"], "origin": origin,
                             "req": req})
            else:                                  # newest note on the topic supersedes the older wording
                if trace is not None:
                    trace.append((r.get("id"), cur["text"], "superseded"))
                cur.update(kind=c["kind"], text=c["text"], body=c["body"], keys=k, ts_last=max(cur["ts_last"], ts),
                           who=c["who"] or cur["who"], req=req or cur.get("req"))
                cur["ts"] = min(cur["ts"], ts); cur["sal"] = max(cur["sal"], sal)
                if r.get("id") not in cur["items"]:
                    cur["items"].append(r.get("id"))
    out = []
    for g in sigs:
        why = _closed(g, per, reqs, now)
        if why:
            if trace is not None:
                trace.append((g["items"][-1], g["text"], why))
            continue
        lc = [float(x["ts"]) for x in reqs if g["who"] and x.get("who") == g["who"]]
        g["last_contact"] = max(lc) if lc else 0.0
        out.append(g)
    out.sort(key=lambda s: (-s["sal"], s["ts"]))
    return out


def weight(sig, now, age_cap_d=7.0):
    age_d = max(0.0, (now - sig["ts"]) / 86400.0)
    return (0.5 + 0.5 * sig["sal"]) * (0.5 + 0.5 * min(age_d, age_cap_d) / max(age_cap_d, 1e-9))


def level(signals, now, scale=1.0, age_cap_d=7.0):
    """Satisfaction level in (0, 1]: 1 = nothing open."""
    load = sum(weight(s, now, age_cap_d) for s in signals)
    return 1.0 / (1.0 + load / max(scale, 1e-9))


def urge(lvl, target, w=1.0):
    """u = w * phi(target - level); phi = deficit relative to target, clipped to [0, 1] (no urge above target)."""
    if target <= 0:
        return 0.0
    return w * max(0.0, min(1.0, (target - lvl) / target))


def estimate(raw_items, now=None, st=None, extra_signals=(), trace=None):
    now = time.time() if now is None else now
    st = st or {}
    sigs = extract(raw_items, now, st.get("people", ()), st.get("requests", ()), st.get("self_name", ""),
                   trace) + list(extra_signals)
    out = {}
    for n in ("unc", "comp"):
        ss = [s for s in sigs if s["need"] == n]
        lv = level(ss, now, st.get("scale", 1.0), st.get("age_cap_d", 7.0))
        t = st.get("targets", {}).get(n, 0.8); w = st.get("weights", {}).get(n, 1.0)
        out[n] = {"signals": ss, "level": round(lv, 4), "target": t, "weight": w, "urge": round(urge(lv, t, w), 4)}
    return out
