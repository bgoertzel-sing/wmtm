"""SemParseAdapter LLM backed by the upstream provider classes of semantic-parse.py (no duplicate client).

p2 review-1 #4: the measurement calls the provider code that ships upstream, not a WMTM copy of it.
The pinned checkout (1f1a7a6f, verified by semparse_catalog.hitl_root) has neither the Anthropic provider nor
a configurable-base-URL provider, so while it lacks them our upstream PR patches
(upstream/semantic-parsing-hitl/000*.patch: 0001 Anthropic, 0003 chat-completions --base-url / --api-key-env)
are applied in order with ``git apply`` to a copy of semantic-parse.py in a scratch dir and that copy is
loaded.  The checkout itself is never modified.  ``gateway_llm()`` (answer 7, the OpenClaw gateway) is
upstream's ``chat-completions`` provider; WMTM has no provider code of its own.

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
PATCH_GLOB = os.path.join(REPO, "upstream", "semantic-parsing-hitl", "0*.patch")


def _load(path: str, name: str = "semantic_parse_upstream"):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _complete(mod) -> bool:
    """The pin has the providers the patches add (Anthropic implemented, chat-completions registered)."""
    return hasattr(mod.Anthropic, "key") and "chat-completions" in getattr(mod, "PROVIDERS", {})


def load_upstream(hitl: str, workdir: str = None):
    """semantic-parse.py of the (verified) checkout ``hitl``; while the pin lacks our upstream PR, a scratch copy
    with upstream/semantic-parsing-hitl/000*.patch applied in order (only semantic-parse.py hunks)."""
    src = os.path.join(hitl, "semantic-parse.py")
    mod = _load(src)
    if _complete(mod):
        return mod
    patches = sorted(glob.glob(PATCH_GLOB))
    if not patches:
        raise FileNotFoundError("upstream provider patches not found: " + PATCH_GLOB)
    d = workdir or tempfile.mkdtemp(prefix="semparse-provider-")
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, "semantic-parse.py")
    shutil.copy(src, dst)
    for patch in patches:
        subprocess.run(["git", "apply", "--include=semantic-parse.py", patch], cwd=d, check=True, capture_output=True)
    mod = _load(dst)
    if not _complete(mod):
        raise RuntimeError("patched semantic-parse.py still lacks the Anthropic / chat-completions providers")
    mod.PATCHED_FROM = (src, tuple(patches))
    return mod


def split_usage(u: dict) -> dict:
    """Upstream usage shape (input = whole prompt, cached = cache read, cache_write) -> adapter split.

    review-4 #1: a field the provider did not report stays None (unmeasured), never 0; uncached input is only
    known when the prompt and both cache fields are known, so weighted usage is None unless every part is."""
    u = u or {}
    inp, rd, wr, out = (u.get(k) for k in ("input", "cached", "cache_write", "output"))
    unc = None if None in (inp, rd, wr) else max(0, inp - rd - wr)
    return {"uncached_input": unc, "cache_read": rd, "cache_write": wr, "output": out,
            "prompt_tokens": inp, "completion_tokens": out,
            "total_tokens": None if None in (inp, out) else inp + out}


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


def gateway_llm(base_url: str, model: str = None, hitl: str = None, flags=(), token_env: str = GATEWAY_TOKEN_ENV,
                workdir=None):
    """answer 7: llm(system, user) through an OpenAI-compatible gateway (e.g. http://127.0.0.1:18789/v1, model
    openclaw/<agent>) using upstream's own ``chat-completions`` provider (our upstream patch 0003, --base-url /
    --api-key-env); no WMTM-local provider code."""
    call = upstream_llm("chat-completions", model=model, hitl=hitl, workdir=workdir,
                        flags=["--base-url", base_url, "--api-key-env", token_env] + list(flags))
    call.base_url = base_url
    return call
