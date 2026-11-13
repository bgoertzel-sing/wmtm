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


PIN = "f44d7b740aed240c834165672b6a862998ee4a12"          # default upstream commit (P4 re-pin, Man Hin latest 2026-11-05)
# Upstream commits this bridge accepts -> sha256 of their templates/generated/PROMPT_CATALOG.txt.
# f44d7b74 (2026-11-05, Man Hin latest) is the default since P4 rev3; 1f1a7a6f stays accepted for rollback.
ALLOWED_PINS = {
    PIN: "645bff3f5c3a0670d98a463d60d18e178d899c08c58f17ea4b3ff5a53b1d25b6",
    "1f1a7a6fc42ffb8911afb7d2e95259fdfe8a0aef": "e4c4a76c7666d70f6d019fd7fea9391d91b01528f8f89132ae05d842fdd8207e",   # previous default, rollback only
    "533c2274beac05439b08fa4dccd6b391fa38139e": "1585e873fc3151b887e5bdf412d7f2bd32dbd20447d8f6fc43503af246682b5c",   # Man Hin HEAD 2026-11-09, live-path replay v2 re-parse (opt-in via WMTM_SEMPARSE_HITL; default PIN unchanged)
    "24e37182e64a20981d423ed1d851da6de5e3b3e8": "257425b2c1593569789317f0f007f57f21f856df868b382adc0880c1c3414809",   # Man Hin 2026-11-12 (sentence-by-sentence fix), master-adopt-v2 re-parse (opt-in via WMTM_SEMPARSE_HITL; default PIN unchanged)
}
LICENSE_SHA256 = "586023696f36ad863849d2b96648022c589acdd12b27c7b15e51356343077d4c"  # MIT, (c) 2026 leungmanhin


class HitlPinError(RuntimeError):
    """The checkout is not semantic-parsing-hitl @PIN with its MIT LICENSE: refuse to import it."""


def checkout_commit(root: str) -> Optional[str]:
    """Commit of a hitl checkout: VERSION ``commit=`` (fetch_semparse_hitl.sh) or the git HEAD (a clone)."""
    v = os.path.join(root, "VERSION")
    if os.path.isfile(v):
        for line in open(v, encoding="utf-8"):
            if line.startswith("commit="):
                return line.split("=", 1)[1].strip()
    head = os.path.join(root, ".git", "HEAD")
    if os.path.isfile(head):
        ref = open(head, encoding="utf-8").read().strip()
        if not ref.startswith("ref:"):
            return ref
        rp = os.path.join(root, ".git", ref[4:].strip())
        if os.path.isfile(rp):
            return open(rp, encoding="utf-8").read().strip()
        pr = os.path.join(root, ".git", "packed-refs")
        if os.path.isfile(pr):
            for line in open(pr, encoding="utf-8"):
                parts = line.split()
                if len(parts) == 2 and parts[1] == ref[4:].strip():
                    return parts[0]
    return None


def verify_checkout(root: str) -> str:
    """Raise HitlPinError unless ``root`` is hitl at one of ALLOWED_PINS with the MIT LICENSE (sha256 checked); return root."""
    import hashlib
    got = checkout_commit(root)
    if got not in ALLOWED_PINS:
        need = ", ".join(c[:8] for c in ALLOWED_PINS)
        raise HitlPinError(f"semantic-parsing-hitl checkout {root!r} is at {got!r}, need one of {need}")
    lic = os.path.join(root, "LICENSE")
    if not os.path.isfile(lic):
        raise HitlPinError(f"semantic-parsing-hitl checkout {root!r} has no LICENSE")
    with open(lic, "rb") as fh:
        if hashlib.sha256(fh.read()).hexdigest() != LICENSE_SHA256:
            raise HitlPinError(f"semantic-parsing-hitl LICENSE in {root!r} is not the MIT licence of {got[:8]}")
    return root


def hitl_root(root: Optional[str] = None) -> str:
    """The hitl checkout: ``root``, else WMTM_SEMPARSE_HITL, else runtime_config ``semparse_hitl`` (vendored
    <vendor>/semparse-hitl-1f1a7a6f).  Must contain templates/tmpl and pass verify_checkout."""
    r = root or os.environ.get("WMTM_SEMPARSE_HITL", "")
    if not r:
        try:
            from .runtime_config import resolve
            r = resolve().get("semparse_hitl") or ""
        except Exception:                                   # noqa: BLE001
            r = ""
    if not r or not os.path.isdir(os.path.join(r, "templates", "tmpl")):
        raise FileNotFoundError(f"semantic-parsing-hitl checkout not found (WMTM_SEMPARSE_HITL={r!r})")
    return verify_checkout(os.path.abspath(r))


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


_INST_RE = re.compile(r"^instance (\d+) \(")


def _bad_instances(findings, insts) -> set:
    """Indices of instances named by emission problems ("instance <i> (t): ..." or "<t> <id>: ...")."""
    ids = {str(r.get("id")): i for i, r in enumerate(insts) if isinstance(r, dict) and r.get("id") is not None}
    bad = set()
    for f in findings:
        if f.get("kind") != "instance":
            continue
        d = str(f.get("detail"))
        m = _INST_RE.match(d)
        if m and int(m.group(1)) < len(insts):
            bad.add(int(m.group(1)))
            continue
        head = d.split(":", 1)[0].split()
        if len(head) >= 2 and head[1] in ids:
            bad.add(ids[head[1]])
        for tok in re.findall(r"@?([A-Za-z_][\w-]*)", d):    # "references unknown instance x" etc.
            if tok in ids and ("reference" in d or "names" in d) and not m:
                bad.add(ids[tok])
    return bad


def reply_to_statements(reply_text: str, text: str, root: Optional[str] = None,
                        reference_time=None) -> dict:
    """Return {"status", "statements", "declarations", "findings", "fired", "unmapped", "issues", "dropped"};
    never raises on a bad reply.

    Partial admission: when upstream emission fails ("malformed" with instance findings), the instances it
    names are dropped (with any instance that then references a dropped one) and the rest is emitted again,
    so the valid part is still admitted; ``dropped`` lists (instance, reason) and status becomes "partial".
    ``unmapped`` / ``issues`` are upstream's own record of text the reply did not cover; the caller treats a
    reply with any of them as a partial parse."""
    out = {"status": "malformed", "statements": [], "declarations": [], "findings": [], "fired": {},
           "unmapped": [], "issues": [], "dropped": []}
    try:
        reply = extract_json(reply_text)
    except (json.JSONDecodeError, ValueError) as e:
        out["findings"].append({"kind": "json", "detail": f"reply is not JSON: {str(e)[:120]}"})
        return out
    if not isinstance(reply, dict):
        out["findings"].append({"kind": "json", "detail": "reply is not a JSON object"})
        return out
    V, catalog = _modules(hitl_root(root))
    reply = dict(reply)
    insts = reply.get("instances")
    for _round in range(len(insts) + 1 if isinstance(insts, list) else 1):
        try:
            res = V.inspect(reply, catalog, reference_time=reference_time, text=text)
        except Exception as e:                              # noqa: BLE001  upstream bug != our crash
            out["findings"].append({"kind": "upstream", "detail": f"{type(e).__name__}: {str(e)[:160]}"})
            return out
        if res.get("statements") is not None or not isinstance(reply.get("instances"), list):
            break
        cur = reply["instances"]
        bad = _bad_instances(res.get("findings") or [], cur)
        if not bad or len(bad) >= len(cur):
            break
        for i in sorted(bad):
            reasons = [str(f.get("detail")) for f in res["findings"] if f.get("kind") == "instance"]
            out["dropped"].append((json.dumps(cur[i], ensure_ascii=False)[:300], "; ".join(reasons)[:300]))
        reply["instances"] = [r for i, r in enumerate(cur) if i not in bad]
    for k in ("status", "findings", "fired", "unmapped", "issues"):
        if res.get(k) is not None:
            out[k] = res[k] if k != "findings" else out["findings"] + list(res[k])
    out["statements"] = list(res.get("statements") or [])
    out["declarations"] = list(res.get("declarations") or [])
    if out["dropped"] and res.get("statements") is not None:
        out["status"] = "partial"
    return out
