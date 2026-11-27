"""ForgettingLog: records evicted items to prevent re-derivation.

When an item is evicted from WMTM, its signature is recorded so that
the inference engine and recall bridge can skip re-admitting it
(unless it receives significant new attention).
"""
from __future__ import annotations

import base64
import collections
import hashlib
import zlib
from dataclasses import dataclass, field

from .item import WMTMItem


@dataclass
class ForgetRecord:
    """Record of a forgotten/evicted item."""
    item_id: str
    content_hash: str
    source_type: str
    evicted_at_tick: int
    age_at_eviction: int
    final_utility: float
    final_sti: float
    derived_from: list[str] = field(default_factory=list)
    deriv_hash: str = ""
    final_confidence: float | None = None   # M-07: stv confidence at eviction (None = unknown / not a reasoner item)


def content_hash(content: str) -> str:
    """Compute a short hash of content for dedup."""
    return hashlib.md5(content.lower().strip().encode()).hexdigest()[:12]


def deriv_hash(content: str, derived_from=None, chash: str = None) -> str:
    """F1 §4: key of a derivation = the conclusion plus its sorted source ids.  The same conclusion reached from
    other sources is a new derivation and gets a different key.  chash: precomputed content_hash (old records)."""
    ch = chash if chash is not None else content_hash(content)
    srcs = ",".join(sorted(str(x) for x in (derived_from or [])))
    return hashlib.md5((ch + "|" + srcs).encode()).hexdigest()[:12]


# M-07: forgotten status must outlive the record window.  A key pruned from the window goes into a fixed-size
# Bloom filter: memory is bounded (bits/8 bytes, whatever the run length) and there are no false negatives, so a
# pruned derivation is still "forgotten" and must pass the STI test.  A false positive only sends a
# never-forgotten derivation through the same STI test; its rate is reported by pruned_fp_rate().
# Sizing: 2 keys per pruned derivation; at 2^18 bits, k=7 the false-positive rate stays below 1% up to ~13.7k
# pruned derivations (~27k keys).  Live (Nov 26): 83 of the 500 window records are derivations, the window spans
# ~381 cycles, i.e. ~0.22 pruned derivations per cycle -> ~60k cycles before 1%.  pruned_fp_rate() reports it.
PRUNED_BITS_DEFAULT = 1 << 18      # 32 KiB in memory; zlib-compressed in the saved state
PRUNED_K = 7


class _PrunedKeys:
    """Fixed-size Bloom filter of keys pruned from the window (no removal, no false negatives)."""

    def __init__(self, bits: int = PRUNED_BITS_DEFAULT, k: int = PRUNED_K, buf: bytes | None = None, n: int = 0):
        self.bits = max(64, int(bits) // 8 * 8)
        self.k = max(1, min(8, int(k)))
        self.buf = bytearray(buf) if buf is not None and len(buf) == self.bits // 8 else bytearray(self.bits // 8)
        self.n = int(n)

    def _idx(self, key: str):
        h = hashlib.sha256(key.encode()).digest()
        return [int.from_bytes(h[4 * i:4 * i + 4], "big") % self.bits for i in range(self.k)]

    def add(self, key: str) -> None:
        new = False
        for j in self._idx(key):
            b = 1 << (j & 7)
            if not self.buf[j >> 3] & b:
                self.buf[j >> 3] |= b
                new = True
        if new:
            self.n += 1

    def __contains__(self, key: str) -> bool:
        return all(self.buf[j >> 3] & (1 << (j & 7)) for j in self._idx(key))

    def fp_rate(self) -> float:
        ones = sum(bin(x).count("1") for x in self.buf)
        return (ones / self.bits) ** self.k

    def serialize(self) -> dict:
        return {"bits": self.bits, "k": self.k, "n": self.n,
                "zb64": base64.b64encode(zlib.compress(bytes(self.buf), 9)).decode()}

    @classmethod
    def deserialize(cls, d: dict) -> "_PrunedKeys":
        buf = zlib.decompress(base64.b64decode(d["zb64"])) if d.get("zb64") else None
        return cls(d.get("bits", PRUNED_BITS_DEFAULT), d.get("k", PRUNED_K), buf, d.get("n", 0))


def _confidence_of(item) -> float | None:
    prov = getattr(item, "provenance", None)
    stv = prov.get("stv") if isinstance(prov, dict) else None
    try:
        return float(stv[1]) if stv is not None and len(stv) > 1 else None
    except (TypeError, ValueError):
        return None


class ForgettingLog:
    """Append-only log of evicted items.

    Used to prevent re-derivation of forgotten beliefs and to
    track what has been forgotten for debugging/analysis.
    """

    def __init__(self, max_records: int = 500) -> None:
        """Initialize the forgetting log.

        F08 fix: Add max_records cap to prevent unbounded growth.
        When the cap is reached, oldest records are pruned (FIFO).
        M-07: a pruned record's content and derivation keys go into a fixed-size filter (_pruned), so pruning
        never ends forgotten status; a prune is O(1) (deque + refcounts).
        """
        self._records: collections.deque = collections.deque()
        self._hashes: collections.Counter = collections.Counter()
        self._derivs: collections.Counter = collections.Counter()
        self._ids: collections.Counter = collections.Counter()
        self._max_records = max(1, int(max_records))
        self._pruned: _PrunedKeys | None = None     # created on the first prune (state unchanged until then)
        self.pruned_total = 0

    def _add(self, rec: ForgetRecord) -> None:
        self._records.append(rec)
        self._hashes[rec.content_hash] += 1
        self._derivs[rec.deriv_hash] += 1
        self._ids[rec.item_id] += 1
        # F08b: Enforce max_records cap (FIFO pruning).  M-07: O(1) per prune; keys stay forgotten via _pruned.
        while len(self._records) > self._max_records:
            self._prune_one()

    @staticmethod
    def _dec(counter: collections.Counter, key: str) -> None:
        counter[key] -= 1
        if counter[key] <= 0:
            del counter[key]

    def _prune_one(self) -> None:
        pruned = self._records.popleft()
        self._dec(self._hashes, pruned.content_hash)
        self._dec(self._derivs, pruned.deriv_hash)
        self._dec(self._ids, pruned.item_id)
        self.pruned_total += 1
        # Only derivations can be re-derived (recalled/user items have no sources and never reach the reasoner
        # admission test), so only their keys enter the filter: ~17% of live prunes, which keeps the filter far
        # from saturation (see PRUNED_BITS_DEFAULT).
        if not pruned.derived_from:
            return
        if self._pruned is None:
            self._pruned = _PrunedKeys()
        self._pruned.add("c:" + pruned.content_hash)
        self._pruned.add("d:" + pruned.deriv_hash)

    def record(self, item: WMTMItem, tick: int) -> ForgetRecord:
        """Record that an item was evicted at the given tick."""
        ch = content_hash(item.content)
        rec = ForgetRecord(
            item_id=item.id,
            content_hash=ch,
            source_type=item.source_type,
            evicted_at_tick=tick,
            age_at_eviction=item.age,
            final_utility=item.utility,
            final_sti=item.attention.sti,
            derived_from=list(item.derived_from or []),
            deriv_hash=deriv_hash(item.content, item.derived_from, ch),
            final_confidence=_confidence_of(item),
        )
        self._add(rec)
        return rec

    def is_forgotten_key(self, dh: str) -> bool:
        """M-07: derivation key (deriv_hash) forgotten, in the window or pruned from it."""
        return dh in self._derivs or (self._pruned is not None and ("d:" + dh) in self._pruned)

    def is_forgotten(self, content: str, derived_from=None) -> bool:
        """Check if content matching this has been forgotten.

        F1 §4: with derived_from (a list, possibly empty) the check is on the derivation (conclusion + sorted
        sources): a forgotten conclusion derived again from different sources is NOT forgotten.  Without it
        (None) the old sentence-only check.  M-07: true also for keys pruned from the window."""
        if derived_from is None:
            ch = content_hash(content)
            return ch in self._hashes or (self._pruned is not None and ("c:" + ch) in self._pruned)
        return self.is_forgotten_key(deriv_hash(content, derived_from))

    def is_pruned_only(self, content: str, derived_from=None) -> bool:
        """M-07 diagnostics: forgotten only through the pruned-key filter (no record in the window)."""
        if derived_from is None:
            return content_hash(content) not in self._hashes and self.is_forgotten(content)
        return deriv_hash(content, derived_from) not in self._derivs and self.is_forgotten(content, derived_from)

    def pruned_fp_rate(self) -> float:
        """Estimated false-positive rate of the pruned-key filter (0.0 before the first prune)."""
        return self._pruned.fp_rate() if self._pruned is not None else 0.0

    def is_id_forgotten(self, item_id: str) -> bool:
        """Check if an item ID has been forgotten."""
        return item_id in self._ids

    def should_re_admit(
        self,
        content: str,
        sti_threshold: float = 5.0,
        current_sti: float = 0.0,
        derived_from=None,
    ) -> bool:
        """Decide whether to re-admit a previously forgotten item.

        Returns True if the item should be re-admitted (e.g., because
        current attention is high enough to override the forgetting).
        """
        # M-07: derived_from as in is_forgotten; a key pruned from the window is still forgotten here.
        if not self.is_forgotten(content, derived_from):
            return True  # Never forgotten, allow
        return current_sti >= sti_threshold

    def get_records(self) -> list[ForgetRecord]:
        """Return all forgetting records."""
        return list(self._records)

    @property
    def max_records(self) -> int:
        return self._max_records

    def clear(self) -> None:
        """Clear the log (for testing)."""
        self._records.clear()
        self._hashes.clear()
        self._derivs.clear()
        self._ids.clear()
        self._pruned = None
        self.pruned_total = 0

    def __len__(self) -> int:
        """Return the number of logged eviction events."""
        return len(self._records)

    # -- F01b: serialization for persistence across subprocess boundaries --

    def to_dict(self) -> dict:
        """Serialize forgetting log state for persistence."""
        d = {
            "max_records": self._max_records,
            "records": [
                {
                    "item_id": rec.item_id,
                    "content_hash": rec.content_hash,
                    "source_type": rec.source_type,
                    "evicted_at_tick": rec.evicted_at_tick,
                    "age_at_eviction": rec.age_at_eviction,
                    "final_utility": rec.final_utility,
                    "final_sti": rec.final_sti,
                    "derived_from": rec.derived_from,
                    **({"final_confidence": rec.final_confidence} if rec.final_confidence is not None else {}),
                }
                for rec in self._records
            ],
        }
        if self._pruned is not None:      # M-07: absent until the first prune, so small logs save as before
            d["pruned"] = self._pruned.serialize()
            d["pruned_total"] = self.pruned_total
        return d

    @classmethod
    def from_dict(cls, d: dict, max_records: int | None = None) -> "ForgettingLog":
        """Restore forgetting log from serialized dict.

        M-07: the cap is applied (max_records argument, else the saved one, else 500); records over the cap are
        pruned oldest-first into the pruned-key filter, so they stay forgotten.  Old saved logs (no "pruned",
        no final_confidence) load unchanged."""
        cap = max_records if max_records is not None else d.get("max_records", 500)
        log = cls(max_records=cap)
        if isinstance(d.get("pruned"), dict):
            try:
                log._pruned = _PrunedKeys.deserialize(d["pruned"])
                log.pruned_total = int(d.get("pruned_total", 0))
            except Exception:
                log._pruned = None
        for rec_d in d.get("records", []):
            rec = ForgetRecord(
                item_id=rec_d["item_id"],
                content_hash=rec_d["content_hash"],
                source_type=rec_d.get("source_type", "recalled"),
                evicted_at_tick=rec_d.get("evicted_at_tick", 0),
                age_at_eviction=rec_d.get("age_at_eviction", 0),
                final_utility=rec_d.get("final_utility", 0.0),
                final_sti=rec_d.get("final_sti", 0.0),
                derived_from=rec_d.get("derived_from", []) or [],
                final_confidence=rec_d.get("final_confidence"),
            )
            # F1 §4: the derivation key is not persisted (state format unchanged); recomputed from content_hash + sources
            rec.deriv_hash = deriv_hash("", rec.derived_from, rec.content_hash)
            log._add(rec)
        return log
