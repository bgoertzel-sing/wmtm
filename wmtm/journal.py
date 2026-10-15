"""Default long-term journal implementation (PeTTa/MeTTa append-only file).

Moved from the Iter tree's ``_petta_journal.py`` (snapshot 83ea611). The
on-disk format and append semantics are unchanged; the only difference is
that the journal location is injected (``PettaJournal(journal_dir)``)
instead of being derived from the module's own file location.

Design:
- History append-only: the journal file is only ever appended to; the
  supersession-resolved view is computed in-memory per read. No rewrite ever.
- All functions are read/read or read/append and never raise.
- Supersedes resolution filters stale facts from every rendered view.

Any object with ``read_lines() -> list[str]`` and
``append(note, supersedes=None, about=None) -> dict`` can be used as a
WMTM journal (see ``wmtm.api.WMTMConfig.journal``).
"""
import os, re, threading, datetime
from pathlib import Path

_LOCK = threading.Lock()

_RE_SUPERSEDES = re.compile(r"\(Supersedes\s+(\S+)\s+(\S+)\)")
_RE_MEMORY_CLUSTER = re.compile(r"\(MemoryCluster\s+([^\s)]+)")


def default_journal_dir(state_dir) -> Path:
    """Iter convention: ``$JOURNAL_DIR`` if set, else ``<state_dir>/_journal``."""
    env = os.environ.get("JOURNAL_DIR")
    return Path(env) if env else Path(state_dir) / "_journal"


def _collect_superseded_ids(lines):
    superseded = set()
    for line in lines:
        if "(Supersedes" not in line:
            continue
        for m in _RE_SUPERSEDES.finditer(line):
            new_id, old_id = m.group(1), m.group(2)
            if new_id != "new-id" and old_id != "old-id":
                superseded.add(old_id)
    return superseded


def _filter_superseded(lines, superseded):
    out = []
    dropping = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(";;; BEGIN MemoryCluster"):
            dropping = stripped.rsplit(" ", 1)[-1] in superseded
            if not dropping:
                out.append(line)
        elif stripped.startswith(";;; END MemoryCluster"):
            if not dropping:
                out.append(line)
            dropping = False
        elif not dropping:
            out.append(line)
    return out


def resolve_supersedes(lines):
    """Given journal lines, return lines with superseded clusters removed."""
    try:
        return _filter_superseded(lines, _collect_superseded_ids(lines))
    except Exception:
        return lines


class PettaJournal:
    """Append-only PeTTa/MeTTa journal at ``<journal_dir>/journal.metta``."""

    def __init__(self, journal_dir):
        self.journal_dir = Path(journal_dir)

    @property
    def path(self) -> Path:
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        return self.journal_dir / "journal.metta"

    def read_lines(self):
        """Read all journal lines, returning [] on any error."""
        try:
            p = self.path
            if not p.exists():
                return []
            return p.read_text(encoding="utf-8").splitlines()
        except Exception:
            return []

    def resolved_lines(self):
        return resolve_supersedes(self.read_lines())

    def _unique_cluster_id(self, prefix="ep-note-"):
        """Cluster id unique within this journal (F31: second-resolution ids collided)."""
        base = prefix + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        try:
            existing = set(_RE_MEMORY_CLUSTER.findall(self.path.read_text(encoding="utf-8", errors="replace")))
        except Exception:
            existing = set()
        cid = base
        n = 1
        while cid in existing:
            n += 1
            cid = f"{base}-{n}"
        return cid

    def append(self, note, supersedes=None, about=None):
        """Append a note as a structured Episode cluster (append-only write)."""
        try:
            note = str(note)
            safe = note.replace("\\", "\\\\").replace('"', '\\"')
            ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if isinstance(supersedes, str):
                supersedes = [supersedes]
            supersedes = [s for s in (supersedes or []) if s and re.fullmatch(r"[A-Za-z0-9._:-]+", s)]
            abouts = [a for a in (about or []) if a and re.fullmatch(r"[A-Za-z0-9._:-]+", a)] or ["journal"]
            with _LOCK:
                cid = self._unique_cluster_id()
            ev = "ev-" + cid
            sup_lines = "".join(f"(Supersedes {cid} {old})\n" for old in supersedes if old != cid)
            about_lines = "".join(f"(About {cid} {a})\n" for a in abouts)
            blk = (
                f";;; BEGIN MemoryCluster {cid}\n"
                f"(MemoryCluster {cid})\n"
                f"(SchemaVersion {cid} medium-memory-v1)\n"
                f"(ClusterType {cid} Episode)\n"
                f"(ClusterSource {cid} iter-experience)\n"
                f"(ClusterOpenedAt {cid} {ts})\n"
                f"(Contains {cid} {ev})\n"
                f"(ObservedEvent {ev})\n"
                + about_lines +
                f'(EventNote {ev} "{safe}")\n'
                + sup_lines +
                f";;; END MemoryCluster {cid}\n"
            )
            with _LOCK:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(blk)
            return {"ok": True, "id": cid, "supersedes": supersedes}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # Compatibility names used by the Iter tools.
    append_note = append
    _read_lines = read_lines
