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


def load_upstream(hitl: str, workdir: str = None):
    """semantic-parse.py of the (verified) checkout ``hitl``; patched copy if Anthropic is a placeholder."""
    src = os.path.join(hitl, "semantic-parse.py")
    mod = _load(src)
    if hasattr(mod.Anthropic, "key"):
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
