"""tools/measure_parse.py and wmtm.semparse_provider (upstream provider) on a tiny synthetic fixture state dir (no network, no real notes)."""
import importlib.util
import json
import os

import pytest

from wmtm import semparse_provider as P

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
    a = M.select(notes, 2, 7, None)[0]
    assert a == M.select(notes, 2, 7, None)[0] and len(a) == 2
    assert M.select(notes, 30, 0, [h1, "nope"]) == ([h1], ["nope"])


def test_baseline_default_dir_and_flags_dir(tmp_path):
    from wmtm import runtime_config as rc
    sd, h1 = make_state(tmp_path)
    b = M.load_baseline(rc.resolve(str(sd))["semparse_dir"])
    assert b[h1]["log"] == "spk1" and b[h1]["output"] == 100
    sd2, _ = make_state(tmp_path / "x" if (tmp_path / "x").mkdir() is None else tmp_path, {"semparse_dir": "pc"})
    assert rc.resolve(str(sd2))["semparse_dir"].endswith("/pc")
    assert h1 in M.load_baseline(rc.resolve(str(sd2))["semparse_dir"])


@needs_hitl
def test_upstream_provider_request_and_usage_split(tmp_path, monkeypatch):
    """review-1 #4: the measurement goes through upstream semantic-parse.py's Anthropic class."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k-test")
    src = os.path.join(HITL, "semantic-parse.py")
    before = open(src, "rb").read()
    llm = P.upstream_llm("anthropic", hitl=HITL, workdir=str(tmp_path / "prov"))
    seen = {}

    def fake(url, headers, body, timeout, **kw):
        seen.update(url=url, headers=headers, body=body, kw=kw)
        return {"content": [{"type": "text", "text": "hi"}], "stop_reason": "end_turn", "usage": {
            "input_tokens": 12, "cache_read_input_tokens": 3000, "cache_creation_input_tokens": 0,
            "output_tokens": 40}}
    monkeypatch.setattr(llm.module, "_post_json", fake)
    assert llm("SYS", "USER") == "hi"
    assert hasattr(llm.module.Anthropic, "key") and os.path.dirname(llm.module.__file__) == str(tmp_path / "prov")
    assert seen["body"]["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert seen["body"]["model"] == llm.model == llm.module.Anthropic.default_model
    assert seen["headers"]["x-api-key"] == "k-test" and 429 in seen["kw"]["long_codes"]
    assert llm.last_usage["uncached_input"] == 12 and llm.last_usage["cache_read"] == 3000
    assert llm.last_usage["prompt_tokens"] == 3012 and llm.last_usage["output"] == 40
    assert open(src, "rb").read() == before                      # the pinned checkout is never modified


@needs_hitl
def test_upstream_provider_errors_propagate(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    llm = P.upstream_llm("anthropic", hitl=HITL, workdir=str(tmp_path / "prov"))
    with pytest.raises(llm.module.ProviderError):
        llm("s", "u")                                   # no key
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")

    def boom(*a, **k):
        raise llm.module.ProviderError("HTTP 429: rate_limit_error")
    monkeypatch.setattr(llm.module, "_post_json", boom)
    with pytest.raises(llm.module.ProviderError, match="429"):
        llm("s", "u")
    assert any(m in "http 429: rate_limit_error" for m in M.LIMIT_MARKERS)


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


class _FakeGateway:
    """Local OpenAI-compatible Chat Completions SSE server (stands in for the OpenClaw gateway; no network)."""

    def __init__(self, reply_text, usage):
        import http.server
        import threading
        self.seen = []
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                outer.seen.append({"path": self.path, "auth": self.headers.get("Authorization"),
                                   "body": json.loads(self.rfile.read(n))})
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                chunks = [{"model": "openclaw/protocosmo2", "choices": [{"delta": {"role": "assistant"}}]},
                          {"choices": [{"delta": {"content": reply_text}}]},
                          {"choices": [{"delta": {}, "finish_reason": "stop"}]},
                          {"choices": [], "usage": usage}][: 4 if usage is not None else 3]
                for c in chunks:
                    self.wfile.write(b"data: " + json.dumps(c).encode() + b"\n\n")
                self.wfile.write(b"data: [DONE]\n\n")

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base_url = f"http://127.0.0.1:{self.srv.server_address[1]}/v1"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()


GW_USAGE = {"prompt_tokens": 3100, "completion_tokens": 50, "total_tokens": 3150,
            "prompt_tokens_details": {"cached_tokens": 3000}, "cache_creation_input_tokens": 0}


@needs_hitl
def test_gateway_provider_request_and_usage(tmp_path, monkeypatch):
    """review-3 / answer 7: OpenAI-compatible gateway at --base-url, agent target model, bearer token."""
    monkeypatch.setenv("OPENCLAW_GATEWAY_TOKEN", "gw-test")
    gw = _FakeGateway("hello", GW_USAGE)
    try:
        llm = P.gateway_llm(gw.base_url, model="openclaw/protocosmo2", hitl=HITL)
        assert llm("SYS", "USER") == "hello"
    finally:
        gw.close()
    r = gw.seen[0]
    assert r["path"] == "/v1/chat/completions" and r["auth"] == "Bearer gw-test"
    assert r["body"]["model"] == "openclaw/protocosmo2" and r["body"]["stream"] is True
    assert r["body"]["stream_options"] == {"include_usage": True}
    assert [m["role"] for m in r["body"]["messages"]] == ["system", "user"]
    assert "thinking" not in r["body"] and "response_format" not in r["body"]   # DeepSeek-only fields dropped
    u = llm.last_usage
    assert u["cache_read"] == 3000 and u["uncached_input"] == 100 and u["output"] == 50
    assert llm.provider == "chat-completions"                      # upstream provider (patch 0003), not WMTM code
    assert llm.module.PROVIDERS["chat-completions"].__module__ == llm.module.__name__
    assert any(p.endswith(".patch") and "/0003-" in p for p in llm.module.PATCHED_FROM[1])


@needs_hitl
def test_gateway_provider_no_token(monkeypatch):
    monkeypatch.delenv("OPENCLAW_GATEWAY_TOKEN", raising=False)
    llm = P.gateway_llm("http://127.0.0.1:9/v1", model="openclaw/x", hitl=HITL)
    with pytest.raises(llm.module.ProviderError, match="OPENCLAW_GATEWAY_TOKEN"):
        llm("s", "u")


@needs_hitl
def test_main_gateway_end_to_end(tmp_path, monkeypatch):
    """measure_parse --provider openclaw --base-url ... --model openclaw/protocosmo2 runs (exit 0) and measures."""
    monkeypatch.setenv("OPENCLAW_GATEWAY_TOKEN", "gw-test")
    sd, h1 = make_state(tmp_path)
    gw = _FakeGateway(REPLY, GW_USAGE)
    out = tmp_path / "out"
    try:
        rc_ = M.main(["--state-dir", str(sd), "-n", "1", "--hashes", h1, "--out", str(out), "--per-hour", "0",
                      "--provider", "openclaw", "--base-url", gw.base_url, "--model", "openclaw/protocosmo2"])
    finally:
        gw.close()
    assert rc_ == 0
    s = json.loads((out / "summary.json").read_text())
    assert s["model"] == "openclaw/protocosmo2" and not s["mocked"]
    assert s["status"]["admitted"] == 1 and s["errors"] == 0
    row = json.loads((out / "per_note.jsonl").read_text().splitlines()[0])
    assert row["cache_read"] == 3000 and row["output"] == 50 and row["weighted"] is not None
    assert row["latency_s"] is not None and gw.seen[0]["body"]["model"] == "openclaw/protocosmo2"


@needs_hitl
@pytest.mark.parametrize("usage", [{"prompt_tokens": 3100, "completion_tokens": 50}, None])
def test_gateway_missing_usage_is_unmeasured(usage, monkeypatch):
    """review-4 #1: fields the server does not report stay None (never 0); weighted usage is then None."""
    monkeypatch.setenv("OPENCLAW_GATEWAY_TOKEN", "gw-test")
    gw = _FakeGateway("hello", usage)
    try:
        llm = P.gateway_llm(gw.base_url, model="openclaw/x", hitl=HITL)
        assert llm("SYS", "USER") == "hello"
    finally:
        gw.close()
    u = llm.last_usage
    assert u["cache_read"] is None and u["cache_write"] is None and u["uncached_input"] is None
    if usage is None:
        assert u["output"] is None and u["prompt_tokens"] is None and u["total_tokens"] is None
    else:
        assert u["output"] == 50 and u["prompt_tokens"] == 3100
    assert M.weighted({k: u.get(k) for k in M.WEIGHTS}) is None


def test_split_usage_never_fills_zero():
    assert P.split_usage({}) == {k: None for k in ("uncached_input", "cache_read", "cache_write", "output",
                                                    "prompt_tokens", "completion_tokens", "total_tokens")}
    full = P.split_usage({"input": 100, "cached": 60, "cache_write": 10, "output": 5})
    assert (full["uncached_input"], full["total_tokens"]) == (30, 105)


def _row(w=None, live=100.0):
    full = w is not None
    return {"status": "admitted", "accepted": 1, "rejected": 0, "error_kind": None,
            "uncached_input": 10 if full else None, "cache_write": 0 if full else None,
            "cache_read": 0 if full else None, "output": 0 if full else None, "weighted": w,
            "latency_s": 5.0, "live_log": "spk1", "live_secs": 40.0,
            "live_weighted_lo": live, "live_weighted_hi": live}


class _A:
    seed, hashes, per_hour = 0, "", 20.0


def test_summary_partial_usage_gives_no_median_ratio_or_verdict():
    """review-5 #1 probe: 1 note with full usage + 29 unknown -> no median, no ratio, usage_ok None."""
    rows = [_row(10.0)] + [_row(None) for _ in range(29)]
    s = M.summarize(rows, "m", False, "d", 30, [], 0, _A())
    assert s["median"]["weighted"] is None and s["median"]["uncached_input"] is None
    assert s["measured_rows"]["weighted"] == 1 and s["usage_complete"] is False
    assert s["ratio_new_over_live"]["vs_lo"] is None and s["ratio_new_over_live"]["vs_hi"] is None
    assert s["budget"]["usage_ok"] is None
    assert s["median"]["latency_s"] == 5.0 and s["budget"]["latency_ok"] is True


def test_summary_complete_usage_pairs_with_live():
    rows = [_row(10.0, 100.0), _row(30.0, 10.0), _row(20.0, None)]   # 3rd note has no live baseline
    s = M.summarize(rows, "m", False, "d", 3, [], 0, _A())
    assert s["usage_complete"] and s["median"]["weighted"] == 20.0
    assert s["ratio_new_over_live"]["paired_rows_hi"] == 2
    assert s["ratio_new_over_live"]["vs_hi"] == round(20.0 / 55.0, 3) and s["budget"]["usage_ok"] is True


@needs_hitl
def test_main_skips_long_notes_never_truncates(tmp_path):
    """review-5 #2 probe: a 2,160-char note is skipped and reported (default parse_max_chars), not measured
    as a prefix; the adapter records truncation, so a cut item is detectable."""
    sd, h1 = make_state(tmp_path)
    st = json.loads((sd / "_wmtm_state.json").read_text())
    long_txt = ("Mira painted the fence. " * 90)[:2160]
    st["store"]["items"]["long"] = {"id": "long", "content": long_txt}
    (sd / "_wmtm_state.json").write_text(json.dumps(st))
    hl = M.content_hash(long_txt)
    mock = tmp_path / "mock.jsonl"
    mock.write_text(json.dumps({"hash": h1, "reply": REPLY}) + "\n")
    out = tmp_path / "out"
    assert M.main(["--state-dir", str(sd), "--hashes", f"{h1},{hl}", "--out", str(out),
                   "--mock-replies", str(mock)]) == 0
    s = json.loads((out / "summary.json").read_text())
    assert s["max_chars"] == 1500 and s["notes_over_max_chars_in_state"] == 1
    assert s["hashes_skipped_long"] == [hl] and s["parsed"] == 1
    per = [json.loads(x) for x in (out / "per_note.jsonl").read_text().splitlines()]
    assert [r["hash"] for r in per] == [h1] and per[0]["chars"] == len(NOTES["i1"])
    out2 = tmp_path / "out2"                            # random sample never picks the long note either
    assert M.main(["--state-dir", str(sd), "-n", "30", "--out", str(out2), "--mock-replies", str(mock)]) == 0
    assert hl not in (out2 / "per_note.jsonl").read_text()
    from wmtm import semparse_adapter as sp
    ad = sp.SemParseAdapter(lambda s_, u: "", system="S", max_chars=5)
    assert ad.parse_item("x", {"text": "abcdefgh"}).truncated_chars == 3
    assert ad.parse_item("y", {"text": "abc"}).truncated_chars == 0


@needs_hitl
def test_explicit_hashes_all_skipped_stay_empty(tmp_path):
    """review-6 probe: only the long note's hash requested -> nothing parsed; never a random substitute."""
    sd, h1 = make_state(tmp_path)
    st = json.loads((sd / "_wmtm_state.json").read_text())
    long_txt = ("Mira painted the fence. " * 90)[:2160]
    st["store"]["items"]["long"] = {"id": "long", "content": long_txt}
    (sd / "_wmtm_state.json").write_text(json.dumps(st))
    hl = M.content_hash(long_txt)
    mock = tmp_path / "mock.jsonl"
    mock.write_text(json.dumps({"hash": h1, "reply": REPLY}) + "\n")
    out = tmp_path / "out"
    assert M.main(["--state-dir", str(sd), "--hashes", hl, "--out", str(out), "--mock-replies", str(mock)]) == 0
    s = json.loads((out / "summary.json").read_text())
    assert s["hashes_given"] is True and s["hashes_skipped_long"] == [hl] and s["parsed"] == 0
    assert (out / "per_note.jsonl").read_text() == ""
    assert M.select({h1: ("i1", "x")}, 30, 0, []) == ([], [])          # explicit empty list never samples
    assert M.select({h1: ("i1", "x")}, 30, 0, None) == ([h1], [])


@needs_hitl
def test_feed_llm_is_upstream_provider(tmp_path, monkeypatch):
    """review-7: the production feed's llm (parse_cache.gateway_llm_usage) is upstream's chat-completions provider,
    the same client measure_parse uses; parse_cache has no HTTP client of its own."""
    from wmtm import parse_cache as PC
    import inspect
    assert "urllib" not in inspect.getsource(PC)
    for k in ("BASE_URL", "LLM_MODEL", "AI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    gw = _FakeGateway("hello", GW_USAGE)
    envf = tmp_path / "llm.env"
    envf.write_text(f"BASE_URL={gw.base_url}\nLLM_MODEL=openclaw/protocosmo2\nAI_API_KEY=fk\n")
    try:
        llm = PC.gateway_llm_usage(env_file=str(envf), hitl=HITL, workdir=str(tmp_path / "prov"))
        assert llm("SYS", "USER") == "hello"
    finally:
        gw.close()
    assert llm.provider == "chat-completions" and llm.module.PROVIDERS["chat-completions"].__module__ == llm.module.__name__
    r = gw.seen[0]
    assert r["auth"] == "Bearer fk" and r["body"]["model"] == "openclaw/protocosmo2" and r["body"]["temperature"] == 0
    assert llm.last_usage["prompt_tokens"] == 3100 and llm.last_usage["total_tokens"] == 3150


@needs_hitl
def test_feed_llm_without_base_url_is_llm_error(monkeypatch):
    from wmtm import parse_cache as PC
    for k in ("BASE_URL", "WMTM_LLM_ENV_FILE"):
        monkeypatch.delenv(k, raising=False)
    llm = PC.gateway_llm_usage(hitl=HITL)
    with pytest.raises(RuntimeError, match="BASE_URL"):
        llm("s", "u")
    assert llm.last_usage is None


# OpenClaw gateway shape (probe 2026-11-05): no cache_creation_input_tokens; total_tokens carries cache-write.
GW_OPENCLAW_USAGE = {"prompt_tokens": 2132, "completion_tokens": 9, "total_tokens": 3488,
                     "prompt_tokens_details": {"cached_tokens": 2128}}


@needs_hitl
def test_gateway_cache_write_from_total(monkeypatch):
    """cache_write = total - prompt - completion when the gateway omits it (toOpenAiChatCompletionsUsage)."""
    monkeypatch.setenv("OPENCLAW_GATEWAY_TOKEN", "gw-test")
    gw = _FakeGateway("hello", GW_OPENCLAW_USAGE)
    try:
        llm = P.gateway_llm(gw.base_url, model="openclaw/x", hitl=HITL)
        assert llm("SYS", "USER") == "hello"
    finally:
        gw.close()
    u = llm.last_usage
    assert (u["cache_read"], u["cache_write"], u["uncached_input"], u["output"]) == (2128, 1347, 4, 9)
    assert u["cache_write_source"] == "gateway_total_minus_prompt_completion"
    assert u["prompt_tokens"] == 2132 + 1347 and u["total_tokens"] == 3488
    assert M.weighted({k: u.get(k) for k in M.WEIGHTS}) is not None


def test_gateway_usage_rules():
    split = P.split_usage({"input": 100, "cached": 60, "cache_write": None, "output": 5})
    assert P.gateway_usage(split, {"total_tokens": 125})["cache_write"] == 20
    assert P.gateway_usage(split, {"total_tokens": 125})["uncached_input"] == 40
    neg = P.gateway_usage(split, {"total_tokens": 90})                  # gap < 0: stays unknown
    assert neg["cache_write"] is None and neg["uncached_input"] is None
    assert P.gateway_usage(split, {})["cache_write"] is None            # no total: stays unknown
    rep = P.gateway_usage(P.split_usage({"input": 100, "cached": 60, "cache_write": 10, "output": 5}),
                          {"total_tokens": 999})
    assert rep["cache_write"] == 10 and rep["cache_write_source"] == "reported"
    assert P.gateway_usage(None, {"total_tokens": 1}) is None
