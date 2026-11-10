"""wmtm/parse_normalise.py - one layer between cached parser output and the shadow KB build.

t-2026-11-10-wmtm-normaliser (andy order 2026-11-09).  Every statement the parser emits is sorted into
exactly one of three classes, and nothing is dropped without being counted:

  mapped           rewritten (if needed) into the one form pc_shadow.semparse_facts / semparse_rules /
                   _parse_rules consume: (: id (H a b) tv) with H in SP_HEADS and symbol arguments, or a flat
                   (: id (Implication P C) tv) rule.
  known_unused     a parser shape we recognise but that carries no class content the reader uses
                   (labels, tense, clock time, counts).  Counted by shape, passed through unchanged.
  unrecognised     everything else (incl. GroupOf, event roles, Directive, ...).  Counted by shape and note
                   id, logged, reported, passed through unchanged (the reader ignores it as before).

Mappings (each has a test and a negative control in tests/test_parse_normalise.py):
  M1 Interpretation wrapper        (Interpretation "t" (: id X tv)) -> (: id X tv)
  M2 Narrow anywhere               every (Narrow base R..) class term with a symbol (or Narrow) base, in any
                                   argument position, -> its deterministic symbol pc_shadow.narrow_symbol(), plus
                                   ONE defining rule (Member $x <sym>) -> (Member $x <base>) (head-noun link,
                                   F7 nwdef) for each symbol that occurs in a mapped statement.
  M3 legacy flat Inheritance       (Inheritance a b) passes through unchanged (counted as mapped).
  M4 legacy Premises/Conclusions   (Implication (Premises ..) (Conclusions ..)) -> And form, one rule per
                                   conclusion (semparse_adapter.normalise, the same rewrite the adapter does at
                                   parse time for new parses).
  M5 catalog-mode facts/rules      (Member sk C), (Member S S), Implication over Member/Narrow: mapped as is
                                   (after M2).

Forbidden readings (order Do 2) - this module never:
  F1 bridges GroupOf to PartOf (GroupOf is counted as unrecognised: andy is asking Man Hin how membership works);
  F2 reads a modifier as a property: (Narrow suite (Mod test)) gives NO (Member $x test); the only rule built
     from a Narrow is the head-noun link to its base;
  F3 builds kind-of (Inheritance) statements from witness shapes ((Member sk_c__i_n C) never yields
     (Inheritance ...)); no new fact is ever created, only symbols renamed.
Pure stdlib + wmtm.semparse_adapter / pc_shadow helpers.
"""
from __future__ import annotations

import collections
import logging

log = logging.getLogger("wmtm.parse_normalise")

SP_HEADS = ("Inheritance", "Member", "Implies", "Similarity", "Evaluation")
KNOWN_UNUSED = {
    "Name": "label of a witness (used by name_resolve before this layer)",
    "Coref": "coreference link between witnesses",
    "Past": "tense", "Ongoing": "aspect", "Habitual": "aspect", "Still": "aspect", "Already": "aspect",
    "Hour": "clock time", "Minute": "clock time", "Month": "date", "Day": "date", "Year": "date",
    "Time": "event time", "Cardinality": "count", "Ordinal": "order", "Measure": "quantity",
    "Equivalence": "rule kind PeTTaChainer bdae8d7e rejects (pc_shadow.semparse_rules drops it)",
}
VERSION = "norm1"


def _is_sym(x) -> bool:
    return isinstance(x, str) and not x.startswith('"')


def shape(n, d=0) -> str:
    """Content-free shape signature: heads kept, leaves abstracted (S symbol, sk witness, $ variable, str)."""
    if isinstance(n, str):
        if n.startswith("$"):
            return "$"
        if n.startswith("sk_"):
            return "sk"
        if n.startswith('"'):
            return "str"
        try:
            float(n)
            return "N"
        except ValueError:
            return "S"
    if not n:
        return "()"
    h = n[0] if isinstance(n[0], str) else "?"
    if d >= 2:
        return "(%s ..)" % h
    return "(" + " ".join([h] + [shape(x, d + 1) for x in n[1:]]) + ")"


def _is_narrow(n) -> bool:
    return (isinstance(n, list) and len(n) >= 3 and n[0] == "Narrow"
            and (_is_sym(n[1]) or _is_narrow(n[1])))


def name_narrow_anywhere(node, defs):
    """M2: replace every Narrow class term (symbol or Narrow base) by its deterministic symbol, in any
    position.  defs collects symbol -> base symbol.  The restriction is NOT turned into any statement (F2)."""
    from .pc_shadow import narrow_symbol
    if _is_narrow(node):
        base = node[1] if _is_sym(node[1]) else name_narrow_anywhere(node[1], defs)
        sym = narrow_symbol(node)
        defs.setdefault(sym, base)
        return sym
    if isinstance(node, list):
        return [name_narrow_anywhere(x, defs) for x in node]
    return node


def _flat_atom(a) -> bool:
    return isinstance(a, list) and len(a) == 3 and all(_is_sym(x) for x in a) and a[0] in SP_HEADS


def _flat_rule(c) -> bool:
    if not (isinstance(c, list) and len(c) == 3 and c[0] == "Implication"):
        return False
    p, q = c[1], c[2]
    ps = p[1:] if isinstance(p, list) and p and p[0] == "And" else [p]
    return bool(ps) and all(_flat_atom(x) for x in ps) and _flat_atom(q)


def _syms(node, out):
    if isinstance(node, list):
        for x in node:
            _syms(x, out)
    elif isinstance(node, str):
        out.add(node)
    return out


def classify(content):
    """-> ("mapped", kind) | ("known_unused", head) | ("unrecognised", shape)."""
    if _flat_atom(content):
        return "mapped", "fact:" + content[0]
    if _flat_rule(content):
        return "mapped", "rule"
    h = content[0] if isinstance(content, list) and content and isinstance(content[0], str) else None
    if h in KNOWN_UNUSED:
        return "known_unused", h
    return "unrecognised", shape(content)


def new_report():
    return {"version": VERSION, "mapped": collections.Counter(), "known_unused": collections.Counter(),
            "unrecognised": collections.Counter(), "unrecognised_by_note": {}, "rewrites": collections.Counter(),
            "nwdef": 0, "notes": 0}


def normalise_atoms(atom_strs, note_id="?", report=None, nwdef=True):
    """Cached atom strings of one note -> (atom strings in the reader's form, report).

    Every input statement is counted exactly once in mapped / known_unused / unrecognised.  Output order:
    the input statements (rewritten where mapped), then the nwdef defining rules for Narrow symbols that occur
    in a mapped statement.  Unmapped statements pass through unchanged, so nothing is removed."""
    from .semparse_adapter import split_toplevel, to_str, normalise as _rule_normalise
    rep = new_report() if report is None else report
    rep["notes"] += 1
    byn = rep["unrecognised_by_note"].setdefault(str(note_id), collections.Counter())
    out, used = [], set()
    defs = {}

    def count(cls, key):
        rep[cls][key] += 1
        if cls == "unrecognised":
            byn[key] += 1

    # one cached atom string at a time: a torn string must not swallow the statements after it
    forms = [f for a in (atom_strs or []) for f in split_toplevel(str(a))]
    for src, node, err in forms:
        if err or not isinstance(node, list) or not node:
            count("unrecognised", "syntax_error"); out.append(src); continue
        if node[0] == "Interpretation" and len(node) == 3:
            node = node[2]; rep["rewrites"]["M1_interpretation"] += 1
        if not (isinstance(node, list) and len(node) == 4 and node[0] == ":"):
            count("unrecognised", "top:" + shape(node)); out.append(src); continue
        stmts = [node]
        c = node[2]
        if (isinstance(c, list) and len(c) == 3 and c[0] == "Implication"
                and any(isinstance(x, list) and x and x[0] in ("Premises", "Conclusions") for x in c[1:])):
            stmts = _rule_normalise(node); rep["rewrites"]["M4_premises_conclusions"] += 1
        for st in stmts:
            d = {}
            named = name_narrow_anywhere(st, d)
            cls, key = classify(named[2])
            if cls == "unrecognised":
                key = shape(st[2])              # report the parser's own shape (Narrow position visible)
            count(cls, key)
            if cls == "mapped":
                if d:
                    rep["rewrites"]["M2_narrow"] += len(d)
                    defs.update(d)
                    used |= set(d)
                out.append(to_str(named))
            else:
                out.append(to_str(st))          # unmapped: unchanged (Narrow inside it is left as is)
    if nwdef:
        # a nested Narrow's base symbol is itself defined; close over bases
        todo = list(used)
        while todo:
            s = todo.pop()
            b = defs.get(s)
            if b in defs and b not in used:
                used.add(b); todo.append(b)
        from .pc_shadow import narrow_defining_rules
        for r in narrow_defining_rules({s: defs[s] for s in used}):
            if r not in out:
                out.append(r); rep["nwdef"] += 1
    if not byn:
        rep["unrecognised_by_note"].pop(str(note_id), None)
    elif sum(byn.values()):
        log.info("parse_normalise: note %s unrecognised %s", note_id, dict(byn))
    return out, rep


def normalise_cached(cached, nwdef=True):
    """{note id: atom strings} -> ({note id: normalised atom strings}, report over all notes)."""
    rep = new_report()
    out = {}
    for iid in sorted(cached):
        out[iid], _ = normalise_atoms(cached[iid], iid, rep, nwdef=nwdef)
    return out, rep


def report_json(rep) -> dict:
    """JSON-safe report (shapes and note ids only, no note text)."""
    return {"version": rep["version"], "notes": rep["notes"], "nwdef": rep["nwdef"],
            "mapped": dict(sorted(rep["mapped"].items())),
            "known_unused": dict(sorted(rep["known_unused"].items())),
            "unrecognised": dict(sorted(rep["unrecognised"].items(), key=lambda kv: (-kv[1], kv[0]))),
            "unrecognised_by_note": {k: dict(sorted(v.items())) for k, v in sorted(rep["unrecognised_by_note"].items())},
            "rewrites": dict(sorted(rep["rewrites"].items()))}
