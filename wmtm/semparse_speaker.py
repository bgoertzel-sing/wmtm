"""Track Q: speaker linking for the semantic parser.

Problem: in parsed notes the human who asked ("the user", "the requester", "he") and the bot itself ("I") become
fresh per-note sk_* witnesses, so facts about a person never accumulate across notes.  Names are rigid in the parser
(Grace -> grace in every note), so the fix is to *name* the speaker in the text sent to the parser.  The prompt file
is never edited; only the TEXT handed to the adapter changes.

Config (flags file ``<state_dir>/_wmtm_flags.json``, never in code):
  speaker_link   bool   (off by default)  route new parses to the speaker-linked cache version (spk1)
  speaker_map    object Telegram user id or username -> canonical lower-case name, e.g. {"<id>": "<name>",
                        "<username>": "<name>"}
  speaker_self   str    the bot's own canonical name ("I", "my", the bot name in any case -> this name)

Speaker resolution, most to least reliable (``speaker_source`` records which one was used):
  1. source:<key>   request metadata stored with the queued item (user_id / sender_id / sender_username);
  2. text:meta      Telegram metadata quoted in the text (``user_id=N``, ``sender_username="x"``), one person only;
  3. text:request   a request phrase naming one mapped person ("answered X", "X asked", "X's request" ...);
  otherwise the note is left unresolved (no guessing) and "the user" stays as it is.
Mapped usernames are also normalised to their canonical name everywhere in the text (handles -> the
name), so the same person gets the same symbol in every note.

Pure helpers, no I/O.
"""
import re

ID_RX = re.compile(r"\buser_id=(\d+)")
USERNAME_RX = re.compile(r'\bsender_username="?@?([A-Za-z0-9_]+)"?')
USER_PH = re.compile(r"\b[Tt]he (?:user|requester|requestor|human)('s)?(?![A-Za-z0-9_])")
NAME_OK = re.compile(r"^[a-z][a-z0-9_]*$")
REQ_BEFORE = r"(?:answered|asked|replied to|reply to|told|for|from|by|per)\s+"
REQ_AFTER = r"(?:\s+(?:asked|wants|wanted|said|requested|replied|answered|wrote)|'s\s+(?:\d{1,2}:\d{2}\s+)?(?:question|request|rule|reply|message|ask|task))"
SOURCE_ID_KEYS = ("user_id", "sender_id", "from_id")
SOURCE_NAME_KEYS = ("sender_username", "username")


def norm_map(m) -> dict:
    """{key(lower, no @): canonical name}; entries with a non-symbol name are dropped."""
    out = {}
    if isinstance(m, dict):
        for k, v in m.items():
            if not isinstance(v, str):
                continue
            v = v.strip().lower()
            if NAME_OK.match(v) and str(k).strip():
                out[str(k).strip().lower().lstrip("@")] = v
    return out


def display(name: str) -> str:
    return name[:1].upper() + name[1:] if name else name


def _word(a):
    return r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(a)


def _aliases(m) -> dict:
    """Non-numeric alias -> name, including each name itself."""
    al = {k: v for k, v in m.items() if not k.isdigit()}
    for v in m.values():
        al.setdefault(v, v)
    return al


def resolve(text: str, source=None, speaker_map=None):
    """-> (name or None, how)."""
    m = norm_map(speaker_map)
    if not m:
        return None, "no_map"
    src = source if isinstance(source, dict) else {}
    had_src = False
    for k in SOURCE_ID_KEYS:
        v = src.get(k)
        if v is not None and str(v).strip():
            had_src = True
            if str(v).strip() in m:
                return m[str(v).strip()], "source:" + k
    for k in SOURCE_NAME_KEYS:
        v = src.get(k)
        if v and str(v).strip():
            had_src = True
            if str(v).strip().lower().lstrip("@") in m:
                return m[str(v).strip().lower().lstrip("@")], "source:" + k
    if had_src:
        return None, "source_unmapped"            # a known sender we have no name for: never guess from the text
    text = text or ""
    hits = {m[i] for i in ID_RX.findall(text) if i in m}
    hits |= {m[u.lower()] for u in USERNAME_RX.findall(text) if u.lower() in m}
    if len(hits) == 1:
        return hits.pop(), "text:meta"
    if hits:
        return None, "ambiguous_meta"
    found = set()
    for a, name in _aliases(m).items():
        w = re.escape(a)
        if re.search(r"(?i)(?<![A-Za-z0-9_])" + REQ_BEFORE + w + r"(?![A-Za-z0-9_])", text) or \
                re.search(r"(?i)(?<![A-Za-z0-9_])" + w + REQ_AFTER, text):
            found.add(name)
    if len(found) == 1:
        return found.pop(), "text:request"
    return None, ("ambiguous_request" if found else "unresolved")


_FP = [(re.compile(r"\bI'm\b"), "{S} is"), (re.compile(r"\bI've\b"), "{S} has"), (re.compile(r"\bI'll\b"), "{S} will"),
       (re.compile(r"\bI'd\b"), "{S} would"), (re.compile(r"(?<![Tt]rack )(?<![Tt]rack-)(?<![Pp]hase )\bI\b(?!['\-0-9])"), "{S}"),
       (re.compile(r"\b[Mm]yself\b"), "{S}"), (re.compile(r"\b[Mm]y\b"), "{S}'s"), (re.compile(r"\bme\b"), "{S}")]


def first_person(text: str, name: str):
    """'I'/'me'/'my' -> the name (display form).  -> (text, n_substitutions)."""
    S, n = display(name), 0
    for rx, rep in _FP:
        text, k = rx.subn(rep.replace("{S}", S), text)
        n += k
    return text, n


def link(text: str, source=None, speaker_map=None, speaker_self="", prefix=True):
    """Rewrite one note for the parser.  -> (text, info).  info: speaker, speaker_source, subs.

    source may carry ``first_person``: "speaker" (the item is the human's own message: I/me/my = the speaker) or
    "self" (default: notes are written by the bot, I/me/my = speaker_self)."""
    m = norm_map(speaker_map)
    me = (speaker_self or "").strip().lower()
    me = me if NAME_OK.match(me) else ""
    src = source if isinstance(source, dict) else {}
    speaker, how = resolve(text, src, m)
    out, subs = text or "", 0
    for a, name in sorted(_aliases(m).items(), key=lambda kv: -len(kv[0])):   # handles -> canonical name
        out, k = re.subn("(?i)" + _word(a), display(name), out)
        subs += k if a != name else 0
    if me:
        out, k = re.subn("(?i)" + _word(me), display(me), out)
    if speaker:
        out, k = USER_PH.subn(lambda mm: display(speaker) + ("'s" if mm.group(1) else ""), out)
        subs += k
    fp = src.get("first_person") or "self"
    who = speaker if fp == "speaker" else me if fp == "self" else ""
    if who:
        out, k = first_person(out, who)
        subs += k
    if speaker and prefix:
        out = "Speaker: %s. %s" % (display(speaker), out)
    return out, {"speaker": speaker, "speaker_source": how, "subs": subs}


def linker(cfg):
    """cfg -> callable(content, source) -> (text, info), bound to the flags-file map."""
    m, me = norm_map(cfg.get("speaker_map")), cfg.get("speaker_self") or ""

    def f(content, source=None):
        return link(content, source, m, me)
    return f
