"""Anthropic Messages API as a SemParseAdapter LLM (P2 measurement provider).

Mirrors the upstream provider in upstream/semantic-parsing-hitl/0001-*.patch: the system prompt is one
text block ending in a ``cache_control`` breakpoint (written once, read on later calls within ~5 min);
the item is plain user input.  ``call.last_usage`` carries Anthropic's own split:
uncached_input, cache_read, cache_write, output (plus the OpenAI-shaped totals the parse log uses).
HTTP 429 / 529 and usage-limit errors are raised as ``RateLimited`` so callers can count them.
"""
import json
import os
import urllib.error
import urllib.request

DEFAULT_MODEL = "claude-sonnet-5-5"          # the order's default (upstream Anthropic.default_model)
URL = "https://api.anthropic.com/v1/messages"
VERSION = "2023-06-01"


class RateLimited(RuntimeError):
    """429 / 529 / usage-limit reply from the provider."""


def split_usage(u: dict) -> dict:
    u = u or {}
    unc, rd, wr = (u.get("input_tokens") or 0), (u.get("cache_read_input_tokens") or 0), \
        (u.get("cache_creation_input_tokens") or 0)
    out = u.get("output_tokens") or 0
    return {"uncached_input": unc, "cache_read": rd, "cache_write": wr, "output": out,
            "prompt_tokens": unc + rd + wr, "completion_tokens": out, "total_tokens": unc + rd + wr + out}


def anthropic_llm(model=None, key=None, max_tokens=8192, timeout=300.0, cache=True, opener=None):
    """Return llm(system, user) -> text.  `opener(req, timeout)` is injectable for tests (no network)."""
    model = model or os.environ.get("WMTM_ANTHROPIC_MODEL") or DEFAULT_MODEL
    opener = opener or (lambda req, t: urllib.request.urlopen(req, timeout=t).read())

    def call(system: str, user: str) -> str:
        k = key or os.environ.get("ANTHROPIC_API_KEY")
        if not k:
            raise RuntimeError("no Anthropic credential (set ANTHROPIC_API_KEY)")
        block = {"type": "text", "text": system}
        if cache:
            block["cache_control"] = {"type": "ephemeral"}
        body = {"model": model, "max_tokens": max_tokens, "system": [block],
                "messages": [{"role": "user", "content": user}]}
        req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST", headers={
            "content-type": "application/json", "x-api-key": k, "anthropic-version": VERSION})
        call.last_usage = None
        try:
            raw = json.loads(opener(req, timeout))
        except urllib.error.HTTPError as e:
            if e.code in (429, 529):
                raise RateLimited("http %d" % e.code) from None
            raise RuntimeError("http %d" % e.code) from None
        if (raw.get("type") == "error" and "rate_limit" in str(raw.get("error", {}).get("type", ""))):
            raise RateLimited(str(raw["error"].get("type")))
        call.last_usage = split_usage(raw.get("usage"))
        return "".join(b.get("text", "") for b in raw.get("content") or [] if b.get("type") == "text")

    call.last_usage = None
    call.model = model
    return call
