#!/usr/bin/env python3
"""Per-arm item 1-4/6 counts from a turn_loop run dir (ids/hashes only, no note text).
Usage: analyze_loop.py <run dir> ...  -> JSON per arm."""
import json, os, re, sys, glob
TAG = re.compile(r"^\s*\[(derived|asserted|recalled|user)\b([^\]]*)\]")
out = {}
for d in sys.argv[1:]:
    st = os.path.join(d, "state"); arm = os.path.basename(d.rstrip("/"))
    T = [json.loads(l) for l in open(os.path.join(d, "out", "turns.jsonl"))]
    s = json.load(open(os.path.join(st, "_wmtm_state.json")))
    recs = s.get("forgetting_log", {}).get("records", [])
    ev_by_tick = {}
    for r in recs: ev_by_tick[r.get("evicted_at_tick")] = ev_by_tick.get(r.get("evicted_at_tick"), 0) + 1
    G = [json.loads(l) for l in open(os.path.join(st, "runtime", "goalchainer", "runs.jsonl"))]
    esc = sum((g.get("v2", {}).get("decisions") or {}).get("escalated", 0) for g in G)
    ch = sum(g.get("v2", {}).get("choices") or 0 for g in G)
    dec = {}
    for g in G:
        for k, v in (g.get("v2", {}).get("decisions") or {}).items(): dec[k] = dec.get(k, 0) + v
    der = der_tv = der_src = focus_lines = 0
    for f in sorted(glob.glob(os.path.join(d, "out", "ctx_*.txt"))):
        infocus = False
        for l in open(f):
            if "[recent focus]" in l: infocus = True; continue
            m = TAG.match(l)
            if not m: continue
            if infocus: focus_lines += 1
            if m.group(1) == "derived":
                der += 1; der_tv += "tv=" in m.group(2) and "tv=none" not in m.group(2); der_src += "from=" in m.group(2) and "from=none" not in m.group(2)
    S = [json.loads(l) for l in open(os.path.join(st, "runtime", "pc_shadow", "shadow.jsonl"))]
    out[arm] = {"turns": len(T), "errors": sum(1 for t in T if t["err"]), "user_turns": sum(t["kind"] == "user" for t in T),
                "auto_ticks": sum(t["kind"] == "auto" for t in T), "evictions_total": len(recs),
                "evictions_by_source": {k: sum(1 for r in recs if r.get("source_type") == k) for k in {r.get("source_type") for r in recs}},
                "gc_runs": len(G), "gc_ok": sum(g.get("status") == "ok" for g in G),
                "gc_canary_ok": sum(bool((g.get("canary") or {}).get("ok")) for g in G), "gc_decisions": dec,
                "escalations": esc, "choices": ch, "focus_headers": sum(t["focus_hdr"] for t in T), "focus_lines": focus_lines,
                "derived_lines": der, "derived_with_tv": der_tv, "derived_with_src": der_src,
                "shadow_runs": len(S), "shadow_goals_max": max([x.get("goals_n") or 0 for x in S] or [0]),
                "shadow_proved_max": max([sum(1 for q in x.get("queries", []) if q.get("ok")) for x in S] or [0])}
print(json.dumps(out, indent=1))
