#!/usr/bin/env python3
"""Build sandbox frozen stores (outside the repo) for B before/after recovery.  No parse calls: rows come from an
existing cache.jsonl plus recovered.jsonl (recover.py).  Usage: mkstore.py <cache.jsonl> <recovered.jsonl|-> <pin> <out dir>"""
import json, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from wmtm.frozen_parse import FrozenStore
cache, rec, pin, out = sys.argv[1:5]
add = {}
if rec != "-":
    for l in open(rec):
        d = json.loads(l); add.setdefault(d["item_id"], []).extend(d["accepted"])
if os.path.exists(os.path.join(out, "frozen.jsonl")): os.remove(os.path.join(out, "frozen.jsonl"))
st = FrozenStore(out); n = m = 0
for l in open(cache):
    r = json.loads(l)
    if r.get("status") not in ("ok", "empty"): continue
    atoms = list(r.get("atoms") or [])
    for a in add.get(r["item_id"], []):
        if a not in atoms: atoms.append(a); m += 1
    n += st.put(r["hash"], pin, r["prompt_sha"], r["item_id"], r["status"], atoms)
print(json.dumps({"entries": n, "added_atoms": m, "manifest_file_sha256": st.manifest()["file_sha256"]}))
