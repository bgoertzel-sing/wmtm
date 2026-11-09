#!/usr/bin/env python3
"""Evidence for t-2026-11-10-wmtm-normaliser (ids, shapes, counts and hashes only; no note text).
Usage: make_evidence.py <evidence dir>.  Reads the frozen raw caches on pop-os and /tmp/nrm/runs/*."""
import json, sys, os, hashlib, collections
sys.path.insert(0, "/home/openclaw/research-agent/projects/omegaclaw/wmtm-module")
from wmtm import parse_normalise as N
from wmtm.semparse_adapter import split_toplevel
F = "/home/openclaw/research-agent/projects/omegaclaw/frozen_parses"
E = sys.argv[1]; os.makedirs(E, exist_ok=True)
PARSES = {"nov5_1f1a7a6f": "raw/nov5_1f1a7a6f_cache.jsonl", "nov9_f44d7b74": "raw/nov9_f44d7b74_cache.jsonl",
          "nov9_533c2274": "raw/nov9_533c2274_cache.jsonl"}
def member_narrow(atoms):
    n = 0
    for _s, node, err in split_toplevel("\n".join(atoms)):
        if err or not isinstance(node, list): continue
        def walk(x):
            nonlocal n
            if isinstance(x, list) and x:
                if x[0] == "Member" and len(x) == 3 and isinstance(x[2], list) and x[2] and x[2][0] == "Narrow": n += 1
                for y in x[1:]: walk(y)
        walk(node)
    return n
summary = {}
for k, rel in PARSES.items():
    p = os.path.join(F, rel)
    if not os.path.exists(p): summary[k] = None; continue
    c = {}
    for l in open(p):
        r = json.loads(l)
        if r.get("status") in ("ok", "empty"): c[r["item_id"]] = r.get("atoms") or []
    _, rep = N.normalise_cached(c); j = N.report_json(rep)
    json.dump(j, open(os.path.join(E, "unrecognised_%s.json" % k), "w"), indent=1, sort_keys=True)
    summary[k] = {"raw_sha256": hashlib.sha256(open(p, "rb").read()).hexdigest(), "notes": len(c),
                  "member_narrow": sum(member_narrow(v) for v in c.values()),
                  "mapped": sum(j["mapped"].values()), "known_unused": sum(j["known_unused"].values()),
                  "unrecognised": sum(j["unrecognised"].values()), "nwdef": j["nwdef"], "rewrites": j["rewrites"],
                  "top_unrecognised": dict(list(j["unrecognised"].items())[:10])}
runs = {}
for d in sorted(os.listdir("/tmp/nrm/runs")):
    sh = os.path.join("/tmp/nrm/runs", d, "shadow.jsonl")
    if not os.path.exists(sh): continue
    r = json.loads(open(sh).read().strip().splitlines()[-1])
    runs[d] = {k: r.get(k) for k in ("status", "atoms", "goals_n", "facts", "pc_proved", "timeouts", "semparse_items", "unparsed_items")}
    runs[d]["canary"] = (r.get("canary") or {}).get("ok"); runs[d]["goals"] = sorted(q["goal"] for q in r.get("queries", []))
json.dump({"parses": summary, "runs": runs}, open(os.path.join(E, "SUMMARY.json"), "w"), indent=1, sort_keys=True)
print(json.dumps({k: (v and {x: v[x] for x in ("notes", "member_narrow", "mapped", "unrecognised", "nwdef")}) for k, v in summary.items()}))
print(json.dumps({k: {x: v[x] for x in ("goals_n", "pc_proved", "canary")} for k, v in runs.items()}))
