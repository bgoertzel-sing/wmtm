"""Catalog mode (semantic-parsing-hitl >= 1f1a7a6f): JSON instances -> upstream tmpl.validate -> atoms.

Synthetic data only: the sentence and reply below are an invented example in the shape of
upstream's templates/suite/raw (no real memories).  Tests that need the upstream checkout
skip unless WMTM_SEMPARSE_HITL points at it.
"""
import json
import os

import pytest

from wmtm import semparse_adapter as sp
from wmtm import semparse_catalog as C

HITL = os.environ.get("WMTM_SEMPARSE_HITL", "")
needs_hitl = pytest.mark.skipif(not os.path.isdir(os.path.join(HITL, "templates", "tmpl")),
                                reason="WMTM_SEMPARSE_HITL checkout not available")

TEXT = "Teodor bought the spindle from Yusra."
REPLY = json.dumps({"id": "s1", "instances": [
    {"t": "named-entity", "id": "n1", "name": "Teodor", "span": "Teodor"},
    {"t": "witness", "id": "x1", "class": "spindle", "definite": True, "span": "the spindle"},
    {"t": "named-entity", "id": "n2", "name": "Yusra", "span": "Yusra"},
    {"t": "acquisition", "id": "e1", "verb": "buy", "acquirer": "@n1", "object": "@x1",
     "source": "@n2", "tense": "past", "span": "Teodor bought the spindle from Yusra"}],
    "unmapped": [], "issues": []})


class FakeLoader:
    def __init__(self):
        self.atoms = []

    def add_atom(self, a):
        self.atoms.append(a)
        return "ok"


def test_extract_json_fences_and_prose():
    assert C.extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert C.extract_json('Here you go: {"a": 2} hope it helps') == {"a": 2}


def test_item_message_matches_upstream_shape():
    assert C.item_message("i1", "hi") == "Item id: i1\nTEXT: hi\n\nWrite the JSON object for this item."


def test_unknown_mode_rejected():
    with pytest.raises(ValueError):
        sp.SemParseAdapter(lambda s, u: "", system="S", mode="nope")


def test_hitl_root_missing_raises(monkeypatch):
    monkeypatch.setenv("WMTM_SEMPARSE_HITL", "/nonexistent")
    with pytest.raises(FileNotFoundError):
        C.hitl_root()


@needs_hitl
def test_bad_json_is_malformed_not_crash():
    o = C.reply_to_statements("not json at all", TEXT)
    assert o["status"] == "malformed" and o["findings"][0]["kind"] == "json"
    assert C.reply_to_statements('{"instances": 3}', TEXT)["status"] != "ok"


@needs_hitl
def test_reply_to_statements_known_answer():
    o = C.reply_to_statements(REPLY, TEXT)
    assert o["status"] == "ok", o["findings"]
    assert len(o["statements"]) == 8 and len(o["declarations"]) == 10


@needs_hitl
def test_adapter_catalog_mode_end_to_end(tmp_path):
    seen = []
    loader = FakeLoader()
    ad = sp.SemParseAdapter(lambda s, u: seen.append((s, u)) or REPLY, loader=loader,
                            mode="catalog", reject_log=str(tmp_path / "rej.jsonl"))
    assert ad.system and "instances" in ad.system          # PROMPT_CATALOG system prompt
    res = ad.parse_item("note-7", {"text": TEXT})
    assert seen[0][1].startswith("Item id: ") and "TEXT: " + TEXT in seen[0][1]
    assert res.catalog_status == "ok" and res.error is None
    assert len(res.accepted) == 8 and not res.rejected
    assert all("sk_" not in a or "__" in a for a in res.accepted)   # witnesses scoped per note
    assert len(res.declarations) == 10


@needs_hitl
def test_adapter_catalog_mode_bad_reply_logged(tmp_path):
    log = tmp_path / "rej.jsonl"
    ad = sp.SemParseAdapter(lambda s, u: "sorry, I cannot", mode="catalog", reject_log=str(log))
    res = ad.parse_item("note-8", {"text": TEXT})
    assert not res.accepted
    assert log.exists() and "catalog" in log.read_text()


def test_latency_and_usage_recorded():
    def llm(s, u):
        llm.last_usage = {"prompt_tokens": 100, "completion_tokens": 7, "note": "x"}
        return "(: a (P x) (STV 1.0 0.9))"
    llm.last_usage = None
    ad = sp.SemParseAdapter(llm, system="S")
    res = ad.parse_item("n1", {"text": "hello"})
    assert res.latency_s is not None and res.latency_s >= 0
    assert res.usage == {"prompt_tokens": 100, "completion_tokens": 7}


def test_llm_without_usage_attribute():
    ad = sp.SemParseAdapter(lambda s, u: "(: a (P x) (STV 1.0 0.9))", system="S")
    res = ad.parse_item("n2", {"text": "hello"})
    assert res.usage == {} and res.latency_s is not None


@needs_hitl
def test_adapter_catalog_span_finding_is_partial_and_logged(tmp_path):
    """review-2 #2: upstream span/graph lints (here span-not-verbatim) are logged and make the parse partial."""
    bad = json.loads(REPLY)
    bad["instances"][1]["span"] = "NOT IN NOTE"
    log = tmp_path / "rej.jsonl"
    ad = sp.SemParseAdapter(lambda s, u: json.dumps(bad), loader=FakeLoader(), mode="catalog",
                            reject_log=str(log))
    res = ad.parse_item("note-9", {"text": TEXT})
    assert res.catalog_status == "partial"
    assert any("span-not-verbatim" in why for _, why in res.rejected)
    recs = [json.loads(l) for l in log.read_text().splitlines()]
    assert any(r["item_id"] == "note-9" and "span-not-verbatim" in r["reason"] for r in recs)
