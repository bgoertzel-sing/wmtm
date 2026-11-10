#!/usr/bin/env python3
"""Note-free evidence for t-2026-11-10-wmtm-narrow-preload: ids, parser symbols, counts, hashes.
Usage: make_evidence.py <evidence dir>.  Reads /tmp/npl (recover.py, mkstore.py, run_b.sh outputs) and the ppv caches."""
import json, sys, os, re, hashlib, collections
E = sys.argv[1]; os.makedirs(E, exist_ok=True); N = "/tmp/npl"
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
out = {"recovery": {}, "runs": {}, "goals": {}, "inputs": {}}
for r in ("r1", "r2", "r3"):
    c = json.load(open(f"{N}/rec_{r}/counts.json")); out["recovery"][r] = c
    ref = collections.Counter()
    for l in open(f"{N}/rec_{r}/rerejects.jsonl"):
        d = json.loads(l); a = d["atom"]
        m = re.match(r"\(: \S+ \((\w+)", a); outer = m.group(1) if m else "?"
        inner = "Narrow(Member ..)" if re.search(r"\(Narrow \S+ \(Member", a) else ("Narrow(Mod ..)" if "(Narrow" in a else "other")
        ref["%s>%s" % (outer, inner)] += 1
    out["recovery"][r]["still_refused_by_shape"] = dict(ref.most_common())
    out["recovery"][r]["recovered_sha256"] = sha(f"{N}/rec_{r}/recovered.jsonl")
    orig = {}
    for l in open(f"/home/openclaw/scratch/ppv/runs/{r}/cache/rejects.jsonl"):
        d = json.loads(l)
        if d["stage"] == "petta": orig[d["atom"].split()[1]] = d["atom"]
    rows = []
    for q in json.loads(open(f"{N}/runs/{r}_after/shadow.jsonl").read().strip().splitlines()[-1])["queries"]:
        by = re.search(r"\(by (\S+)", q["proof"]).group(1); o = orig.get(by, "")
        m = re.search(r"\(Narrow (\S+) \((Mod|Member) (\S+?)\)\)", o); cls = q["goal"].split()[-1].rstrip(")")
        rows.append({"goal": q["goal"], "top_rule": by, "recovered_rule": bool(o), "narrow_base": m and m.group(1),
                     "restriction_head": m and m.group(2), "restriction": m and m.group(3),
                     "trivial_echo": bool(m and m.group(3) == cls), "stv": q.get("stv")})
    out["goals"][r] = rows
for n in sorted(os.listdir(f"{N}/runs")):
    rec = json.loads(open(f"{N}/runs/{n}/shadow.jsonl").read().strip().splitlines()[-1])
    out["runs"][n] = {k: rec.get(k) for k in ("status", "atoms", "facts", "goals_n", "pc_proved", "timeouts", "unparsed_items", "add_fail")}
    out["runs"][n]["canary"] = (rec.get("canary") or {}).get("ok")
    out["runs"][n]["shadow_sha256"] = sha(f"{N}/runs/{n}/shadow.jsonl")
    out["runs"][n]["store_sha256"] = sha(f"{N}/store/{n}/frozen.jsonl")
for r in ("r1", "r2", "r3"):
    out["inputs"]["ppv_" + r] = {"cache_sha256": sha(f"/home/openclaw/scratch/ppv/runs/{r}/cache/cache.jsonl"),
                                 "rejects_sha256": sha(f"/home/openclaw/scratch/ppv/runs/{r}/cache/rejects.jsonl")}
F = "/home/openclaw/research-agent/projects/omegaclaw/frozen_parses/raw/nov9_f44d7b74_cache.jsonl"
out["inputs"]["f44d7b74"] = {"cache_sha256": sha(F), "rejects_log": "missing (/tmp/nrm/parse_f44d7b74 deleted)"}
out["judge"] = json.load(open(f"{N}/judge.json"))
json.dump(out, open(os.path.join(E, "SUMMARY.json"), "w"), indent=1, sort_keys=True)
for r in ("r1", "r2", "r3"):
    g = out["goals"][r]; print(r, "goals", len(g), "echo", sum(x["trivial_echo"] for x in g), out["recovery"][r]["still_refused_by_shape"])
