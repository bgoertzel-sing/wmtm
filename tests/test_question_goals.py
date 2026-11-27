"""t-2026-11-24-wmtm-p05-questions-goals: P-05 question goals and R-10 confidence floor, synthetic only (no note-derived content).
Question tests need the sph 24e37182 templates: WMTM_PC_SHADOW_SPH_TEMPLATES=<checkout>/templates."""
import json, os, time, pytest
from wmtm import master_loader as ML, pc_admit
from wmtm.store import WMTMStore

T = os.environ.get("WMTM_PC_SHADOW_SPH_TEMPLATES", "")
needs_t = pytest.mark.skipif(not (T and os.path.isfile(os.path.join(T, "tmpl", "lower.py"))), reason="sph templates not set")


def _note(*sents):
    ML._tmpl(T)
    from tmpl import blocks as B
    return [{"k": k, "text": t, "instances": B.qualify(i, k), "unmapped": u} for k, (t, i, u) in enumerate(sents, 1)]


SOLD = [{"t": "named-entity", "id": "n1", "name": "Lamine"}, {"t": "witness", "id": "x1", "class": "quilt"},
        {"t": "transfer", "id": "e1", "verb": "sell", "giver": "@n1", "object": "@x1", "tense": "past"}]
ASK = [{"t": "named-entity", "id": "n1", "name": "Lamine"}, {"t": "witness", "id": "x1", "class": "quilt"},
       {"t": "transfer", "id": "e1", "verb": "sell", "giver": "@n1", "object": "@x1", "tense": "past"},
       {"t": "question", "id": "q1", "span": "Did Lamine sell a quilt?"}]
G00 = [{"span": "drop the widget?", "code": "G00", "construction": "synthetic"}]


def _notes():
    return [("na", _note(("Lamine sold a quilt.", SOLD, []), ("Did Lamine sell a quilt?", ASK, []), ("drop the widget?", [], G00)))]


@needs_t
def test_questions_off_by_default_and_no_meta_key():
    ops0, m0 = ML.plan(T, _notes())
    ops1, m1 = ML.plan(T, _notes(), questions=False)
    assert ops0 == ops1 and m0 == m1 and "questions" not in m0


@needs_t
def test_question_becomes_query_and_adds_no_fact():
    ops0, _ = ML.plan(T, _notes())
    ops1, m1 = ML.plan(T, _notes(), questions=True)
    assert ops0 == ops1                       # a question states nothing
    q = m1["questions"]
    assert q["found"] == 1 and q["malformed"] == 0 and q["unmapped_g00"] == 1
    assert len(q["queries"]) == 1 and "$" in q["queries"][0] and "sell" in q["queries"][0]
    assert q["query_note"][q["queries"][0]] == ("na", 2)


def _store():
    st = WMTMStore()
    st.admit("s0", "cat is a mammal", source_type="recalled", initial_sti=1.0)
    return st


def _doc(tmp_path, rows):
    doc = {"ts": time.time(), "spec_ts": time.time(), "cycle": 0, "status": "ok", "canary_ok": True, "results": rows}
    (tmp_path / pc_admit.ADMIT_FILE).write_text(json.dumps(doc))


ROWS = [{"goal": "(Inheritance a%d b)" % i, "stv": [0.9, c], "proof": "(inh_trans sp%d)" % i, "sources": ["s0"]}
        for i, c in enumerate((0.002, 0.7, 0.9, 0.98))]


def test_conf_floor_off_by_default(tmp_path):
    _doc(tmp_path, ROWS)
    cands, info = pc_admit.load_candidates({"shadow_dir": str(tmp_path), "reasoner_max_admit": 10}, _store())
    assert len(cands) == 4 and "below_floor" not in info["dropped"]


@pytest.mark.parametrize("floor,kept", [(0.5, 3), (0.75, 2), (0.95, 1)])
def test_conf_floor_drops_below(tmp_path, floor, kept):
    _doc(tmp_path, ROWS)
    cands, info = pc_admit.load_candidates({"shadow_dir": str(tmp_path), "reasoner_max_admit": 10,
                                            "reasoner_conf_floor": floor}, _store())
    assert len(cands) == kept and info["dropped"]["below_floor"] == 4 - kept
    assert all(c.confidence >= floor for c in cands)
