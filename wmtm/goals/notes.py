"""v0.7.0rc2 (Track V): closure evidence from the journal, for items whose later notes are not in the active set.

The goal engine sees only the WMTM active set, so a later journal note that settles an item ("the cleanup from Mar03
14:05 is done", "already closed X's 'just do Y' request", "RESOLVED: ...") was invisible unless it happened to be
recalled.  This module reads the bot's append-only journal (``goal_journal_path``; default
``<state_dir>/_journal/journal.metta``, read-only) and keeps, per note, only the closure digests of its sentences
(``needs.sentence_digest``: topic keys, a closure flag, referenced note stamps, "answers to HH:MM" times, moot
anchors, the speaker_map people named).  No raw text is stored.

Index: ``<runtime_dir>/goalchainer/notes_index.json`` (mode 600): {v, path, head (sha of the first head_n <= 4 KB parsed
bytes), map (speaker
map sha), off (bytes parsed), notes: [[id, ts, [digest, ...]], ...]}.  The journal is append-only, so each run parses
only the bytes added since ``off`` (complete lines only); a changed head, path or speaker map rebuilds it.  Notes
older than ``goal_history_max_days`` are dropped; notes without any closure evidence are not stored.
"""
from __future__ import annotations

import calendar
import hashlib
import json
import os
import re
import time

from . import needs

INDEX = "notes_index.json"
JOURNAL_FILE = "journal" + ".metta"
VERSION = 1
HEAD = 4096
MAX_NEW_BYTES = 64 * 1024 * 1024
_NOTE = re.compile(r'^\(EventNote ev-(ep-note-(\d{8}T\d{6})Z(?:-\d+)?) "((?:[^"\\]|\\.)*)"\)[ \t]*$', re.M)


def journal_path(cfg):
    p = str(cfg.get("goal_journal_path") or "")
    if p:
        return p
    sd = cfg.get("state_dir")
    if not sd:
        return ""
    d = os.environ.get("JOURNAL_DIR") or os.path.join(str(sd), "_journal")     # the Iter convention (wmtm/journal.py)
    return os.path.join(d, JOURNAL_FILE)


def _sha(b):
    return hashlib.sha256(b).hexdigest()[:16]


def _digests(content, people, aliases):
    out = []
    for s in needs.sentences(content):
        d = needs.sentence_digest(needs.canon_text(s, aliases), people)
        if d:
            out.append(d)
    return out


def parse_text(text, people=(), aliases=None):
    """Journal text -> ([[id, ts, [digest]]] for notes with closure evidence, end): end = the offset up to which the
    text was fully consumed (a note still being written at the end of the text is left for the next run)."""
    out, last = [], 0
    for m in _NOTE.finditer(text):
        last = m.end()
        try:
            ts = float(calendar.timegm(time.strptime(m.group(2), "%Y%m%dT%H%M%S")))
        except ValueError:
            continue
        ds = _digests(m.group(3).replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\"), people, aliases)
        if ds:
            out.append([m.group(1), ts, ds])
    m = re.compile(r"^\(EventNote ", re.M).search(text, last)
    if m and len(text) - m.start() < 1_000_000:     # a note still being written: parse it next time
        return out, m.start()
    return out, len(text)


def load(cfg, now=None, stats=None):
    """-> [(id, ts, [digest])] oldest first, within goal_history_max_days.  Never raises (stats["error"])."""
    stats = {} if stats is None else stats
    if not cfg.get("goal_journal_closure", True):
        stats["journal"] = "off"
        return []
    path = journal_path(cfg)
    if not path or not os.path.isfile(path):
        stats["journal"] = "absent"
        return []
    now = time.time() if now is None else now
    t0 = time.time()
    keep_s = float(cfg.get("goal_history_max_days", 45.0)) * 86400.0
    rt = os.path.join(cfg.get("runtime_dir") or ".", "goalchainer")
    ipath = os.path.join(rt, INDEX)
    people = needs.people_patterns(cfg.get("speaker_map"))
    aliases = needs.alias_map(cfg.get("speaker_map"), cfg.get("speaker_self"))
    msha = _sha(json.dumps([cfg.get("speaker_map") or {}, cfg.get("speaker_self") or ""], sort_keys=True).encode())
    ap = os.path.abspath(path)
    try:
        size = os.path.getsize(ap)
        with open(ap, "rb") as fh:
            first = fh.read(HEAD)
    except OSError as e:
        stats["error"] = "%s: journal unreadable" % type(e).__name__
        return []
    try:
        idx = json.load(open(ipath, encoding="utf-8"))
        hn = int(idx.get("head_n", 0))         # the head is hashed over what was parsed (a short journal grows)
        if (idx.get("v") != VERSION or idx.get("path") != ap or idx.get("head") != _sha(first[:hn])
                or idx.get("map") != msha or int(idx.get("off", 0)) > size or hn > len(first)):
            idx = None
    except (OSError, ValueError, AttributeError, TypeError):
        idx = None
    notes = list((idx or {}).get("notes") or ())
    off = int((idx or {}).get("off", 0))
    added = 0
    if size > off:
        try:
            with open(ap, "rb") as fh:
                fh.seek(off if size - off <= MAX_NEW_BYTES else size - MAX_NEW_BYTES)
                if size - off > MAX_NEW_BYTES:          # very large backlog: only the tail, from a line start
                    fh.readline()
                buf = fh.read()
            end = buf.rfind(b"\n") + 1                   # complete lines only; the rest is parsed next time
            txt = buf[:end].decode("utf-8", "replace")
            new, used = parse_text(txt, people, aliases)
            end = len(txt[:used].encode("utf-8", "replace")) if used < len(txt) else end
            off = (size - len(buf) if size - off > MAX_NEW_BYTES else off) + end
            seen = {n[0] for n in notes}
            for n in new:
                if n[0] not in seen:
                    notes.append(n); added += 1
        except OSError as e:
            stats["error"] = "%s: journal unreadable" % type(e).__name__
    before = len(notes)
    notes = [n for n in notes if now - float(n[1]) <= keep_s]
    if idx is None or added or len(notes) != before or off != int((idx or {}).get("off", 0)):
        try:
            os.makedirs(rt, exist_ok=True)
            tmp = "%s.%d.tmp" % (ipath, os.getpid())
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            os.fchmod(fd, 0o600)        # rc2: explicit; umask / a default ACL on the dir must not widen it (seen: 640)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                hn = min(HEAD, off)
                json.dump({"v": VERSION, "path": ap, "head": _sha(first[:hn]), "head_n": hn, "map": msha, "off": off,
                           "notes": notes}, fh)
            os.replace(tmp, ipath)
        except OSError:
            stats["index_write"] = "failed"
    notes.sort(key=lambda n: float(n[1]))
    stats.update(journal="ok", notes=len(notes), added=added, s=round(time.time() - t0, 3))
    return [(n[0], float(n[1]), n[2]) for n in notes]
