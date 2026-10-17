"""Track K test helper: the reasoner reads cached semparse atoms only, so synthetic tests fake the Track H cache.

install(monkeypatch) replaces pc_shadow._cache_lookup with a tiny deterministic parser for "x is a y" / "x -> y" /
"x implies y" texts.  Texts it cannot parse stay unparsed (no atoms), exactly like an item the LLM parser has not seen.
"""
import re
from wmtm import pc_shadow

_PATS = [(re.compile(r"^\s*(\w+) is an? (\w+)\s*\.?$", re.I), "Inheritance"),
         (re.compile(r"^\s*(\w+)\s*(?:->|implies)\s*(\w+)\s*\.?$", re.I), "Implies")]


def atoms_for(text):
    for rx, head in _PATS:
        m = rx.match(text)
        if m:
            return ["(: f_%s_%s (%s %s %s) (STV 1.0 0.9))" % (m.group(1).lower(), m.group(2).lower(), head,
                                                              m.group(1).lower(), m.group(2).lower())]
    return None


def install(monkeypatch):
    def lookup(items, cache_dir=None):
        return {it.id: a for it in items for a in [atoms_for(it.content)] if a is not None}
    monkeypatch.setattr(pc_shadow, "_cache_lookup", lookup)
