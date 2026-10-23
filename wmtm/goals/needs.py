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
_OPTION_BEFORE = re.compile(r"\b(?:or|should|whether|would|could|to|if|can)\s+(?:\w+\s+)?$", re.I)


def moot_hits(t):
    """Moot words that report a state ("the X bracket is gone"), not an option ("provide or drop X", "whether to
    remove X"): rc2."""
    for m in _MOOT.finditer(t or ""):
        if not _OPTION_BEFORE.search(t[max(0, m.start() - 24):m.start()]):
            yield m
_PRONOUN_OWNER = {"the user", "user", "their", "them", "they", "you", "your"}
_SELF_WORDS = {"me", "i", "myself"}
MAX_SENT = 400


_ENTITY = re.compile(r"\b([A-Za-z]*[a-z][A-Z][A-Za-z]*|[A-Z]{3,}[a-z]?|[a-z_]+(?=\.(?:py|metta|md|json)\b))\b")
_PATH_STOP = {"and/or", "either/or", "yes/no", "on/off", "true/false", "read/write"}
_PATH = re.compile(r"(?<![\w/.-])((?:[A-Za-z_][\w-]*/)+[A-Za-z_][\w-]*)(?:\.[A-Za-z]{1,6})?(?![\w/-])")
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
    for m in _PATH.finditer(raw):                  # v0.7.0rc2: "src/widget.metta" / "src/widget" -> @src/widget
        w = m.group(1).lower()
        if len(w) >= 5 and w not in _PATH_STOP:
            ks.add("@" + w)
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
    # rc2: an anchor and its own plain spelling ("@wmtm" / "wmtm") count once
    return bool(anch) and len(sh | {x[1:] for x in anch if x.startswith("@")}) >= 2 and len(sh) >= 1


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


_LABEL = re.compile(r"^\s*(?:LINK|SUPPORTS|CONTRADICTS|CONTRAST|CORRECTION|LESSON|NOTE)\b", re.I)
# v0.7.0rc2 (Track V): an item must name its object.  A body that opens with a negation / pronoun / conjunction is a
# fragment of a longer thought ("still open: no later note says I joined.") and is dropped, never cut into shape.
_BODY_FRAGMENT = re.compile(r"^\W*(?:no|nothing|none|not|it|this|these|those|they|he|she|and|or|but|so|also|then|"
                            r"yet)\b", re.I)
# A second clause with its own subject ("..., and Quill hasn't answered on X yet") is a separate item.
_AND_SUBJ = re.compile(r",\s+and\s+(?=(?:I|[A-Z][\w-]*)(?:'s)?\s+(?:\w+\s+){0,2}?(?:has|hasn't|have|haven't|is|isn't|"
                       r"was|wasn't|still|needs?|owes?|did|didn't|does|doesn't|will|won't|must|should)\b)")


def split_items(after):
    """v0.7.0rc2: one item per line.  A list "a; b; c" (>= 3 parts: a single ";" usually continues the same
    thought) and "a, and <Subject> has/hasn't ..." -> separate parts."""
    out = []
    parts = re.split(r";\s+", after or "")
    for p in (parts if len(parts) >= 3 else [after or ""]):
        out.extend(x.strip(" ,") for x in _AND_SUBJ.split(p))
    return [x for x in out if x]


def _one(kind, tok, text, after, owner_body, people, self_name, requester):
    if len(text) > MAX_SENT:
        return None, "too_long"
    if _BODY_FRAGMENT.match(after or ""):
        return None, "fragment"
    body = after if kind == "question" else text
    if len(body.strip()) < 12:
        return None, "fragment"
    who = resolve_owner(tok, owner_body, people, self_name, requester)
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


def candidates_of(sentence, people=(), self_name="", requester=None):
    """One sentence -> [(dict(kind, who, text, body) | None, drop_reason)].  v0.7.0rc2: a bundled item list after
    the marker becomes one candidate per item, each worded as "<marker> <item>." (whole sentence, never a fragment)."""
    mk = marker(sentence)
    if not mk:
        return [(None, "no_marker")]
    kind, tok, m = mk
    r = res_hit(sentence)
    if 0 <= r < m.start():
        return [(None, "resolution_report")]
    start = 0
    if _LABEL.match(sentence) or _FRAGMENT.match(sentence):   # "LINK: ... Still open: X" -> from the marker's clause
        start = m.start()
        if len(sentence) - start < 12:
            return [(None, "fragment")]
    head, after = sentence[start:m.end()], sentence[m.end():].strip()
    parts = split_items(after) if kind != "self" else [after]
    if len(parts) <= 1:
        return [_one(kind, tok, sentence[start:], after, sentence[m.start():], people, self_name, requester)]
    out = []
    for p in parts:
        t = head.rstrip() + " " + p
        if not t.rstrip().endswith((".", "?", "!")):
            t = t.rstrip() + "."
        out.append(_one(kind, tok, t, p, sentence[m.start():m.end()] + " " + p, people, self_name, requester))
    return out


def candidate(sentence, people=(), self_name="", requester=None):
    """One sentence -> dict(kind, who, text, body) or (None, drop_reason) (the first item; see candidates_of)."""
    c, why = candidates_of(sentence, people, self_name, requester)[0]
    return (c, why) if c else (None, why)


def request_digest(text):
    """What the reply checks need from a request text (no raw text kept): topic keys, the reply flag,
    "answers to HH:MM" times and the anchors near moot words."""
    t = str(text or "")
    moot = set()
    for m in moot_hits(t):
        moot |= strong(keys(t[max(0, m.start() - 40):m.end() + 40]))
    return {"keys": sorted(keys(t)), "reply": t.lstrip().startswith("[reply to"),
            "ans": [m.group(1) for m in _ANS_TIME.finditer(t)], "moot": sorted(moot),
            "dec": bool(_DECISION.search(t))}


# rc2: a reply that states a decision ("ok, merge it", "just upgrade X", "go ahead")
_DECISION = re.compile(r"\b(?:yes|yep|yeah|ok|okay|approved?|go ahead|sure|agreed|fine|do it|let'?s do|just "
                       r"(?:upgrade|merge|deploy|do|use|drop|keep|go)|no|nope|don'?t)\b", re.I)
REPLY_GRACE_S = 24 * 3600.0
DECISION_MAX_KEYS = 12      # a decision reply is terse; a long message sharing one word is not an answer


def _req_view(r):
    """A request as {keys(set), reply, ans, moot(set)}: from a stored digest, or computed from its text."""
    if "keys" in r:
        return {"keys": set(r.get("keys") or ()), "reply": bool(r.get("reply")), "ans": list(r.get("ans") or ()),
                "moot": set(r.get("moot") or ()), "dec": bool(r.get("dec"))}
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


_STAMP = re.compile(r"^\s*([A-Z][a-z]{2}\d{1,2} \d{1,2}:\d{2})\b")


def stamp(content):
    """v0.7: the note's own leading time stamp ("Mar03 14:05 ..."), else None."""
    m = _STAMP.match(content or "")
    return m.group(1) if m else None


# ------------------------------------------------------------------ v0.7.0rc2 (Track V): topic clusters
TOPIC_OVERLAP = 0.4        # default of the goal_topic_overlap flag
_SUFFIXES = ("ings", "ing", "ers", "er", "ed", "es", "s", "e")


def stem(w):
    """Light suffix stripping so paraphrases share keys (merge / merging / merged -> merg)."""
    for suf in _SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[:-len(suf)]
    return w


def norm(ks):
    """keys -> normalized terms: stemmed plain keys plus anchors ("@x"; a path anchor also adds its last part)."""
    out = set()
    for k in ks or ():
        if k.startswith("@"):
            out.add(k)
            if "/" in k:
                out.add("@" + k.rsplit("/", 1)[1])
        else:
            out.add(stem(k))
    return out


def _anchors(n):
    return {k[1:] for k in n if k.startswith("@")} | {k for k in n if k.startswith("track_")}


def _anchor_share(na, nb):
    """Anchors of one side that appear (as anchor or plain word) on the other side."""
    pa, pb = {k for k in na if not k.startswith("@")}, {k for k in nb if not k.startswith("@")}
    aa, ab = _anchors(na), _anchors(nb)
    return (aa & (ab | pb | {stem(x) for x in ab})) | (ab & (pa | {stem(x) for x in aa}))


def cluster_match(a, b, thr=None):
    """Same (person-independent) topic cluster, robust to paraphrase: the R2 topic_match, or normalized term overlap
    |A & B| / min(|A|, |B|) >= thr (goal_topic_overlap, default 0.4) with >= 2 shared terms, or a shared anchor
    (CamelCase / CAPS / file or path name / track letter) plus one more shared term."""
    if not a or not b:
        return False
    if topic_match(a, b):
        return True
    thr = TOPIC_OVERLAP if thr is None else float(thr)
    na, nb = norm(a), norm(b)
    pa, pb = {k for k in na if not k.startswith("@")}, {k for k in nb if not k.startswith("@")}
    sh = pa & pb
    if pa and pb and len(sh) >= 2 and len(sh) >= thr * min(len(pa), len(pb)):
        return True
    anch = _anchor_share(na, nb)
    return bool(anch) and len(sh | anch) >= 2       # an anchor and its plain spelling count once


def alias_map(speaker_map, self_name=""):
    """speaker_map -> {alias (lower case, non-numeric, != canonical): canonical name}."""
    out = {}
    for k, v in (speaker_map or {}).items():
        k, v = str(k).strip().lower().lstrip("@"), str(v or "").strip().lower()
        if k and v and not k.isdigit() and k != v:
            out[k] = v
    return out


def canon_text(text, aliases):
    """v0.7.0rc2: every speaker_map alias in the text -> the canonical name (whole word, keeps a leading @-less form),
    so the same person is never two people in one line ("Remind quill ... waiting on <quill's username>")."""
    if not aliases or not text:
        return text
    rx = re.compile(r"(?<![A-Za-z0-9_])@?(%s)(?![A-Za-z0-9_])" % "|".join(map(re.escape, sorted(aliases, key=len,
                                                                                                 reverse=True))), re.I)
    return rx.sub(lambda m: aliases[m.group(1).lower()], text)


# ------------------------------------------------------------------ closure evidence as digests (no raw text)
_STAMP_ANY = re.compile(r"\b([A-Z][a-z]{2}\d{1,2} \d{1,2}:\d{2})\b")


def sentence_digest(s, people=()):
    """What the closure checks need from one later sentence, without its text: topic keys, whether it reports a
    closure (a non-negated resolution word not preceded by an open marker), the note stamps it references, the
    "answers to HH:MM" times, the anchors near moot words and the people it names.  -> dict or None (no evidence)."""
    p = res_hit(s)
    mk = marker(s)
    r = p >= 0 and not (mk and mk[2].start() <= p)
    ans = [m.group(1) for m in _ANS_TIME.finditer(s or "")]
    moot = set()
    for m in moot_hits(s or ""):
        moot |= strong(keys(s[max(0, m.start() - 40):m.end() + 40]))
    if not (r or ans or moot):
        return None
    return {"k": sorted(keys(s)), "r": bool(r), "st": _STAMP_ANY.findall(s) if r else [], "ans": ans,
            "moot": sorted(moot), "who": sorted({n for n, pat in people if pat.search(s or "")})}


COMMON_DF = 0.03            # an anchor in more than 3% (and > 3) of the later closure sentences is too common to


def common_terms(later):
    """rc2: anchors too frequent among the closure sentences to identify a topic on their own (a project name)."""
    df, n = {}, 0
    for _ts, ds in later:
        for d in ds:
            if d:
                n += 1
                for k in set(d.get("k") or ()):
                    df[k] = df.get(k, 0) + 1
    lim = max(3, COMMON_DF * n)
    return {k.lstrip("@") for k, c in df.items() if c > lim}


def _note_closes(sig, d, thr, common=frozenset()):
    for st in d.get("st") or ():                  # v0.7: "the cleanup from Mar03 14:05 is done" closes that note's items
        if st in (sig.get("stamps") or ()):
            return "closed_by_stamp_reference"
    for t in d.get("ans") or ():
        if re.search(r"\b" + re.escape(t) + r"\b", sig["text"]):
            return "closed_answers_to_time"
    if set(d.get("moot") or ()) & strong(sig["ckeys"]):
        return "closed_moot"
    if not d.get("r"):
        return None
    dk = set(d.get("k") or ())
    if cluster_match(sig["ckeys"], dk, thr):
        return "closed_by_note"
    # rc2: a later note reports the addressee's decision / request closed, on one of the item's anchors
    # ("... had already closed Quill's 'just upgrade X' request" closes "Quill's choice on X ...").
    if sig.get("who") and sig["who"] != SELF and sig["who"] in (d.get("who") or ()):
        na, nd = norm(sig["ckeys"]), norm(dk)
        anch = _anchor_share(na, nd)
        other = {k for k in na & nd if not k.startswith("@")} - anch
        if (anch - set(common)) or (anch and other):
            return "closed_by_owner_decision"
    return None


_FLAG_ON = r"(?:turn(?:ing|ed)?|switch(?:ing|ed)?|flip(?:ping|ped)?|set(?:ting)?|put(?:ting)?)\s+(?:\S+\s+){0,2}?%s\s+on|" \
           r"(?:enabl\w*|activat\w*)\s+(?:\S+\s+){0,2}?%s|%s\s*(?:=|:|to)\s*(?:on|true|1)\b|%s\s+on\b"
_FLAG_OFF = r"(?:turn(?:ing|ed)?|switch(?:ing|ed)?|flip(?:ping|ped)?|set(?:ting)?|put(?:ting)?)\s+(?:\S+\s+){0,2}?%s\s+off|" \
            r"(?:disabl\w*|deactivat\w*)\s+(?:\S+\s+){0,2}?%s|%s\s*(?:=|:|to)\s*(?:off|false|0)\b|%s\s+off\b"


def flag_contradiction(text, flags):
    """v0.7.0rc2: an open item about switching a known boolean flag (`speaker_link`, `goal_prompt`, ...) on (off)
    while the live flags already have it on (off) is contradicted by live state -> the flag name, else None.
    Limits: boolean flags of the flags file only; deploy / version / branch claims are not checked."""
    t = text or ""
    for name, val in (flags or {}).items():
        if not isinstance(val, bool) or name not in t:
            continue
        q = re.escape(name)
        if re.search(r"%s\s+(?:on\s+or\s+off|off\s+or\s+on)\b" % q, t, re.I):
            continue                               # "X on or off?": no claim either way
        on = re.search(_FLAG_ON % (q, q, q, q), t, re.I)
        off = re.search(_FLAG_OFF % (q, q, q, q), t, re.I)
        if on and not off and val:
            return name
        if off and not on and not val:
            return name
    return None


def _closed(sig, later, requests, now, thr=None, unattributed=True, common=frozenset()):
    """-> reason string if later evidence closes sig (status at `now`), else None.  later = [(ts, [sentence
    digest])] from the active set and (rc2) the journal index; requests = request digests (rc2: unattributed group
    requests too, who=None)."""
    for ts, ds in later:
        if ts <= sig["ts_last"] or ts > now:
            continue
        for d in ds:
            why = _note_closes(sig, d, thr, common) if d else None
            if why:
                return why + ("_note" if not why.endswith("_note") else "")
    after = [(r, _req_view(r)) for r in requests or () if sig["ts_last"] < float(r["ts"]) <= now]
    for r, v in after:
        if r.get("who"):
            why = _req_moot_or_answered(sig, v)
            if why:
                return why + "_reply"
    if sig["who"] and sig["who"] != SELF:
        ns = norm(sig["ckeys"])
        # rc2: a DECISION reply from shortly before the newest restatement also counts (the bot's own note can
        # restate an item it had not yet seen answered: "ok, merge it" at 10:00, "still needs X's OK" at 16:00)
        for r in requests or ():
            rt = float(r["ts"])
            if sig["ts_last"] - REPLY_GRACE_S < rt <= sig["ts_last"] and rt >= sig["ts"] - REPLY_GRACE_S \
                    and r.get("who") in (sig["who"], None) and (r.get("who") or unattributed):
                v = _req_view(r)
                sh = {k for k in ns & norm(v["keys"]) if not k.startswith("@")}
                if v["reply"] and v["dec"] and len(v["keys"]) <= DECISION_MAX_KEYS and \
                        (sh or _anchor_share(ns, norm(v["keys"]))):
                    return "closed_by_decision_reply"
        for r, v in after:
            nv = norm(v["keys"])
            sh = {k for k in ns & nv if not k.startswith("@")}
            if r.get("who") == sig["who"]:
                if len(sh) >= 2 or (len(sh) >= 1 and v["reply"]):
                    return "closed_by_reply"
            elif r.get("who") is None and unattributed and v["reply"]:
                # rc2: a group reply to the bot whose sender the transport did not record (older envelopes) closes
                # the item when it is clearly on the topic (or states a decision on it).  Biased to silence: never
                # used to address anyone.
                if len(sh) >= 2 or _anchor_share(ns, nv) or (sh and v["dec"] and len(v["keys"]) <= DECISION_MAX_KEYS):
                    return "closed_by_unattributed_reply"
    return None


def extract(raw_items, now=None, people=(), requests=(), self_name="", trace=None, st=None):
    """-> open signals {kind, need, text, body, keys, ckeys, ts (oldest), ts_last, sal, items, who, origin,
    last_contact}.  trace (optional list) receives (item_id, sentence, reason) for every dropped marker sentence /
    closed signal.  st (rc2, optional): topic_overlap, aliases, notes (journal digests), flags, close_unattributed."""
    now = time.time() if now is None else now
    st = st or {}
    thr = st.get("topic_overlap", TOPIC_OVERLAP)
    aliases = st.get("aliases") or {}
    names = set(aliases) | set(aliases.values()) | {str(self_name or "").lower()} | set(st.get("names") or ())
    names |= {"@" + n for n in list(names)}
    reqs = [r for r in requests or () if float(r.get("ts", 0)) <= now]
    items = [r for r in raw_items or [] if r.get("source_type", "recalled") == "recalled" and r.get("content")]
    items.sort(key=lambda r: item_ts(r, now))
    smax = max([float(r.get("sti") or 0.0) for r in items] + [1e-9])
    per, sigs = [], []
    for r in items:
        ts = item_ts(r, now); sal = max(0.0, min(1.0, float(r.get("sti") or 0.0) / smax))
        ss = [canon_text(x, aliases) for x in sentences(r["content"])]
        per.append((ts, [sentence_digest(x, people) for x in ss]))
        req = requester_at(reqs, ts)
        cands = []
        for s in ss:
            for c, why in candidates_of(s, people, self_name, req):
                if c:
                    cands.append((c, "text"))
                elif trace is not None and why != "no_marker":
                    trace.append((r.get("id"), s, why))
        for q in r.get("queries") or ():
            cands.append(({"kind": "question", "who": None, "text": str(q), "body": str(q)}, "parser"))
        for c, origin in cands:
            # rc2: people's names are not topic terms (every item of one person would share them)
            k = keys(c["body"] if c["kind"] == "question" else c["text"]) - names
            if len(k) < 2:
                continue
            need = "unc" if c["kind"] == "question" else "comp"
            cur = next((g for g in sigs if g["need"] == need and g["origin"] == origin
                        and cluster_match(g["ckeys"], k, thr)), None)
            if cur is None:
                sigs.append({"kind": c["kind"], "need": need, "text": c["text"], "body": c["body"], "keys": k,
                             "ckeys": set(k), "ts": ts, "ts_last": ts, "sal": sal, "items": [r.get("id")],
                             "who": c["who"], "origin": origin, "req": req,
                             "stamps": [x for x in (stamp(r["content"]),) if x]})
            else:                                  # newest note on the topic supersedes the older wording
                if trace is not None:
                    trace.append((r.get("id"), cur["text"], "superseded"))
                cur.update(kind=c["kind"], text=c["text"], body=c["body"], keys=k, ts_last=max(cur["ts_last"], ts),
                           who=c["who"] or cur["who"], req=req or cur.get("req"))
                cur["ckeys"] |= k                  # rc2: closure / dedupe match the whole cluster's terms
                cur["ts"] = min(cur["ts"], ts); cur["sal"] = max(cur["sal"], sal)
                if stamp(r["content"]) and stamp(r["content"]) not in cur.setdefault("stamps", []):
                    cur["stamps"].append(stamp(r["content"]))
                if r.get("id") not in cur["items"]:
                    cur["items"].append(r.get("id"))
    seen = {r.get("id") for r in items}
    later = per + [(float(t), ds) for i, t, ds in st.get("notes") or () if i not in seen and float(t) <= now]
    flags = st.get("flags") or {}
    common = common_terms(later)
    out = []
    for g in sigs:
        why = _closed(g, later, reqs, now, thr, st.get("close_unattributed", True), common)
        if not why and flags:
            f = flag_contradiction(g["text"], flags)
            why = "closed_flag_already_set_%s" % f if f else None
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
                   trace, st) + list(extra_signals)
    out = {}
    for n in ("unc", "comp"):
        ss = [s for s in sigs if s["need"] == n]
        lv = level(ss, now, st.get("scale", 1.0), st.get("age_cap_d", 7.0))
        t = st.get("targets", {}).get(n, 0.8); w = st.get("weights", {}).get(n, 1.0)
        out[n] = {"signals": ss, "level": round(lv, 4), "target": t, "weight": w, "urge": round(urge(lv, t, w), 4)}
    return out
