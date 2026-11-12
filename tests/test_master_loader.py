"""master-adopt-v2: the recipe loader (wmtm/master_loader.py) on synthetic notes only (no note-derived content).
Needs the sph 24e37182 templates: WMTM_PC_SHADOW_SPH_TEMPLATES=<checkout>/templates."""
import os, pytest
from wmtm import master_loader as ML

T = os.environ.get("WMTM_PC_SHADOW_SPH_TEMPLATES", "")
pytestmark = pytest.mark.skipif(not (T and os.path.isfile(os.path.join(T, "tmpl", "lower.py"))), reason="sph templates not set")


def _note(*sents):
    ML._tmpl(T)
    from tmpl import blocks as B
    return [{"k": k, "text": t, "instances": B.qualify(i, k)} for k, (t, i) in enumerate(sents, 1)]


def _sold(name, cls="quilt", mods=None):
    w = {"t": "witness", "id": "x1", "class": cls}
    if mods: w["mods"] = mods
    return [{"t": "named-entity", "id": "n1", "name": name}, w,
            {"t": "transfer", "id": "e1", "verb": "sell", "giver": "@n1", "object": "@x1", "tense": "past"}]


def _plan(notes, **kw):
    ML._tmpl(T)
    return ML.plan(T, notes, **kw)


def test_shared_class_definition_loaded_once():
    ops, meta = _plan([("na", _note(("A progress report was sold.", _sold("Lamine", "report", ["progress"])))),
                       ("nb", _note(("A progress report was sold.", _sold("Yusra", "report", ["progress"]))))], rules=False)
    defs = [x for k, x in ops if k == "atom" and x.startswith("(: kind__report__mod_progress ")]
    assert len(defs) == 1
    assert meta["notes"]["na"]["definitions"] >= 1 and meta["notes"]["nb"]["definitions_shared"] >= 1


def test_named_individual_shared_via_name_table():
    ops, meta = _plan([("na", _note(("Lamine sold a quilt.", _sold("Lamine")))),
                       ("nb", _note(("Lamine sold a quilt.", _sold("Lamine"))))], rules=False)
    atoms = [x for k, x in ops if k == "atom"]
    assert any("(Name lamine " in a for a in atoms)
    assert not any("sk_lamine" in a for a in atoms)
    quilts = {a.split("(Member ")[1].split()[0] for a in atoms if "(Member " in a and " quilt)" in a}
    assert len(quilts) == 2 and all(q.endswith(("__na", "__nb")) for q in quilts)   # witnesses kept apart


def test_predicates_declared_before_load():
    ops, meta = _plan([("na", _note(("A progress report was sold.", _sold("Lamine", "report", ["progress"]))))])
    first_atom = next(i for i, (k, _) in enumerate(ops) if k == "atom")
    assert meta["kb_predicates"] > 0 and all(k == "pred" for k, _ in ops[:meta["kb_predicates"]])
    assert first_atom >= meta["kb_predicates"] and meta["rules"] > 0
    pos = {x: i for i, (k, x) in enumerate(ops) if k == "pred"}
    assert "report__mod_progress" in pos
    use = next(i for i, (k, x) in enumerate(ops) if k == "atom" and "report__mod_progress" in x)
    assert pos["report__mod_progress"] < use
