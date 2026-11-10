"""t-2026-11-10-wmtm-normaliser, order Do 4 / acceptance 3: evaluations read only frozen parses keyed by
(note hash, parser pin, prompt sha) and provably never re-parse."""
import pytest
from types import SimpleNamespace as NS
from wmtm import frozen_parse as F, parse_cache as PC


def _it(i, text):
    return NS(id=i, content=text)


def test_key_needs_all_three_parts():
    assert F.key("h", "533c2274beac", "1585e873fc3151b8") == "h|533c2274beac|1585e873fc3151b8"
    for bad in (("", "p", "s"), ("h", "", "s"), ("h", "p", "")):
        with pytest.raises(F.FrozenParseError):
            F.key(*bad)


def test_lookup_keyed_by_hash_pin_and_prompt(tmp_path):
    st = F.FrozenStore(str(tmp_path))
    h = F.content_hash("note one")
    st.put(h, "pinA", "shaA", "n1", "ok", ["(: f (Member a b) (STV 1 1))"])
    assert st.lookup([_it("n1", "note one")], "pinA", "shaA") == {"n1": ["(: f (Member a b) (STV 1 1))"]}
    # negative controls: a different pin, prompt or note text is a miss, never a fallback
    for pin, sha, text in (("pinB", "shaA", "note one"), ("pinA", "shaB", "note one"), ("pinA", "shaA", "note 2")):
        with pytest.raises(F.FrozenParseError):
            st.lookup([_it("n1", text)], pin, sha)
        assert st.lookup([_it("n1", text)], pin, sha, strict=False) == {}


def test_existing_key_never_overwritten(tmp_path):
    st = F.FrozenStore(str(tmp_path))
    assert st.put("h", "p", "s", "n1", "ok", ["A"]) is True
    assert st.put("h", "p", "s", "n1", "ok", ["B"]) is False
    assert st.entries()[F.key("h", "p", "s")]["atoms"] == ["A"]


def test_manifest_has_no_atoms_text(tmp_path):
    st = F.FrozenStore(str(tmp_path))
    st.put("h", "p", "s", "n1", "ok", ['(: l (Name sk_a "Secret") (STV 1 1))'])
    import json
    assert "Secret" not in json.dumps(st.manifest()) and st.manifest()["file_sha256"]


class _Boom:
    def __call__(self, *a, **k):
        raise AssertionError("LLM must not be called inside an evaluation")


@pytest.mark.parametrize("fn", ["process_queue", "process_queue_ctx", "process_queue_spk"])
def test_no_reparse_inside_evaluation(fn, tmp_path):
    with F.evaluation():
        with pytest.raises(F.FrozenParseError):
            f = getattr(PC, fn)
            import inspect
            req = [n for n, q in inspect.signature(f).parameters.items()
                   if q.default is inspect.Parameter.empty and q.kind in (q.POSITIONAL_ONLY, q.POSITIONAL_OR_KEYWORD)]
            f(**{n: (_Boom() if n == "llm" else None) for n in req})


def test_no_reparse_when_env_set(monkeypatch):
    monkeypatch.setenv(F.ENV, "1")
    with pytest.raises(F.FrozenParseError):
        PC.process_queue(None, _Boom(), adapter=object())


def test_put_refused_inside_evaluation(tmp_path):
    with F.evaluation():
        with pytest.raises(F.FrozenParseError):
            F.FrozenStore(str(tmp_path)).put("h", "p", "s", "n1", "ok", [])


def test_guard_off_outside_evaluation(monkeypatch):
    monkeypatch.delenv(F.ENV, raising=False)
    assert not F.in_evaluation()
    F.refuse_if_evaluating("x")      # negative control: no error outside an evaluation


def test_shadow_reads_only_frozen_store_when_env_set(tmp_path, monkeypatch):
    from wmtm import pc_shadow as P
    st = F.FrozenStore(str(tmp_path / "fz"))
    st.put(F.content_hash("note one"), "pinA", "shaA", "n1", "ok", ["(: f (Member a b) (STV 1 1))"])
    live = tmp_path / "live"; live.mkdir()
    import json
    (live / "cache.jsonl").write_text(json.dumps({"hash": F.content_hash("note one"), "item_id": "n1", "status": "ok",
                                                  "atoms": ["(: g (Member live x) (STV 1 1))"]}) + "\n")
    items = [_it("n1", "note one")]
    monkeypatch.delenv(F.STORE_ENV, raising=False)
    assert P._cache_lookup(items, str(live)) == {"n1": ["(: g (Member live x) (STV 1 1))"]}   # control: live cache
    monkeypatch.setenv(F.STORE_ENV, "%s|pinA|shaA" % (tmp_path / "fz"))
    assert P._cache_lookup(items, str(live)) == {"n1": ["(: f (Member a b) (STV 1 1))"]}       # frozen wins, no live read
    assert F.in_evaluation()
    with pytest.raises(F.FrozenParseError):
        PC.process_queue(None, _Boom(), adapter=object())
    monkeypatch.setenv(F.STORE_ENV, "%s|pinB|shaA" % (tmp_path / "fz"))
    assert P._cache_lookup(items, str(live)) == {}                                              # other pin: miss, no fallback
