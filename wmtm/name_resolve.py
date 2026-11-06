"""P3 Deviation 6 (cos answer 4): resolve parser-1f1a7a6f named witnesses to deterministic symbols.

Parser 1f1a7a6f emits a named entity as a per-note witness plus a label: (Name sk_github_1__i_n1 "GitHub").
Man Hin's answer 1: the same name mints the same deterministic symbol across notes, unless one note has two
bearers of it.  His emitter (templates/tmpl/emit.py:158 slug, :444-455 assign_symbols) mints ``slug(name)`` for a
single bearer and ``slug(name)_k`` for k bearers in one text.  Here, before the gate:
  * a witness whose label is borne by no other witness in its note  -> slug(label)          (shared across notes)
  * k witnesses bearing one label inside one note                   -> slug(label)_k__i_<note> (note-scoped, reported)
  * a witness with several labels uses its first label (reported as an alias case)
  * unnamed witnesses are untouched (per-note prefix + sk_registry, as before).
Pure stdlib.
"""
from __future__ import annotations
import re, unicodedata

NAME = re.compile(r'\(Name\s+(sk_[A-Za-z0-9_\-]*__i_[A-Za-z0-9_]+)\s+"((?:[^"\\]|\\.)*)"\)')
_SYM_END = r"(?![A-Za-z0-9_\-])"
_SYM_START = r"(?<![A-Za-z0-9_\-$])"


def slug(text: str) -> str:
    """Verbatim copy of semparse-hitl@1f1a7a6f templates/tmpl/emit.py:158."""
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "x"


def plan(atom_strs):
    """-> (mapping sk -> symbol, report dict) for one note's atoms."""
    labels = {}
    for a in atom_strs or []:
        for sym, lab in NAME.findall(a):
            labels.setdefault(sym, [])
            if lab not in labels[sym]:
                labels[sym].append(lab)
    by_base = {}
    for sym, labs in labels.items():
        by_base.setdefault(slug(labs[0]), []).append(sym)
    mapping, multi = {}, []
    for base, syms in by_base.items():
        if len(syms) == 1:
            mapping[syms[0]] = base
        else:
            syms = sorted(syms, key=lambda s: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", s)])
            for k, s in enumerate(syms, 1):
                mapping[s] = "%s_%d__%s" % (base, k, "i_" + s.split("__i_", 1)[1])
            multi.append({"base": base, "labels": sorted({labels[s][0] for s in syms}), "witnesses": syms})
    aliases = [{"witness": s, "labels": l, "used": l[0]} for s, l in labels.items() if len(l) > 1]
    numeric = [b for b in by_base if b.isdigit()]
    return mapping, {"named": len(labels), "multi_bearer": multi, "aliases": aliases, "numeric_slugs": numeric}


def resolve(atom_strs):
    """-> (atoms with named witnesses replaced, report)."""
    mapping, rep = plan(atom_strs)
    if not mapping:
        return list(atom_strs or []), rep
    rx = re.compile(_SYM_START + "(" + "|".join(re.escape(s) for s in sorted(mapping, key=len, reverse=True)) + ")" + _SYM_END)
    return [rx.sub(lambda m: mapping[m.group(1)], a) for a in atom_strs], rep
