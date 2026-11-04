"""SemParseAdapter LLM backed by the upstream provider classes of semantic-parse.py (no duplicate client).

p2 review-1 #4: the measurement calls the provider code that ships upstream, not a WMTM copy of it.
The pinned checkout (1f1a7a6f, verified by semparse_catalog.hitl_root) still has the Anthropic placeholder,
so when its ``Anthropic`` class has no ``key`` method, our upstream PR patch
(upstream/semantic-parsing-hitl/0001-*.patch) is applied with ``git apply`` to a copy of semantic-parse.py
in a scratch dir and that copy is loaded.  The checkout itself is never modified.

``upstream_llm()`` returns llm(system, user) -> text with ``last_usage`` in the adapter's split:
uncached_input, cache_read, cache_write, output (+ prompt/completion/total).  Provider errors (HTTP 429 /
529 after upstream's own retries, a missing key) propagate as the module's ``ProviderError``; the adapter
records them in ParseResult.error.
"""
import argparse
import glob
import importlib.util
import os
import shutil
import subprocess
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATCH_GLOB = os.path.join(REPO, "upstream", "semantic-parsing-hitl", "0001-*.patch")


def _load(path: str, name: str = "semantic_parse_upstream"):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_upstream(hitl: str, workdir: str = None, need_anthropic: bool = True):
    """semantic-parse.py of the (verified) checkout ``hitl``; patched copy if Anthropic is a placeholder."""
    src = os.path.join(hitl, "semantic-parse.py")
    mod = _load(src)
    if hasattr(mod.Anthropic, "key") or not need_anthropic:
        return mod
    patches = sorted(glob.glob(PATCH_GLOB))
    if not patches:
        raise FileNotFoundError("upstream Anthropic provider patch not found: " + PATCH_GLOB)
    d = workdir or tempfile.mkdtemp(prefix="semparse-provider-")
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, "semantic-parse.py")
    shutil.copy(src, dst)
    subprocess.run(["git", "apply", patches[0]], cwd=d, check=True, capture_output=True)
    mod = _load(dst)
    if not hasattr(mod.Anthropic, "key"):
        raise RuntimeError("patched semantic-parse.py still has no Anthropic provider")
    mod.PATCHED_FROM = (src, patches[0])
    return mod


def split_usage(u: dict) -> dict:
    """Upstream usage shape (input = whole prompt, cached = cache read, cache_write) -> adapter split."""
    u = u or {}
    inp, rd, wr = (u.get("input") or 0), (u.get("cached") or 0), (u.get("cache_write") or 0)
    out = u.get("output") or 0
    return {"uncached_input": max(0, inp - rd - wr), "cache_read": rd, "cache_write": wr, "output": out,
            "prompt_tokens": inp, "completion_tokens": out, "total_tokens": inp + out}


def upstream_llm(provider: str = "anthropic", model: str = None, hitl: str = None, flags=(), workdir=None):
    """llm(system, user) through upstream PROVIDERS[provider]; ``flags`` are upstream provider CLI flags
    (e.g. ["--effort", "low"]), parsed by upstream add_provider_args so defaults match semantic-parse.py."""
    from .semparse_catalog import hitl_root
    mod = load_upstream(hitl_root(hitl), workdir)
    ap = argparse.ArgumentParser(add_help=False)
    mod.add_provider_args(ap)
    args = ap.parse_args(["--provider", provider] + list(flags))
    prov = mod.PROVIDERS[provider](args)
    m = model or prov.default_model

    def call(system: str, user: str) -> str:
        call.last_usage = None
        r = prov.complete(system, user, m)
        call.last_usage = split_usage(r.usage)
        return r.text

    call.last_usage, call.model, call.provider, call.module, call.args = None, m, provider, mod, args
    return call


GATEWAY_TOKEN_ENV = "OPENCLAW_GATEWAY_TOKEN"


def gateway_provider_class(mod):
    """answer 7: an OpenAI-compatible Chat Completions endpoint (the OpenClaw gateway, ``--base-url``) built on
    upstream's own DeepSeek provider (same OpenAI-format streaming client, ``_post_json`` retries and
    ``_read_sse``); only the URL, the key and the DeepSeek-only body fields differ."""

    class Gateway(mod.DeepSeek):
        name = "openclaw"
        default_model = "openclaw/default"
        env_keys = (GATEWAY_TOKEN_ENV,)

        def __init__(self, args, base_url: str, token_env: str = GATEWAY_TOKEN_ENV):
            super().__init__(args)
            self.url = base_url.rstrip("/") + "/chat/completions"
            self.token_env = token_env
            self.env_keys = (token_env,)

        def key(self) -> str:
            if os.environ.get(self.token_env):
                return os.environ[self.token_env]
            raise mod.ProviderError(f"set {self.token_env} (gateway bearer token)")

        def request(self, system: str, user: str, model: str):
            a = self.args
            body = {"model": model, "stream": True, "stream_options": {"include_usage": True},
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
            if getattr(a, "max_tokens", None):
                body["max_tokens"] = a.max_tokens
            if getattr(a, "temperature", None) is not None:
                body["temperature"] = a.temperature
            return self.url, {"Authorization": "Bearer <key>"}, body

        def complete(self, system: str, user: str, model: str):
            r = super().complete(system, user, model)
            u = getattr(r, "raw_usage", None) or {}
            if r.usage.get("cached") is None:          # OpenAI shape: prompt_tokens_details.cached_tokens
                r.usage["cached"] = (u.get("prompt_tokens_details") or {}).get("cached_tokens")
            if u.get("cache_creation_input_tokens") is not None:
                r.usage["cache_write"] = u["cache_creation_input_tokens"]
            return r

    return Gateway


def gateway_llm(base_url: str, model: str = None, hitl: str = None, flags=(), token_env: str = GATEWAY_TOKEN_ENV):
    """llm(system, user) through an OpenAI-compatible gateway (e.g. http://127.0.0.1:18789/v1,
    model openclaw/<agent>) using upstream's provider code; ``flags`` are upstream provider CLI flags."""
    from .semparse_catalog import hitl_root
    mod = load_upstream(hitl_root(hitl), need_anthropic=False)
    ap = argparse.ArgumentParser(add_help=False)
    mod.add_provider_args(ap)
    args = ap.parse_args(["--provider", "deepseek"] + list(flags))
    prov = gateway_provider_class(mod)(args, base_url, token_env)
    m = model or prov.default_model

    def call(system: str, user: str) -> str:
        call.last_usage = None
        r = prov.complete(system, user, m)
        call.last_usage = split_usage(r.usage)
        return r.text

    call.last_usage, call.model, call.provider, call.module, call.args = None, m, "openclaw", mod, args
    call.base_url = prov.url
    return call
