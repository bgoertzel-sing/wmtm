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


def test_statement_labels_unique_across_notes():
    ops, meta = _plan([("na", _note(("Lamine sold a quilt.", _sold("Lamine")))),
                       ("nb", _note(("Yusra sold a quilt.", _sold("Yusra"))))], rules=False)
    import re as _re
    labs = [_re.match(r"\(: (\S+) ", x).group(1) for k, x in ops if k == "atom" and not x.startswith("(: kind__")
            and not x.startswith("(: by_")]
    assert len(labs) == len(set(labs))
    assert any(l.endswith("__na") for l in labs) and any(l.endswith("__nb") for l in labs)


# t-2026-11-15-wmtm-master-shadow-wiring: goal builder + cached-parse note reader (synthetic only)

def test_rule_goals_forward_one_step():
    rule = "(: r1 (Implication (Member $x quilt) (Member $x textile)) (STV 1.0 0.9))"
    ops = [("pred", "Member"), ("atom", rule),
           ("atom", "(: s1 (Member q1 quilt) (STV 1.0 0.9))"),
           ("atom", "(: s2 (Member q2 quilt) (STV 1.0 0.9))"),
           ("atom", "(: s3 (Member q2 textile) (STV 1.0 0.9))")]
    goals, per = ML.rule_goals(ops, [rule])
    assert goals == {"(Member q1 textile)": "r1"}          # q2 already stated -> not a goal
    assert per == {"r1": 1}


def test_rule_goals_ignores_unseeded_implications():
    rule = "(: r1 (Implication (Member $x quilt) (Member $x textile)) (STV 1.0 0.9))"
    ops = [("atom", rule), ("atom", "(: s1 (Member q1 quilt) (STV 1.0 0.9))")]
    goals, _ = ML.rule_goals(ops, [])
    assert goals == {}


def test_notes_from_parsed_missing_cache_reports_absent(tmp_path):
    notes, info = ML.notes_from_parsed(T, str(tmp_path / "none.jsonl"), ["na", "nb"])
    assert notes == [] and info["complete"] == 0 and info["absent"] == ["na", "nb"]


# review 1, finding 3: build_snapshot with shadow_load_order=master_ops (synthetic parsed.jsonl, no note-derived content)

def _parsed_rows(doc, sents, good=True):
    """Rows of a sentence-mode parsed.jsonl for one synthetic note: each reply made under the context of the earlier
    sentences (context_sha256 as tmpl.blocks.walk checks it)."""
    ML._tmpl(T)
    from tmpl import blocks as B
    rows, prior = [], []
    for k, (text, inst) in enumerate(sents, 1):
        ctx = B.context_section(prior)
        reply = {"response": {"instances": inst, "unmapped": []},
                 "item": {"context_sha256": B._sha(ctx) if ctx else None}}
        if not good:
            reply = {"error": "synthetic failure"}
        rows.append({"id": "%s.s%02d" % (doc, k), "dataset": "syn", "doc": doc, "sent": k, "text": text, "reply": reply})
        prior.append({"k": k, "text": text, "instances": B.qualify(inst, k)})
    return rows


class _It:
    def __init__(s, i, st="note"): s.id = i; s.source_type = st


class _St:
    def __init__(s, ids): s.items = [_It(*x) if isinstance(x, tuple) else _It(x) for x in ids]
    def get_active_set(s): return list(s.items)


def _snap(tmp_path, ids, rows, **over):
    import json
    from wmtm import pc_shadow as PS, runtime_config as rc
    p = tmp_path / "parsed.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    cfg = rc.resolve()
    cfg.update(shadow_load_order="master_ops", shadow_sph_templates=T, shadow_master_parsed=str(p), shadow_max_goals=0)
    cfg.update(over)
    return PS.build_snapshot(_St(ids), k=len(ids), cfg=cfg)


def _rows_two_notes():
    return (_parsed_rows("na", [("A progress report was sold.", _sold("Lamine", "report", ["progress"]))])
            + _parsed_rows("nb", [("A progress report was sold.", _sold("Yusra", "report", ["progress"]))]))


def test_build_snapshot_master_ops_recipe_order_and_sources(tmp_path):
    sp = _snap(tmp_path, ["na", "nb", "nc", ("d1", "derived")], _rows_two_notes()
               + _parsed_rows("nbad", [("Lamine sold a quilt.", _sold("Lamine"))], good=False))
    ops, meta = sp["master_ops"], sp["master_meta"]
    assert sp["load_order"] == "master_ops" and sp["atoms"] == []
    assert meta["kb_predicates"] > 0 and all(k == "pred" for k, _ in ops[:meta["kb_predicates"]])
    rules = ML.seeded_rules(T)
    assert [x for _, x in ops[meta["kb_predicates"]:meta["kb_predicates"] + len(rules)]] == list(dict.fromkeys(rules))
    atoms = [x for k, x in ops if k == "atom"]; preds = [x for k, x in ops if k == "pred"]
    assert len(atoms) == len(set(atoms)) and len(preds) == len(set(preds))
    defs = [x for x in atoms if x.startswith("(: kind__report__mod_progress ")]
    assert len(defs) == 1 and meta["shared_definitions"] >= 1                     # shared definition once
    srcs = {s for v in sp["atom_src"].values() for s in (v if isinstance(v, (list, tuple, set)) else [v])}
    assert {"na", "nb"} <= srcs and sp["label_fact"]                              # sources present in the spec
    assert sp["master_notes"]["complete"] == 2 and sp["master_notes"]["absent"] == ["nc"]
    assert sp["semparse_items"] == 2 and sp["unparsed_items"] == 1 and sp["derived_items"] == 1


def test_build_snapshot_master_ops_deterministic_no_narrow_preload(tmp_path, monkeypatch):
    from wmtm import semparse_adapter as SA
    calls = []
    monkeypatch.setattr(SA, "narrow_preload", lambda *a, **k: calls.append(1))
    a = _snap(tmp_path, ["na", "nb"], _rows_two_notes())
    b = _snap(tmp_path, ["nb", "na"], _rows_two_notes())                     # store order must not matter
    assert a["master_ops"] == b["master_ops"] and a["goals"] == b["goals"] and calls == []


def test_build_snapshot_master_ops_goal_cap_and_templates_required(tmp_path):
    full = _snap(tmp_path, ["na", "nb"], _rows_two_notes())
    if full["goal_total"] > 1:
        cap = _snap(tmp_path, ["na", "nb"], _rows_two_notes(), shadow_max_goals=1)
        assert cap["goals"] == full["goals"][:1] and cap["goal_total"] == full["goal_total"]
    with pytest.raises(RuntimeError):
        _snap(tmp_path, ["na"], _rows_two_notes(), shadow_sph_templates="")


def test_build_snapshot_flag_off_has_no_master_ops(tmp_path, monkeypatch):
    import _fake_semparse; _fake_semparse.install(monkeypatch)
    from wmtm import pc_shadow as PS, runtime_config as rc
    from wmtm.store import WMTMStore
    st = WMTMStore(); st.admit("s0", "cat is a mammal", source_type="recalled", initial_sti=1.0)
    for lo in (None, "legacy", ""):
        cfg = rc.resolve(); cfg.update(shadow_master_parsed=str(tmp_path / "bogus.jsonl"), shadow_sph_templates=T)
        if lo is not None: cfg["shadow_load_order"] = lo
        sp = PS.build_snapshot(st, k=1, cfg=cfg)
        assert "master_ops" not in sp and sp.get("load_order") != "master_ops"
