"""Track J: parse-quality gate.  Synthetic facts only."""
import json
from wmtm import parse_gate as pg, pc_admit, runtime_config as rc
from wmtm.store import WMTMStore

ST = pg.settings(rc.resolve(None, environ={}))


def test_defaults_and_flags_file(tmp_path):
    assert ST["on"] and ST["max_per_fact"] == 3 and "trivial" in ST["broad"] and "mostly" in ST["hedged"]
    (tmp_path / rc.FLAGS_FILENAME).write_text(json.dumps({"gate_max_per_fact": 5, "gate_broad_action": "discount",
                                                          "gate_hedged_action": "bogus", "gate_min_conf": 0.6}))
    st = pg.settings(rc.resolve(str(tmp_path), environ={}))
    assert st["max_per_fact"] == 5 and st["broad_action"] == "discount" and st["hedged_action"] == "reject" and st["min_conf"] == 0.6


def test_quantifiers_parsed():
    q = pg.quantifiers(['(: a (QuantifierPhrase widget trivial "mostly") (STV 1.0 0.99))',
                        '(Interpretation x (: b (QuantifierPhrase gadget shiny "no") (STV 1.0 0.99)))'])
    assert q == {("widget", "trivial"): "mostly", ("gadget", "shiny"): "no"}


def test_rules():
    keep = ("Inheritance", "cat", "mammal", 0.9, 0.9)
    assert pg.check_fact(keep, None, ST) == (keep, None, "keep")
    assert pg.check_fact(("Inheritance", "sk_x__i", "mammal", 0.9, 0.9), None, ST)[1] == "placeholder_subject"
    assert pg.check_fact(("Inheritance", "it", "mammal", 0.9, 0.9), None, ST)[1] == "placeholder_subject"
    assert pg.check_fact(("Inheritance", "cat", "mammal", 0.9, 0.1), None, ST)[1] == "low_confidence"
    assert pg.check_fact(("Inheritance", "request", "open", 0.9, 0.9), "no", ST)[1] == "negative_quantifier"
    assert pg.check_fact(("Inheritance", "widget", "trivial", 0.9, 0.9), None, ST)[:2] == (None, "broad_category")
    assert pg.check_fact(("Inheritance", "widget", "cheap", 0.9, 0.9), "mostly", ST)[:2] == (None, "hedged_quantifier")
    assert pg.check_fact(("Implies", "rain", "thing", 0.9, 0.9), None, ST)[0] is not None   # broad applies to is-a only


def test_discount_and_off():
    st = dict(ST, broad_action="discount", hedged_action="discount", discount=0.5)
    f, why, act = pg.check_fact(("Inheritance", "widget", "trivial", 0.9, 0.9), "mostly", st)
    assert act == "discount" and why == "broad_category+hedged_quantifier" and f[3] == 0.225
    f = ("Inheritance", "sk_a", "trivial", 0.9, 0.01)
    assert pg.check_fact(f, "no", dict(ST, on=False)) == (f, None, "keep")


def test_gate_facts_records_decisions():
    kept, dec = pg.gate_facts([("Inheritance", "cat", "mammal", 0.9, 0.9), ("Inheritance", "widget", "trivial", 0.9, 0.9)],
                              {("widget", "trivial"): "mostly"}, ST, "i1")
    assert [k[1] for k in kept] == ["cat"] and dec[0]["reason"] == "broad_category" and dec[0]["quant"] == "mostly"
    assert pg.summary(dec) == {"rejected": {"broad_category": 1}, "discounted": {}}


def test_cap_per_fact():
    pairs = [("c%d" % i, ["(Inheritance widget x)", "f%d" % i]) for i in range(6)]
    kept, n, over = pg.cap_per_fact(pairs, dict(ST, max_per_fact=2))
    assert kept == ["c0", "c1"] and n == 4 and over == {"(Inheritance widget x)": 4}
    assert pg.cap_per_fact(pairs, dict(ST, max_per_fact=0))[1] == 0


def test_load_candidates_applies_cap(tmp_path):
    st = WMTMStore(); st.admit("s0", "a is a b", source_type="recalled", initial_sti=1.0)
    rows = [{"goal": "(Inheritance a%d hub)" % i, "stv": [0.9, 0.9 - i * 0.01], "proof": "(inh_trans sp%d sp99)" % i,
             "sources": ["s0"], "facts": ["(Inheritance x%d b)" % i, "(Inheritance b hub)"]} for i in range(8)]
    doc = {"ts": 9e12, "spec_ts": 9e12, "status": "ok", "canary_ok": True, "results": rows, "py_invalid_chain": []}
    (tmp_path / pc_admit.ADMIT_FILE).write_text(json.dumps(doc))
    cands, info = pc_admit.load_candidates({"shadow_dir": str(tmp_path), "gate_max_per_fact": 3}, st, now=9e12)
    assert [c.content for c in cands] == ["a0 is a hub", "a1 is a hub", "a2 is a hub"]
    assert info["dropped"]["per_fact_cap"] == 5 and info["cap_hit"] == {"(Inheritance b hub)": 5}


def test_build_snapshot_gates_before_kb(tmp_path, monkeypatch):
    from wmtm import pc_shadow
    import _fake_semparse; _fake_semparse.install(monkeypatch)
    st = WMTMStore()
    for i, t in enumerate(["cat is a mammal", "mammal is a animal", "dog is a thing"]):
        st.admit("s%d" % i, t, source_type="recalled", initial_sti=1.0 - i * 0.01)
    cfg = dict(rc.resolve(None, environ={}), semparse_dir=str(tmp_path / "none"))
    sp = pc_shadow.build_snapshot(st, 1, 10, cfg)
    assert not any("thing" in a for a in sp["atoms"]) and any("mammal" in a for a in sp["atoms"]) and sp["gate"]["rejected"] == {"broad_category": 1}
    assert all(sp["label_fact"][k].startswith("(") for k in sp["atom_src"])


def test_review_log(tmp_path):
    spec = {"cycle": 2, "label_fact": {"sp0": "(Inheritance b hub)"}, "fact_src": [["Inheritance", "b", "hub", "s0"]],
            "gate": {"decisions": [{"reason": "broad_category"}]}}
    rec = {"status": "ok", "queries": [{"goal": "(Inheritance a%d hub)" % i, "ok": True, "proof": "(inh_trans sp0 sp%d)" % (i + 1)} for i in range(3)]
           + [{"goal": "(Inheritance q hub)", "ok": False}]}
    doc = pg.review(str(tmp_path), rec, spec, {"gate_review_min": 3})
    assert doc["many_conclusions"]["(Inheritance b hub)"]["n"] == 3
    assert "disagreements" not in doc                                # Track K: no Python comparison
    assert len((tmp_path / pg.REVIEW_FILE).read_text().splitlines()) == 1


def test_identifier_category_track_m():
    """Track M: commit hashes / hex ids typed as categories (Track K: 0a1b2c3 / id_4d5e6f7 'is a branch')."""
    rej = [("Member", "0a1b2c3", "topic_branch"), ("Member", "id_4d5e6f7", "release_branch"),
           ("Inheritance", "pin", "c_2b3c4d5"), ("Member", "deadbeef1234", "branch"),
           ("Member", "c_5e6f7a8", "repo"), ("Inheritance", "cat", "0f1e2d3c")]
    for f in rej:
        assert pg.check_fact(f + (0.9, 0.9), None, ST)[1:] == ("identifier_category", "reject"), f
    keep = [("Member", "c_5e6f7a8", "commit"), ("Member", "c_7c8d9e0", "merged"),
            ("Member", "pettachainer_36b3fe6_dedup", "vendor"), ("Member", "module_build_20260101", "branch"),
            ("Member", "agent_demo_live_20260101", "fork_branch"), ("Member", "ltm_path", "dir"),
            ("Implies", "0a1b2c3", "topic_branch"), ("Member", "decade", "branch")]
    for f in keep:
        assert pg.check_fact(f + (0.9, 0.9), None, ST)[1] is None, f
    assert pg.is_identifier("0a1b2c3") and pg.is_identifier("id_4d5e6f7") and not pg.is_identifier("abcdefa")
    d = pg.check_fact(("Member", "0a1b2c3", "branch", 0.9, 0.9), None, dict(ST, identifier_action="discount"))
    assert d[1:] == ("identifier_category", "discount") and d[0][3] == 0.45
    assert pg.check_fact(("Member", "0a1b2c3", "branch", 0.9, 0.9), None, dict(ST, identifier_action="keep"))[1] is None
