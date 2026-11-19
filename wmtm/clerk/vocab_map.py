"""Fixed vocabulary map: Clerk (parser-clerk e2e6aba, manual v11.5 + tests/projection/test_linkform.py)
heads -> wmtm predicate names (t-2026-11-18-wmtm-clerk-ab, committed BEFORE any arm-B parse).

Order rules (answer-2): instance-of -> Member; class-to-class kind-of/subset-of -> Inheritance;
Implication keeps $x.  Individual vs class follows manual v11.5 s.3: "a symbol made of a name or a
kind's word and a number is an individual's id (idris-1); any other symbol is a kind".
Source rows (Clerk linkform typing table) noted per entry; where Clerk says Inheritance for an
individual (isa fido dog), the order's instance-of -> Member rule wins.
"""
import re

INDIVIDUAL_ID = re.compile(r"^[a-z][a-z0-9-]*-[0-9]+$")   # manual v11.5 s.3 (idris-1, petra-2)

# Clerk head -> (wmtm head when subject is an individual, wmtm head when subject is a class)
COPULA = {
    "isa":       ("Member", "Inheritance"),   # derived.py ISA S64; linkform (isa fido dog)
    "is-a":      ("Member", "Inheritance"),   # linkform (is-a robert astronaut)
    "is":        ("Member", "Inheritance"),   # linkform (is robert astronaut)
    "instance-of": ("Member", "Member"),      # order: instance-of -> Member (0 hits in Clerk e2e6aba)
    "member-of": ("Member", "Member"),        # linkform (member-of robert crew) -> Member
    "kind-of":   ("Inheritance", "Inheritance"),  # linkform (kind-of coffee-drinker caffeinated)
    "subset-of": ("Inheritance", "Inheritance"),  # order (0 hits in Clerk e2e6aba)
}
ONE_ARG = ("Member", "Inheritance")            # (K x): linkform (astronaut robert) -> x in class K
IDENTITY = {"equal": "Similarity", "same-as": "Similarity", "identity": "Similarity"}  # linkform
NAME = {"called": "Name"}                      # linkform Called; wmtm KNOWN_UNUSED Name (label of a witness)
RULE = {"implies": "Implication"}              # (forall ($x) (implies A B)) -> Implication, $x kept
CONNECTIVE = {"and": "And", "or": "Or", "not": "Not"}
CONTEXT = {"in-context": "Context"}
BINDERS = ("forall", "exists", "most")        # forall/exists-in-antecedent -> $var; exists elsewhere -> skolem
PEELED = ("truth-scope", "manner-of-knowing", "hypothesis")  # peeled at top level as Clerk's key rule does
DEFAULT = "Evaluation"                         # any other head of >=2 args: (Evaluation h (List ...))
UNMAPPED = ("excludes", "says", "believes", "asks", "requests", "degree", "habit", "at-stake",
            "quantity", "because", "although")  # logged as unmapped units, never loaded as facts


def is_individual(sym) -> bool:
    return isinstance(sym, str) and bool(INDIVIDUAL_ID.match(sym))


def copula_head(head: str, subject) -> str:
    ind, cls = COPULA[head]
    return ind if (is_individual(subject) or str(subject).startswith("sk")) else cls
