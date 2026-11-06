"""P3 (Man Hin answer 1): per-note sk_* prefixing + wmtm's cross-note registry of unnamed entities."""
import json, os
import pytest
from wmtm import sk_registry as skr
from wmtm.sk_registry import SkRegistry
from wmtm.parse_cache import ParseCache, process_queue


@pytest.fixture(autouse=True)
def _legacy(monkeypatch):
    monkeypatch.setenv("WMTM_SEMPARSE_MODE", "legacy")


class LLM:
    def __init__(self, replies):
        self.replies, self.last_usage = replies, {}
    def __call__(self, system, user):
        for k, v in self.replies.items():
            if k in user:
                return v
        return ""


def _ad(llm):
    from wmtm.semparse_adapter import SemParseAdapter
    return SemParseAdapter(llm, loader=None, system="SYS")


def test_owner_and_scan():
    assert skr.owner("sk_report_1__i_n5") == "i_n5"
    got = skr.scan(["(: a (Member sk_report_1__i_n5 report) (STV 1.0 0.9))",
                    "(: b (Agent sk_x_1__i_n6 alice) (STV 1.0 0.9))", "(: c (Member alice person) (STV 1 1))"])
    assert got == {"sk_report_1__i_n5": {"report"}, "sk_x_1__i_n6": set()}     # named 'alice' not recorded


def test_same_unnamed_symbol_in_two_notes_is_two_entities(tmp_path):
    """Per-note prefix: sk_request_1 in n1 and in n2 must not collapse; named entities link by symbol."""
    llm = LLM({"first": "(: e1 (Member sk_request_1 request) (STV 1.0 0.9))\n(: e2 (Agent sk_request_1 bob) (STV 1.0 0.9))",
               "second": "(: e1 (Member sk_request_1 request) (STV 1.0 0.9))\n(: e2 (Agent sk_request_1 bob) (STV 1.0 0.9))"})
    c = ParseCache(str(tmp_path / "c"))
    c.enqueue([("n1", "first note", 1.0), ("n2", "second note", 0.9)])
    process_queue(c, llm, adapter=_ad(llm))
    a1, a2 = c.atoms_for("first note"), c.atoms_for("second note")
    assert any("sk_request_1__i_n1" in a for a in a1) and not any("__i_n2" in a for a in a1)
    assert any("sk_request_1__i_n2" in a for a in a2) and not any("__i_n1" in a for a in a2)
    assert all(" bob)" in a for a in a1 + a2 if "Agent" in a)                 # named: same symbol, unprefixed
    ents = SkRegistry(c.d).entities()
    assert set(ents) == {"sk_request_1__i_n1", "sk_request_1__i_n2"}
    assert ents["sk_request_1__i_n1"]["owner"] == "i_n1" and ents["sk_request_1__i_n1"]["kinds"] == ["request"]
    assert not any(e["linked"] for e in ents.values()) and SkRegistry(c.d).links() == []


def test_context_reuse_is_recorded_as_cross_note_link(tmp_path):
    """A later note that reuses an earlier note's scoped witness (Track O) is the only cross-note link."""
    llm = LLM({"kitten": "(: e1 (Member sk_kitten_1 kitten) (STV 1.0 0.9))",
               "scratched": "(: e2 (Member sk_scratch_1 scratch) (STV 1.0 0.9))\n"
                            "(: e3 (Agent sk_scratch_1 sk_kitten_1__i_n1) (STV 1.0 0.9))"})
    c = ParseCache(str(tmp_path / "c"))
    c.enqueue([("n1", "a kitten", 1.0)]); process_queue(c, llm, adapter=_ad(llm))
    c.enqueue([("n2", "it scratched", 1.0)]); process_queue(c, llm, adapter=_ad(llm))
    r = SkRegistry(c.d)
    assert r.links() == [("sk_kitten_1__i_n1", "i_n1", "i_n2")]
    e = r.entities()["sk_kitten_1__i_n1"]
    assert e["notes"] == ["i_n1", "i_n2"] and e["linked"] and e["kinds"] == ["kitten"]
    assert set(r.for_note("i_n2")) == {"sk_kitten_1__i_n1", "sk_scratch_1__i_n2"}
    assert e["hash"] is not None


def test_failed_or_empty_parse_writes_no_rows_and_torn_line_is_skipped(tmp_path):
    c = ParseCache(str(tmp_path / "c")); llm = LLM({})
    c.enqueue([("n1", "nothing here", 1.0)]); process_queue(c, llm, adapter=_ad(llm))
    assert not os.path.exists(os.path.join(c.d, skr.FILE))
    r = SkRegistry(c.d); os.makedirs(c.d, exist_ok=True)
    with open(r.path, "w") as fh:
        fh.write('{"sym": "sk_a_1__i_n1", "owner": "i_n1", "note": "i_n1", "role": "intro", "kinds": ["a"]}\n{torn\n')
    assert list(r.entities()) == ["sk_a_1__i_n1"]


def test_registry_never_merges(tmp_path):
    r = SkRegistry(str(tmp_path))
    r.note("i_n1", "h1", ["(: a (Member sk_cat_1__i_n1 cat) (STV 1 1))"])
    r.note("i_n2", "h2", ["(: a (Member sk_cat_1__i_n2 cat) (STV 1 1))"])     # same kind, different notes
    assert len(r.entities()) == 2 and r.links() == []
