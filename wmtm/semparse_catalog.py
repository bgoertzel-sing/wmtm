"""wmtm/semparse_catalog.py - catalog mode for semantic-parsing-hitl >= 1f1a7a6f.

Upstream replaced the legacy prompt.txt (the model wrote MeTTa directly) with a template
catalog: the system prompt is templates/generated/PROMPT_CATALOG.txt, the model answers with
JSON ``{"id", "instances": [...], "unmapped": [...]}`` and upstream's own ``tmpl.validate``
emits the MeTTa statements and declarations.  This module is the thin bridge:

  reply text -> extract_json -> tmpl.validate.inspect(reply, catalog, text=TEXT)
             -> (status, statements, declarations, findings)

The statements then go through the adapter's existing structural check / normalise /
prefix / PeTTa load path, so nothing downstream changes.  The hitl checkout is located by
``WMTM_SEMPARSE_HITL`` (or the ``root`` argument); it is imported, never copied here.
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Optional

PROMPT_REL = os.path.join("templates", "generated", "PROMPT_CATALOG.txt")
_CACHE: dict = {}


def hitl_root(root: Optional[str] = None) -> str:
    r = root or os.environ.get("WMTM_SEMPARSE_HITL", "")
    if not r or not os.path.isdir(os.path.join(r, "templates", "tmpl")):
        raise FileNotFoundError(f"semantic-parsing-hitl checkout not found (WMTM_SEMPARSE_HITL={r!r})")
    return os.path.abspath(r)


def prompt_path(root: Optional[str] = None) -> str:
    return os.path.join(hitl_root(root), PROMPT_REL)


def _modules(root: str):
    """Import upstream tmpl.{validate,catalog} from the checkout once; cache the loaded catalog."""
    if root not in _CACHE:
        tdir = os.path.join(root, "templates")
        if tdir not in sys.path:
            sys.path.insert(0, tdir)
        from tmpl import catalog as CAT, validate as V      # noqa: E402  (upstream, MIT)
        _CACHE[root] = (V, CAT.load())
    return _CACHE[root]


def extract_json(text: str):
    """Same rule as upstream semantic-parse.py extract_json: strip fences / stray prose."""
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.S)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        s, e = t.find("{"), t.rfind("}")
        if s >= 0 and e > s:
            return json.loads(t[s:e + 1])
        raise


def item_message(item_id: str, text: str) -> str:
    """Same user turn as upstream semantic-parse.py item_message (keeps the cached catalog prefix intact)."""
    return f"Item id: {item_id}\nTEXT: {text}\n\nWrite the JSON object for this item."


def looks_like_catalog_reply(text: str) -> bool:
    t = (text or "").lstrip()
    return t.startswith("{") or t.startswith("```json") or '"instances"' in t[:400]


def reply_to_statements(reply_text: str, text: str, root: Optional[str] = None,
                        reference_time=None) -> dict:
    """Return {"status", "statements", "declarations", "findings", "fired"}; never raises on a bad reply."""
    out = {"status": "malformed", "statements": [], "declarations": [], "findings": [], "fired": {}}
    try:
        reply = extract_json(reply_text)
    except (json.JSONDecodeError, ValueError) as e:
        out["findings"].append({"kind": "json", "detail": f"reply is not JSON: {str(e)[:120]}"})
        return out
    if not isinstance(reply, dict):
        out["findings"].append({"kind": "json", "detail": "reply is not a JSON object"})
        return out
    V, catalog = _modules(hitl_root(root))
    try:
        res = V.inspect(reply, catalog, reference_time=reference_time, text=text)
    except Exception as e:                                  # noqa: BLE001  upstream bug != our crash
        out["findings"].append({"kind": "upstream", "detail": f"{type(e).__name__}: {str(e)[:160]}"})
        return out
    for k in out:
        if k in res:
            out[k] = res[k]
    return out
