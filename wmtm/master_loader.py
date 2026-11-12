"""master-adopt-v2: load sentence-mode parses the way semantic-parsing-hitl 24e37182 templates/README.md says
(upstream PeTTaChainer master recipe).  Order, which matters on that engine:
  (1) once per KB: declare tmpl.lower.predicates("pettachainer-master") positive-only;
  (2) the "(: ..." lines of generated/seeded_rules.pettachainer-master.metta;
  (3) per note, per sentence (tmpl.blocks.block_records): lower(rec, "pettachainer-master", symbols=names),
      declare low["predicates"] BEFORE that sentence's statements, then load statements + definitions.
Our name table (``names_for``): a named individual (Name sym "Label") with one bearer in its note gets slug(label),
shared across notes; every other sk_ symbol gets a per-note suffix so two notes' witnesses stay apart.  A definition
(kind__/by_) two notes share keeps its own name and is loaded once (a restatement, not new evidence).
Pure planning: ``plan`` returns the ordered ops [("pred", name) | ("atom", text)]; ``apply`` runs them on a chainer.
Upstream code is imported, never edited."""
from __future__ import annotations
import os, re, sys

from .name_resolve import slug


def _tmpl(tdir):
    tdir = os.path.expanduser(tdir)
    if tdir not in sys.path:
        sys.path.insert(0, tdir)
    from tmpl import lower as L, blocks as B, catalog as CAT   # noqa: E402 (upstream, MIT)
    return L, B, CAT


def seeded_rules(tdir):
    with open(os.path.join(os.path.expanduser(tdir), "generated", "seeded_rules.pettachainer-master.metta"),
              encoding="utf-8") as fh:
        return [ln.strip() for ln in fh if ln.strip().startswith("(:")]


def _syms(term):
    if isinstance(term, list):
        for x in term:
            yield from _syms(x)
    elif isinstance(term, str):
        yield term


def names_for(note_id, records):
    """-> symbols table for one note's records (all sentences together)."""
    labels = {}
    for r in records:
        t = r["term"]
        if isinstance(t, list) and len(t) == 3 and t[0] == "Name" and isinstance(t[1], str):
            labels.setdefault(t[1], str(t[2]))
    by = {}
    for sym, lab in labels.items():
        by.setdefault(slug(lab), []).append(sym)
    suffix = "__" + re.sub(r"[^A-Za-z0-9]", "_", note_id)
    out = {}
    for base, syms in by.items():
        if len(syms) == 1:
            out[syms[0]] = base
    for r in records:
        for s in _syms(r["term"]):
            if s.startswith("sk_") and s not in out:
                out[s] = s + suffix
    return out


def plan(tdir, notes, kb_once=True, rules=True, catalog=None):
    """notes: [(note_id, prior)] with prior = tmpl.blocks.walk(...)[0] for that note.
    -> (ops, meta).  meta: counts and, per note, sentences ok/malformed, predicates, statements, definitions."""
    L, B, CAT = _tmpl(tdir)
    catalog = catalog or CAT.load()
    ops, seen_pred, seen_atom = [], set(), set()
    meta = {"kb_predicates": 0, "rules": 0, "notes": {}, "shared_definitions": 0}
    def pred(n):
        if n not in seen_pred:
            seen_pred.add(n); ops.append(("pred", n)); return True
        return False
    def atom(a):
        if a not in seen_atom:
            seen_atom.add(a); ops.append(("atom", a)); return True
        return False
    if kb_once:
        for n in L.predicates(L.MASTER):
            meta["kb_predicates"] += pred(n)
    if rules:
        for r in seeded_rules(tdir):
            meta["rules"] += atom(r)
    for nid, prior in notes:
        recs = B.block_records(prior, catalog)
        allrec = [x for rec in recs for x in rec.get("records") or []]
        names = names_for(nid, allrec)
        m = {"sentences": len(recs), "malformed": sum(r["status"] != "ok" for r in recs), "predicates": 0,
             "statements": 0, "definitions": 0, "definitions_shared": 0, "names": sum(not v.startswith("sk_") for v in names.values())}
        for rec in recs:
            if rec["status"] != "ok" or rec.get("kind") == "question":
                continue
            low = L.lower({"records": rec["records"], "types": rec["types"], "functions": rec["functions"]},
                          L.MASTER, symbols=names)
            for n in low["predicates"]:                 # BEFORE this sentence's statements
                m["predicates"] += pred(n)
            for s in low["statements"]:
                m["statements"] += atom(s)
            for d in low["definitions"]:
                if atom(d): m["definitions"] += 1
                else: m["definitions_shared"] += 1
        meta["shared_definitions"] += m["definitions_shared"]
        meta["notes"][nid] = m
    meta["ops"] = len(ops)
    return ops, meta


def apply(h, ops):
    """Run planned ops on a PeTTaChainer; -> (pred_fail, add_fail)."""
    pf = af = 0
    for kind, x in ops:
        try:
            h.set_positive_only_predicate(x) if kind == "pred" else h.add_atom(x)
        except Exception:
            if kind == "pred": pf += 1
            else: af += 1
    return pf, af
