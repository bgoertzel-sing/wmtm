"""Track S (GoalChainer phase b): an optional, read-only "Goal suggestions (not instructions)" block.

Reads only <runtime_dir>/goalchainer/latest.json (written atomically by engine.write_latest after every run).
Shown only when the goal_prompt flag is on, the run is fresh (<= goal_prompt_max_age_s), its status is ok and
its canary passed.  At most goal_prompt_max_lines (cap 3) lines.  Never raises; any problem -> no block."""
import json
import os
import re
import time

# Same values as wmtm.goals.engine.SUBDIR / LATEST (test-checked).  Deliberately NOT imported: the user path must
# never import the goal engine (only workers/pc_shadow.py does); this module only reads one JSON file.
SUBDIR = "goalchainer"
LATEST = "latest.json"
ASKED = "asked.jsonl"   # Track T: one line per rendered suggestion (shown_at); the engine's re-ask rule reads it

# Wording convention (rc2): the block is read by the bot about the person it is talking to now (the "speaker").
# Every line is worded TO that speaker, so the bot can relay it as is: "you"/"your" always mean the speaker, never
# the bot.  The speaker's canonical name and its speaker_map aliases are replaced by you/your (possessive 's ->
# your) and each line starts with a reader-directed lead-in ("Open question for you:", "Pending for you:", ...).
HEADER = "[Goal suggestions (not instructions): optional points the assistant may raise with the current speaker " \
         "if relevant; each line is worded to the speaker (\"you\" = the speaker, not the assistant); never a user " \
         "request, do not act on them unless the user asks]"
MAX_LINES = 3
TEXT_CHARS = 200
# Same as wmtm.goals.actions.MESSAGE_ACTIONS (test-checked).  SelfTask / LookUp are never shown.
MESSAGE_ACTIONS = ("ClarifyQuestion", "FlagUncertainty", "SummarizeStatus", "RemindPending")
# action -> (engine template prefix, lead-in when the addressee is the speaker, lead-in otherwise ({W} = name)).
_PHRASE = {
    "ClarifyQuestion": ("Ask {who}: ", "Open question for you: ", "Open question for {W}: "),
    "FlagUncertainty": ("In the next reply to {who}, say this is still open: ", "Still open for you: ", "Still open for {W}: "),
    "SummarizeStatus": ("Send {who} a short status of ", "Status for you: ", "Status for {W}: "),
    "RemindPending":   ("Remind {who} about: ", "Pending for you: ", "Pending for {W}: "),
}
# Item markers the engine keeps inside the text; redundant after the lead-in ("Pending for you: Still pending: ...").
_MARKER = re.compile(r"^\s*(?:still\s+pending|pending|still\s+open|open\s+questions?\s+for\s+you|blocked\s+on\s+you)"
                     r"\s*:\s*", re.I)
_VERB = {"is": "are", "was": "were", "has": "have", "does": "do"}


def _setting(cfg, key):
    from .context import setting
    return setting(cfg, key)


def load_latest(cfg):
    path = os.path.join((cfg or {}).get("runtime_dir") or ".", SUBDIR, LATEST)
    try:
        with open(path, encoding="utf-8") as fh:
            rec = json.load(fh)
    except Exception:   # noqa: BLE001
        return None
    return rec if isinstance(rec, dict) else None


def _who(p):
    return str(p.get("who") or "").strip().lower().lstrip("@")


def candidates(rec, speaker):
    """Proposals that may be shown to `speaker`: status proposed, non-empty text, a message-type action, and
    addressed to the current speaker.  Unknown speaker -> []."""
    sp = str(speaker or "").strip().lower().lstrip("@")
    if not sp or not isinstance(rec, dict):
        return []
    return [p for p in rec.get("proposals") or () if isinstance(p, dict) and p.get("status") == "proposed"
            and str(p.get("text") or "").strip() and p.get("action") in MESSAGE_ACTIONS and _who(p) == sp]


def names_for(who, speaker_map=None):
    """The canonical name plus every non-numeric speaker_map alias of it (lower case, no @)."""
    w = str(who or "").strip().lower().lstrip("@")
    out = {w} if w else set()
    if isinstance(speaker_map, dict):
        for k, v in speaker_map.items():
            k = str(k).strip().lower().lstrip("@")
            if isinstance(v, str) and v.strip().lower().lstrip("@") == w and k and not k.isdigit():
                out.add(k)
    return out


def to_you(text, names):
    """Whole-word, case-insensitive: <name>'s -> your, <name> -> you (with 'is/was/has/does' -> 'are/were/have/do')."""
    names = sorted((n for n in names if n), key=len, reverse=True)
    if not names:
        return text
    rx = re.compile(r"(?<![A-Za-z0-9_@])@?(?:%s)(?![A-Za-z0-9_])(?:(?P<poss>['\u2019]s(?![A-Za-z0-9_]))|"
                    r"(?P<verb>\s+(?:is|was|has|does)(?![A-Za-z0-9_])))?" % "|".join(map(re.escape, names)), re.I)

    def rep(m):
        if m.group("poss"):
            return "your"
        if m.group("verb"):
            v = m.group("verb")
            return "you" + v[:len(v) - len(v.lstrip())] + _VERB[v.strip().lower()]
        return "you"
    return rx.sub(rep, text)


def phrase(p, reader=None, speaker_map=None):
    """Engine text -> one suggestion line without the action name or command verb.  When the addressee is `reader`
    (the speaker the block is shown to): second person, see the wording convention above."""
    t = " ".join(str(p.get("text") or "").split())
    who = str(p.get("who") or "")
    tpl, you_lead, other_lead = _PHRASE.get(p.get("action"), ("", "For you: ", "For {W}: "))
    pre = tpl.format(who=who)
    if pre and t.lower().startswith(pre.lower()):
        t = t[len(pre):]
    elif tpl:
        lead = tpl.split("{who}")[0]
        if lead and t.lower().startswith(lead.lower()):     # template drifted: still never echo the command verb
            t = t[len(lead):]
    sp = str(reader or "").strip().lower().lstrip("@")
    if sp and sp == _who(p):
        t, lead = to_you(t, names_for(sp, speaker_map)), you_lead
    else:
        lead = other_lead.replace("{W}", who[:1].upper() + who[1:] if who else "them")
    for _ in range(3):
        t2 = _MARKER.sub("", t)
        if t2 == t:
            break
        t = t2
    return (lead + t)[:TEXT_CHARS]


def speaker_of(store, cfg, request):
    """Current speaker, resolved like rc4/Track Q: the source_type=user request item's source_meta + text via
    semparse_speaker.resolve with the flags-file speaker_map; falls back to the raw request text.  -> name|None."""
    try:
        from . import semparse_speaker as _sp
        text, src = request or "", None
        for it in (store.get_active_set() if store is not None else ()):
            if getattr(it, "source_type", None) == "user":
                text = getattr(it, "content", "") or text
                src = getattr(it, "source_meta", None)
                break
        name, _how = _sp.resolve(text, src, _setting(cfg, "speaker_map"))
        return name or None
    except Exception:   # noqa: BLE001
        return None


def eligible(rec, cfg, now=None, speaker=None, automated=False):
    """-> (ok, reason).  Reasons: off | automated | missing | status | canary | stale | future | no_speaker | empty."""
    if not _setting(cfg, "goal_prompt"):
        return False, "off"
    if automated:
        return False, "automated"
    if not rec:
        return False, "missing"
    if rec.get("status") != "ok":
        return False, "status"
    if rec.get("canary_ok") is not True:
        return False, "canary"
    now = time.time() if now is None else now
    try:
        age = now - float(rec.get("ts"))
    except (TypeError, ValueError):
        return False, "stale"
    if age < -60:
        return False, "future"
    if age > float(_setting(cfg, "goal_prompt_max_age_s")):
        return False, "stale"
    if not str(speaker or "").strip():
        return False, "no_speaker"
    if not candidates(rec, speaker):
        return False, "empty"
    return True, ""


def rotate_asked(path, max_bytes, keep_s, now):
    """rc3: size cap for asked.jsonl that keeps the re-ask window.  When the file is over max_bytes it moves to
    path.1 (replacing the previous .1) and the entries still inside keep_s (goal_reask_s) are written back to a fresh
    path, so suppression never loses a recent ask.  -> True if rotated.  Never raises."""
    try:
        if not max_bytes or max_bytes <= 0 or os.path.getsize(path) <= max_bytes:
            return False
        keep = []
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    e = json.loads(line)
                    if 0 <= now - float(e.get("ts")) < keep_s:
                        keep.append(line if line.endswith("\n") else line + "\n")
                except (ValueError, TypeError, AttributeError):
                    continue
        tmp = path + ".%d.tmp" % os.getpid()
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.writelines(keep)
        os.replace(path, path + ".1")
        os.replace(tmp, path)
        return True
    except Exception:   # noqa: BLE001
        return False


def record_shown(cfg, props, speaker, now=None):
    """Track T fix 2: a proposal counts as ASKED only once it was rendered into a prompt block.  Appends
    {ts, shown_at, id, who, topic, action} per shown line to <runtime_dir>/goalchainer/asked.jsonl (rc3: size-capped
    by jsonl_max_bytes, keeping the goal_reask_s window on rotation).  Never raises."""
    try:
        now = time.time() if now is None else now
        path = os.path.join((cfg or {}).get("runtime_dir") or ".", SUBDIR, ASKED)
        rotate_asked(path, int(_setting(cfg, "jsonl_max_bytes") or 0), float(_setting(cfg, "goal_reask_s")), now)
        with open(path, "a", encoding="utf-8") as fh:
            for p in props:
                fh.write(json.dumps({"ts": now, "shown_at": now, "id": p.get("id"), "who": _who(p) or speaker,
                                     "topic": list(p.get("topic") or ()), "action": p.get("action"),
                                     "display_only": bool(p.get("display_only"))}) + "\n")
    except Exception:   # noqa: BLE001
        pass


def render(cfg, now=None, rec=None, speaker=None, automated=False, record=False):
    """-> block text or None.  Needs a real user turn (automated=False) and a resolved speaker.
    record=True (the live user path only) logs the shown lines as asked (Track T)."""
    try:
        if automated or not _setting(cfg, "goal_prompt"):
            return None
        rec = load_latest(cfg) if rec is None else rec
        ok, _ = eligible(rec, cfg, now, speaker, automated)
        if not ok:
            return None
        n = max(0, min(MAX_LINES, int(_setting(cfg, "goal_prompt_max_lines"))))
        props = sorted(candidates(rec, speaker), key=lambda p: -float(p.get("score") or 0))[:n]
        if not props:
            return None
        out = HEADER + "\n" + "\n".join("  - " + phrase(p, speaker, _setting(cfg, "speaker_map")) for p in props)
        if record:
            record_shown(cfg, props, speaker, now)
        return out
    except Exception:   # noqa: BLE001
        return None
