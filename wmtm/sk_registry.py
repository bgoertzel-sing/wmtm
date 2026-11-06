"""P3 (Man Hin answer 1): wmtm's own cross-note registry for unnamed entities.

Until upstream CONTEXT mode lands, notes are parsed one at a time.  Unnamed witnesses (sk_*) are prefixed per note
by semparse_adapter (``sk_request_1`` in note n1 becomes ``sk_request_1__i_n1``), so two notes never silently share
an unnamed entity.  Named entities link by their deterministic symbols and are NOT recorded here.

This registry records, for every scoped witness that reaches the parse cache:
  * the note that introduced it (``__i_<note>`` suffix -> owner), its content hash and first-seen time;
  * its kinds (``(Member sk_x__i_n kind)`` / ``(Inheritance sk_x__i_n kind)`` atoms);
  * the later notes whose validated atoms reuse it (Track O context reuse) -> the only cross-note links.
It never merges two witnesses: identity across notes is only ever asserted by reuse of the same scoped symbol.
Storage: ``<semparse_dir>/sk_registry.jsonl``, append-only rows; the resolved view folds them.  Pure stdlib.
"""
from __future__ import annotations
import json, os, re

SK = re.compile(r"\bsk_[A-Za-z0-9_\-]*__i_[A-Za-z0-9_]+")
KIND = re.compile(r"\((?:Member|Inheritance)\s+(sk_[A-Za-z0-9_\-]*__i_[A-Za-z0-9_]+)\s+([A-Za-z_][A-Za-z0-9_\-]*)\)")
FILE = "sk_registry.jsonl"


def owner(sym: str) -> str:
    """'sk_report_1__i_n5' -> 'i_n5' (the note scope that introduced the witness)."""
    return "i_" + sym.split("__i_", 1)[1]


def scan(atoms):
    """Scoped witnesses and their kinds in a list of atom strings: {sym: set(kinds)}."""
    out = {}
    for a in atoms or []:
        for s in SK.findall(a):
            out.setdefault(s, set())
        for s, k in KIND.findall(a):
            out.setdefault(s, set()).add(k)
    return out


class SkRegistry:
    def __init__(self, d):
        self.d = d
        self.path = os.path.join(d, FILE)

    def note(self, note_scope, h, atoms, ts=None):
        """Record the witnesses in one note's validated atoms.  note_scope: safe_id of the note (``i_...``).
        Caller holds the cache lock.  Returns the rows written."""
        rows = []
        for sym, kinds in sorted(scan(atoms).items()):
            own = owner(sym)
            rows.append({"sym": sym, "owner": own, "note": note_scope, "hash": h, "ts": ts,
                         "kinds": sorted(kinds), "role": "intro" if own == note_scope else "reuse"})
        if rows:
            os.makedirs(self.d, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.writelines(json.dumps(r) + "\n" for r in rows)
        return rows

    def _rows(self):
        out = []
        try:
            with open(self.path, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        r = json.loads(line)
                    except ValueError:              # torn line: skipped, never fatal
                        continue
                    if isinstance(r, dict) and isinstance(r.get("sym"), str):
                        out.append(r)
        except OSError:
            pass
        return out

    def entities(self):
        """Resolved view: {sym: {owner, hash, first_ts, kinds, notes (all notes using it, owner first), linked}}.
        ``linked`` is True when a note other than the owner reuses the witness (a cross-note link)."""
        ents = {}
        for r in self._rows():
            e = ents.setdefault(r["sym"], {"owner": r.get("owner") or owner(r["sym"]), "hash": None,
                                           "first_ts": r.get("ts"), "kinds": [], "notes": []})
            if r.get("role") == "intro" and e["hash"] is None:
                e["hash"] = r.get("hash")
            for k in r.get("kinds") or []:
                if k not in e["kinds"]:
                    e["kinds"].append(k)
            if r.get("note") and r["note"] not in e["notes"]:
                e["notes"].append(r["note"])
        for e in ents.values():
            e["notes"].sort(key=lambda n: n != e["owner"])
            e["linked"] = any(n != e["owner"] for n in e["notes"])
        return ents

    def for_note(self, note_scope):
        """Witnesses a note introduced or reused."""
        return {s: e for s, e in self.entities().items() if note_scope in e["notes"]}

    def links(self):
        """Cross-note links: [(sym, owner_note, other_note)]."""
        return [(s, e["owner"], n) for s, e in sorted(self.entities().items()) for n in e["notes"] if n != e["owner"]]
