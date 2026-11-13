#!/usr/bin/env python3
"""t-2026-11-12-wmtm-sentence-reasoning step 1: rebuild the sentence-mode accepted atoms per note exactly as the
sentence-parse v3 analysis did (tools/analyze.py sentence_runs: same SemParseAdapter catalog path, fed the stored
sentence replies; NO parse calls - the llm is a stub returning the stored replies) and write a cache dir per run
(cache.jsonl + rejects.jsonl) in the same row shape as the whole-note parse-variance caches, keyed by the raw spec
item content hash.  Only complete notes are written.  Canary: per-note atomset hash must equal analysis.json.
Usage: rebuild.py <out dir>.  Prints ids/counts/hashes only."""
import json, os, sys, hashlib, importlib.util
OUT = sys.argv[1]
SP = "/home/openclaw/scratch/sp2"
spec_ = importlib.util.spec_from_file_location("sp2an", SP + "/tools/analyze.py"); A = importlib.util.module_from_spec(spec_)
spec_.loader.exec_module(A)                    # analyze.py's own imports/paths (ppv wmtm, hitl templates, PV)
from wmtm.parse_cache import content_hash
B, SemParseAdapter, safe_id, PV = A.B, A.SemParseAdapter, A.safe_id, A.PV
an = json.load(open(SP + "/runs/analysis.json"))
spec = json.load(open("/home/openclaw/research-agent/projects/omegaclaw/frozen_parses/inputs/raw_spec_20notes.json"))
raw = {it["id"]: it["content"] for it in spec["raw_items"]}
rows = A.jl(SP + "/sel.jsonl"); blocks = {b[0]["doc"]: b for b in B.blocks_of(rows)}
clean = json.load(open(SP + "/clean.json"))
PSHA = "1585e873fc3151b8"
summary = {}
for run in ("s1", "s2", "s3"):
    pf = "%s/runs/%s/parsed.jsonl" % (SP, run); replies = B.read_replies(pf)
    d = os.path.join(OUT, run); os.makedirs(d, exist_ok=True)
    rejlog = os.path.join(d, "rejects.jsonl")
    if os.path.exists(rejlog): os.remove(rejlog)
    cache = []; per = {}
    for nid, meta in an["sentence"][run]["notes"].items():
        if not meta["complete"]: continue
        blk = blocks[nid]; prior, nxt = B.walk(blk, replies)
        assert nxt is None
        insts, un, iss = [], [], []
        for p in prior:
            resp = replies[p["row"]["id"]]["response"]
            un += resp.get("unmapped") or []; iss += resp.get("issues") or []; insts += p["instances"]
        combined = {"id": safe_id(nid), "instances": insts, "unmapped": un, "issues": iss}
        fake = lambda system, user, _c=json.dumps(combined, ensure_ascii=False): _c
        fake.last_usage = None
        ad = SemParseAdapter(fake, loader=A.loader(), prompt_path=A.PROMPT, mode="catalog", hitl_root=A.HITL,
                             reject_log=rejlog, max_chars=1500, preamble=False)
        res = ad.parse_item(nid, clean[nid]["clean"])
        aset = PV.norm_atoms(res.accepted)
        per[nid] = {"atoms": len(res.accepted), "atomset_ok": aset == meta["atomset"]}
        cache.append({"hash": content_hash(raw[nid]), "item_id": nid, "status": "ok", "atoms": list(res.accepted),
                      "prompt_sha": PSHA})
    with open(os.path.join(d, "cache.jsonl"), "w") as fh:
        for r in cache: fh.write(json.dumps(r) + "\n")
    summary[run] = {"notes": sorted(per), "atoms": sum(v["atoms"] for v in per.values()),
                    "atomset_ok": sum(v["atomset_ok"] for v in per.values()), "n": len(per),
                    "parsed_sha256": hashlib.sha256(open(pf, "rb").read()).hexdigest(),
                    "cache_sha256": hashlib.sha256(open(os.path.join(d, "cache.jsonl"), "rb").read()).hexdigest()}
json.dump(summary, open(os.path.join(OUT, "rebuild.json"), "w"), indent=1, sort_keys=True)
for r, s in summary.items(): print(r, "notes", s["n"], "atoms", s["atoms"], "atomset_ok", s["atomset_ok"], "cache", s["cache_sha256"][:12])
