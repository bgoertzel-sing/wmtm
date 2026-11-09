"""wmtm/frozen_parse.py - frozen parse caches for evaluations (t-2026-11-10-wmtm-normaliser, order Do 4).

Every evaluation (A/B, replay) reads parses ONLY from a frozen store keyed by
    (note content hash, parser pin, prompt sha256)
Nothing re-parses inside an evaluation: while ``evaluation()`` is active (or env WMTM_EVAL_FROZEN=1),
parse_cache.process_queue / process_queue_ctx / process_queue_spk refuse to run (FrozenParseError).
Re-parsing is its own step (``freeze``), run on purpose when a pin changes.

The store holds note-derived atoms, so it lives on pop-os outside the repository; only its sha256 sums
(``manifest()``) go in the repo.  Store layout: <dir>/frozen.jsonl, one JSON object per key.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os

ENV = "WMTM_EVAL_FROZEN"
_ACTIVE = [0]


class FrozenParseError(RuntimeError):
    pass


def content_hash(text: str) -> str:
    from .parse_cache import content_hash as _ch      # same note hash the live cache uses
    return _ch(text)


def key(note_hash: str, pin: str, prompt_sha: str) -> str:
    if not (note_hash and pin and prompt_sha):
        raise FrozenParseError("frozen key needs note hash, parser pin and prompt sha")
    return "%s|%s|%s" % (note_hash, pin[:12], prompt_sha[:16])


def in_evaluation() -> bool:
    return _ACTIVE[0] > 0 or os.environ.get(ENV, "") not in ("", "0")


@contextlib.contextmanager
def evaluation():
    """Mark an evaluation: any parse attempt inside raises FrozenParseError."""
    _ACTIVE[0] += 1
    try:
        yield
    finally:
        _ACTIVE[0] -= 1


def refuse_if_evaluating(where: str):
    if in_evaluation():
        raise FrozenParseError("re-parse refused inside an evaluation (%s); run the freeze step instead" % where)


class FrozenStore:
    def __init__(self, d):
        self.d = d
        self.path = os.path.join(d, "frozen.jsonl")

    def entries(self) -> dict:
        out = {}
        try:
            with open(self.path, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(e, dict) and "key" in e:
                        out[e["key"]] = e
        except OSError:
            pass
        return out

    def put(self, note_hash, pin, prompt_sha, item_id, status, atoms):
        """Freeze step only (never call inside an evaluation).  An existing key is never overwritten."""
        refuse_if_evaluating("FrozenStore.put")
        k = key(note_hash, pin, prompt_sha)
        if k in self.entries():
            return False
        os.makedirs(self.d, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"key": k, "note_hash": note_hash, "pin": pin[:12], "prompt_sha": prompt_sha[:16],
                                 "item_id": item_id, "status": status, "atoms": list(atoms or [])}) + "\n")
        return True

    def import_cache(self, cache_jsonl, pin, prompt_sha=None):
        """Freeze an existing parse cache (cache.jsonl rows: hash, item_id, status, atoms, prompt_sha)."""
        n = 0
        with open(cache_jsonl, encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                ps = prompt_sha or r.get("prompt_sha")
                if r.get("status") in ("ok", "empty") and ps:
                    n += bool(self.put(r["hash"], pin, ps, r.get("item_id"), r["status"], r.get("atoms")))
        return n

    def lookup(self, items, pin, prompt_sha, strict=True) -> dict:
        """Evaluation read: item.id -> atoms for (hash(item.content), pin, prompt_sha).  Read-only; a missing
        key raises (strict) instead of falling back to any parse."""
        ent = self.entries()
        out, missing = {}, []
        for it in items:
            e = ent.get(key(content_hash(it.content), pin, prompt_sha))
            if e is None or e.get("status") not in ("ok", "empty"):
                missing.append(it.id)
                continue
            out[it.id] = list(e.get("atoms") or [])
        if missing and strict:
            raise FrozenParseError("no frozen parse for %d notes at pin %s prompt %s: %s"
                                   % (len(missing), pin[:12], prompt_sha[:16], ",".join(map(str, missing[:5]))))
        return out

    def manifest(self) -> dict:
        """sha256 of the store file plus per-key atom sha256 (no note text)."""
        ent = self.entries()
        try:
            fsha = hashlib.sha256(open(self.path, "rb").read()).hexdigest()
        except OSError:
            fsha = None
        return {"file_sha256": fsha, "keys": {k: hashlib.sha256("\n".join(e.get("atoms") or []).encode()).hexdigest()
                                             for k, e in sorted(ent.items())}}
