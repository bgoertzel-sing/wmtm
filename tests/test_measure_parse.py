"""tools/measure_parse.py and wmtm.anthropic_llm on a tiny synthetic fixture state dir (no network, no real notes)."""
import importlib.util
import io
import json
import os
import urllib.error

import pytest

from wmtm import anthropic_llm as A

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("measure_parse", os.path.join(HERE, "..", "tools", "measure_parse.py"))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

HITL = os.environ.get("WMTM_SEMPARSE_HITL", "")
needs_hitl = pytest.mark.skipif(not os.path.isdir(os.path.join(HITL, "templates", "tmpl")),
                                reason="WMTM_SEMPARSE_HITL checkout not available")

NOTES = {"i1": "Teodor bought the spindle from Yusra.", "i2": "Mira painted the fence.",
         "i3": "The kettle is on the stove."}          # synthetic
REPLY = json.dumps({"id": "s1", "instances": [
    {"t": "named-entity", "id": "n1", "name": "Teodor", "span": "Teodor"},
    {"t": "witness", "id": "x1", "class": "spindle", "definite": True, "span": "the spindle"},
    {"t": "named-entity", "id": "n2", "name": "Yusra", "span": "Yusra"},
    {"t": "acquisition", "id": "e1", "verb": "buy", "acquirer": "@n1", "object": "@x1",
     "source": "@n2", "tense": "past", "span": "Teodor bought the spindle from Yusra"}],
    "unmapped": [], "issues": []})


def make_state(tmp_path, flags=None):
    sd = tmp_path / "state"
    sd.mkdir()
    items = {k: {"id": k, "content": v} for k, v in NOTES.items()}
    items["empty"] = {"id": "empty", "content": "  "}
    (sd / "_wmtm_state.json").write_text(json.dumps({"store": {"items": items}}))
    sp = sd / "_wmtm_shadow" / "semparse_cache"
    if flags:
        (sd / "_wmtm_flags.json").write_text(json.dumps(flags))
        sp = sd / flags["semparse_dir"]
    (sp / "spk1").mkdir(parents=True)
    h1 = M.content_hash(NOTES["i1"])
    (sp / "spk1" / "parse_log.jsonl").write_text(json.dumps(
        {"hash": h1, "status": "ok", "secs": 40.0, "prompt_tokens": 1000, "completion_tokens": 100}) + "\n")
    return sd, h1


def test_content_hash_matches_parse_cache():
    from wmtm.parse_cache import content_hash
    assert M.content_hash("abc") == content_hash("abc") and len(M.content_hash("abc")) == 24


def test_weighted_and_live_bounds():
    assert M.weighted({"uncached_input": 10, "cache_write": 100, "cache_read": 1000, "output": 2}) == 245.0
    assert M.weighted({"uncached_input": None, "cache_write": 0, "cache_read": 0, "output": 0}) is None
    b = {"uncached_input": 1000, "output": 100, "cache_split_known": False}
    assert M.live_weighted(b, "uncached_input") == 1500.0 and M.live_weighted(b, "cache_write") == 1750.0


def test_load_notes_and_seeded_select(tmp_path):
    sd, h1 = make_state(tmp_path)
    notes = M.load_notes(str(sd))
    assert len(notes) == 3 and notes[h1][0] == "i1"
    a = M.select(notes, 2, 7, [])[0]
    assert a == M.select(notes, 2, 7, [])[0] and len(a) == 2
    assert M.select(notes, 30, 0, [h1, "nope"]) == ([h1], ["nope"])


def test_baseline_default_dir_and_flags_dir(tmp_path):
    from wmtm import runtime_config as rc
    sd, h1 = make_state(tmp_path)
    b = M.load_baseline(rc.resolve(str(sd))["semparse_dir"])
    assert b[h1]["log"] == "spk1" and b[h1]["output"] == 100
    sd2, _ = make_state(tmp_path / "x" if (tmp_path / "x").mkdir() is None else tmp_path, {"semparse_dir": "pc"})
    assert rc.resolve(str(sd2))["semparse_dir"].endswith("/pc")
    assert h1 in M.load_baseline(rc.resolve(str(sd2))["semparse_dir"])


def test_anthropic_llm_request_and_usage_split():
    seen = {}

    def opener(req, t):
        seen["body"] = json.loads(req.data)
        seen["hdr"] = dict(req.header_items())
        return json.dumps({"content": [{"type": "text", "text": "hi"}], "usage": {
            "input_tokens": 12, "cache_read_input_tokens": 3000, "cache_creation_input_tokens": 0,
            "output_tokens": 40}}).encode()
    llm = A.anthropic_llm(key="k-test", opener=opener)
    assert llm("SYS", "USER") == "hi"
    assert seen["body"]["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert seen["body"]["model"] == A.DEFAULT_MODEL
    assert llm.last_usage["uncached_input"] == 12 and llm.last_usage["cache_read"] == 3000
    assert llm.last_usage["prompt_tokens"] == 3012


def test_anthropic_llm_429_and_no_key(monkeypatch):
    def opener(req, t):
        raise urllib.error.HTTPError(A.URL, 429, "too many", {}, io.BytesIO(b""))
    with pytest.raises(A.RateLimited):
        A.anthropic_llm(key="k", opener=opener)("s", "u")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        A.anthropic_llm(opener=opener)("s", "u")


@needs_hitl
def test_main_mocked_end_to_end(tmp_path):
    sd, h1 = make_state(tmp_path)
    mock = tmp_path / "mock.jsonl"
    mock.write_text(json.dumps({"hash": h1, "reply": REPLY}) + "\n")
    out = tmp_path / "out"
    assert M.main(["--state-dir", str(sd), "-n", "3", "--out", str(out), "--mock-replies", str(mock)]) == 0
    s = json.loads((out / "summary.json").read_text())
    assert s["parsed"] == 3 and s["mocked"] and s["status"]["admitted"] == 1 and s["status"]["rejected"] == 2
    assert s["median"]["weighted"] == "not measured (no credential)"
    assert s["live_baseline"]["joined"] == 1
    per = (out / "per_note.jsonl").read_text()
    for t in NOTES.values():                            # no note text outside the local bad-parse file
        assert t not in per and t not in (out / "summary.json").read_text()
    assert "Mira" in (out / "bad_parses.local.jsonl").read_text()
