"""t-2026-11-24-wmtm-p01-class-links: a shadow pass that adds class-to-class links (Inheritance) the parse
already supports, plus the Member facts those links give.  Off by default (WMTM_CLASS_LINKS, runtime_config
"class_links"); with it off nothing calls ``derive`` and the atom stream is untouched.

Input: the lowered statements of one note, ``(: name term (STV s c))`` strings as load_arm writes them.
Output: new statements, each with the names of the statements it came from and the parse unit ids
(``s<sentence>_<instance>``, the prefix of every lowered instance statement's name).

Rules (each fires only on what the parse states; no world knowledge, no guessed generalisation):
  R1 generic_isa   a universal generic whose antecedent is one Member over a variable and whose consequent is one
                   Member over the SAME variable, strength >= 0.9 (every/each/all/bare plural):
                   (Implication (Member $x A) (Member $x B))  ->  (Inheritance A B), with that truth.
                   Does not fire for most/many/few/no (strength < 0.9), conditions, events, or a different variable.
  R2 narrow_subset (P-12) two narrowed classes A, B of the same base noun where B's restrictions are a strict
                   subset of A's: (Inheritance A B).  ``kind__`` already gives A -> base; R2 adds the missing
                   narrower -> less-narrow step.  Never fires across bases or for equal restriction sets.
  R3 member_link   (Member x A) stated, (Inheritance A B) stated or from R1/R2, (Member x B) not stated:
                   (Member x B).  x must be an individual (no variables).
  R4 identity_member (p01a, only with identity=True / WMTM_CLASS_LINKS_IDENTITY) (Same x y) stated between two
                   individuals and (Member y C) stated, (Member x C) not stated: (Member x C); both directions.
                   Never from variables, never chained, no coreference beyond the parse's own Same atoms.
"""
from __future__ import annotations
import hashlib, re

TRUTH_DEF = (1.0, 0.99)
_TOK = re.compile(r'\(|\)|"[^"]*"|[^\s()]+')
_UNIT = re.compile(r"^(s\d+_[a-z]+\d+)")


def _parse(s):
    t = _TOK.findall(s); i = 0
    def rd():
        nonlocal i
        x = t[i]; i += 1
        if x == "(":
            out = []
            while t[i] != ")":
                out.append(rd())
            i += 1
            return out
        return x
    return rd()


def _show(x):
    return "(" + " ".join(map(_show, x)) + ")" if isinstance(x, list) else x


def _num(s):
    return ("%g" % float(s))


def unit_of(name):
    m = _UNIT.match(name)
    return m.group(1) if m else None


def _stmt(rule, term, truth):
    body = _show(term)
    h = hashlib.sha256(body.encode()).hexdigest()[:10]
    return f"cl_{rule}__{h}", f"(: cl_{rule}__{h} {body} (STV {_num(truth[0])} {_num(truth[1])}))"


def derive(statements, identity=False):
    """statements: iterable of lowered statement strings of ONE note.  -> list of dicts
    {"rule", "atom", "sources": [statement names], "units": [parse unit ids]} in a stable order.
    identity=True (t-2026-11-26-wmtm-p01a, flag WMTM_CLASS_LINKS_IDENTITY, default off) enables R4."""
    mem, inh, nb, gen, mentions, same = {}, {}, {}, [], {}, {}
    for s in statements:
        n = _parse(s)
        if isinstance(n, list) and len(n) == 4 and isinstance(n[1], str):
            mentions[n[1]] = set(_TOK.findall(s))
        if not (isinstance(n, list) and len(n) == 4 and n[0] == ":" and isinstance(n[2], list)):
            continue
        name, term, tv = n[1], n[2], n[3]
        h = term[0] if term and isinstance(term[0], str) else None
        if h == "Member" and len(term) == 3 and all(isinstance(x, str) for x in term[1:]) and not term[1].startswith("$"):
            mem.setdefault((term[1], term[2]), name)
        elif h == "Inheritance" and len(term) == 3 and all(isinstance(x, str) for x in term[1:]):
            inh.setdefault((term[1], term[2]), name)
        elif h == "NarrowBy" and len(term) == 3 and isinstance(term[1], str):
            nb.setdefault(term[1], {})[_show(term[2])] = name
        elif h == "Same" and len(term) == 3 and all(isinstance(x, str) and not x.startswith("$") for x in term[1:]) and term[1] != term[2]:
            same.setdefault((term[1], term[2]), name)
        elif h == "Implication" and len(term) == 3:
            gen.append((name, term, tv))
    out, seen = [], set()

    def emit(rule, term, truth, sources):
        key = _show(term)
        if key in seen:
            return
        seen.add(key)
        nm, atom = _stmt(rule, term, truth)
        units = sorted({u for u in map(unit_of, sources) if u})
        out.append({"rule": rule, "name": nm, "atom": atom, "sources": list(sources), "units": units})

    new_links = {}
    # R1
    for name, (_, a, c), tv in gen:
        if not (isinstance(a, list) and isinstance(c, list) and len(a) == 3 and len(c) == 3):
            continue
        if a[0] != "Member" or c[0] != "Member" or not (isinstance(a[1], str) and a[1].startswith("$")) or a[1] != c[1]:
            continue
        if not (isinstance(a[2], str) and isinstance(c[2], str)) or a[2].startswith("$") or c[2].startswith("$") or a[2] == c[2]:
            continue
        if not (isinstance(tv, list) and tv[0] == "STV" and float(tv[1]) >= 0.9):
            continue
        if (a[2], c[2]) in inh:
            continue
        emit("generic_isa", ["Inheritance", a[2], c[2]], (float(tv[1]), float(tv[2])), [name])
        new_links[(a[2], c[2])] = [name]
    # R2
    base = {}
    for (s, o), nm in inh.items():
        if s.startswith("sk_") or nm is None or not nm.startswith("kind__"):
            continue
        base[s] = (o, nm)
    for A in sorted(nb):
        for B in sorted(nb):
            if A == B or A not in base or B not in base or base[A][0] != base[B][0]:
                continue
            ra, rb = set(nb[A]), set(nb[B])
            if not (rb < ra) or (A, B) in inh:
                continue
            src = [base[A][1], base[B][1]] + [nb[A][r] for r in sorted(ra)] + [nb[B][r] for r in sorted(rb)]
            src += sorted({mem[k] for k in mem if k[1] in (A, B)})
            src += sorted({nm for nm, syms in mentions.items() if unit_of(nm) and (A in syms or B in syms)} - set(src))
            if not any(unit_of(x) for x in src):
                continue                      # untraceable to a parse unit: never emitted
            emit("narrow_subset", ["Inheritance", A, B], TRUTH_DEF, src)
            new_links[(A, B)] = src
    # R4 (p01a, opt-in): a stated identity between two individuals carries each one's stated classes to the other.
    # Only stated (Same x y) atoms from the parse; no coreference guessing, no chaining through several Same atoms.
    if identity:
        for (x, y), snm in sorted(same.items()):
            for a, b in ((x, y), (y, x)):
                for (z, C), mnm in sorted(mem.items()):
                    if z == b and (a, C) not in mem:
                        emit("identity_member", ["Member", a, C], TRUTH_DEF, [snm, mnm])
    # R3
    links = {k: [v] for k, v in inh.items() if not k[0].startswith("sk_")}
    links.update(new_links)
    for (x, A), mnm in sorted(mem.items()):
        for (s, B), lsrc in sorted(links.items()):
            if s == A and (x, B) not in mem:
                emit("member_link", ["Member", x, B], TRUTH_DEF, [mnm] + lsrc)
    return out
