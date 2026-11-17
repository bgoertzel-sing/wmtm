"""t-2026-11-17-wmtm-variable-implication-test: note-stated Implications with variables, as the parser lowers them.

Synthetic only: tests/fixtures/variable_implications/ holds 6 parsed invented notes (notes.json) and their real sentence-mode
parser replies at semantic-parsing-hitl 24e37182 (parsed.jsonl, made by
reports/t-2026-11-17-wmtm-variable-implication-test/tools/drive.py).  No engine: these pin the lowered shapes and the
note-implication goal building (the 1dd5f47 logic, ported in the report's tools/nimpl_port.py) that the report's
PeTTaChainer run rests on.  Several assertions pin CURRENT gaps (marked GAP); a fix upstream should flip them.
Needs the sph 24e37182 templates: WMTM_PC_SHADOW_SPH_TEMPLATES=<checkout>/templates."""
import json, os, sys
import pytest
from wmtm import master_loader as ML

T = os.environ.get("WMTM_PC_SHADOW_SPH_TEMPLATES", "")
pytestmark = pytest.mark.skipif(not (T and os.path.isfile(os.path.join(T, "tmpl", "lower.py"))), reason="sph templates not set")
HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures", "variable_implications")
TOOLS = os.path.join(HERE, "..", "reports", "t-2026-11-17-wmtm-variable-implication-test", "tools")


@pytest.fixture(scope="module")
def kb():
    sys.path.insert(0, TOOLS)
    from nimpl_port import note_impl_goals
    cases = json.load(open(os.path.join(FIX, "notes.json")))["cases"]
    ids = [c["doc"] for c in cases]
    notes, info = ML.notes_from_parsed(T, os.path.join(FIX, "parsed.jsonl"), ids)
    ops, meta = ML.plan(T, notes)
    goals, st = note_impl_goals(ops, ML.seeded_rules(T), meta["atom_src"])
    by = {}
    for k, a in ops:
        n = ML._node(a) if k == "atom" else None
        if n and isinstance(n, list) and len(n) == 4 and isinstance(n[1], str):
            by.setdefault(n[1][-4:-1] if n[1].endswith("Z") else "", []).append((n[1], n[2]))
    return {"cases": {c["case"]: c for c in cases}, "info": info, "ops": ops, "meta": meta, "goals": goals, "st": st, "by": by}


def _impls(kb, nn):
    return [t for l, t in kb["by"].get("0%s" % nn[-2:], []) if isinstance(t, list) and t[0] == "Implication"]


def _vars(t):
    return sorted({x for x in ML._syms(t) if x.startswith("$")})


def test_all_notes_complete(kb):
    assert kb["info"]["complete"] == 6 and not kb["info"]["incomplete"] and not kb["info"]["absent"]


def test_c2_every_a_that_b_keeps_variables_and_builds_goal(kb):
    imp = _impls(kb, "02")
    assert len(imp) == 1 and _vars(imp[0]) == ["$e", "$x"]
    assert kb["goals"].get("(Member tweety happy)", "").startswith("nimpl:s1_r1_implication__ep_note_20991117T000002Z")


def test_c3_gap_pronoun_in_conclusion_is_skolemised(kb):
    imp = _impls(kb, "03")
    assert len(imp) == 1 and "$x" in _vars(imp[0])
    concl = imp[0][2]
    assert concl[0] == "Member" and concl[1].startswith("sk_they_1__")      # GAP: not $x, so the rule cannot reach marta
    assert "(Member marta loud)" not in kb["goals"]


def test_c1_gap_anything_x_is_y_is_not_an_implication(kb):
    assert _impls(kb, "01") == []                                          # GAP: lowered as Inheritance over a narrowed class
    inh = [t for l, t in kb["by"]["001"] if t[0] == "Inheritance"]
    assert ["Inheritance", "thing__member_acoustic", "quiet"] in inh


def test_c4_c5_gap_anything_adds_thing_premise(kb):
    for nn, concl in (("04", ["Member", "$x", "ball"]), ("05", ["Not", ["Member", "$x", "liquid"]])):
        flat = [t for t in _impls(kb, nn) if t[2] == concl]
        assert len(flat) == 1 and _vars(flat[0]) == ["$x"]                 # variables kept
        assert ["Member", "$x", "thing"] in flat[0][1][1:]                 # GAP: nothing states (Member _ thing)
    assert not any(g.startswith("(Member sk_toy") or g.startswith("(Member sk_pond") for g in kb["goals"])


def test_c6_near_miss_builds_no_goal(kb):
    assert len(kb["goals"]) == 1 and "trumpet" not in next(iter(kb["goals"]))
