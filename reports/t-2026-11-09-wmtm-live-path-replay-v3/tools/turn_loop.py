#!/usr/bin/env python3
"""Sandbox live-path turn loop (t-2026-11-09-wmtm-live-path-replay-v3).  One arm per process.
Usage: turn_loop.py --code <wmtm src dir> --state <sandbox state dir> --notes raw_spec.json --out <dir> [--n 20]
Per note i: write it to the sandbox journal, run a USER turn (observe + context_for with a request built from the
note id only, never note text in logs), wait for the detached pc_shadow worker (+ GoalChainer v2 hook), then one
AUTOMATED tick (context_for('') fast path).  Logs per turn: evictions/forgets (forget_log delta), recent-focus lines,
context lines with/without TV + source tags, goalchainer runs/choices.  Opens no ports; never touches live dirs."""
import argparse, json, os, sys, time, hashlib, re
ap = argparse.ArgumentParser()
for k in ("--code", "--state", "--notes", "--out"): ap.add_argument(k, required=True)
ap.add_argument("--n", type=int, default=20); ap.add_argument("--wait", type=float, default=900)
a = ap.parse_args()
LIVE = "/home/openclaw/research-agent/projects/omegaclaw/protocosmo2/iter-port/repos/memory"
assert not os.path.abspath(a.state).startswith(LIVE), "refuse: live state dir"
sys.path.insert(0, a.code)
os.environ["JOURNAL_DIR"] = os.path.join(a.state, "_journal")
from wmtm.api import WMTM, WMTMConfig
from wmtm.journal import PettaJournal
from wmtm import runtime_config as rc
os.makedirs(a.out, exist_ok=True)
log = open(os.path.join(a.out, "turns.jsonl"), "a")
notes = json.load(open(a.notes))["raw_items"][:a.n]
jr = PettaJournal(os.environ["JOURNAL_DIR"])
mem = WMTM(WMTMConfig(state_dir=a.state))          # same as the live transformation: use_goalchainer default False
cfg = rc.resolve(a.state)
gdir = os.path.join(cfg["runtime_dir"], "goalchainer"); sdir = cfg["shadow_dir"]
def nlines(p):
    try: return sum(1 for _ in open(p))
    except OSError: return 0
def wait_worker():
    t0 = time.time()
    while rc.busy(os.path.join(sdir, "worker.pid"), 1800) and time.time() - t0 < a.wait: time.sleep(2)
    return round(time.time() - t0, 1)
def flog():
    try: return len(json.load(open(mem.state_file)).get("forgetting_log", {}).get("records", []) or [])
    except Exception: return -1
def ctx_stats(c):
    L = [l for l in (c or "").splitlines() if l.strip()]
    der = [l for l in L if "derived" in l.lower() or "conclusion" in l.lower() or "(by " in l]
    tv = re.compile(r"(stv|tv|strength|conf)[^\n]*\d\.\d", re.I); src = re.compile(r"(from|src|source|sources)[:= ]", re.I)
    foc = sum(1 for l in L if "[recent focus]" in l)
    return {"lines": len(L), "sha": hashlib.sha256((c or "").encode()).hexdigest()[:16], "focus_hdr": foc,
            "derived": len(der), "derived_tv": sum(1 for l in der if tv.search(l)), "derived_src": sum(1 for l in der if src.search(l))}
for i, it in enumerate(notes):
    _cid = it["id"]; _ev = "ev-" + _cid    # real note id as cluster id, so the recall bridge resolves it (relevance_stimulus)
    _ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(it.get("origin_ts", 0)) or time.time()))
    _safe = it["content"].replace("\\", "\\\\").replace('"', '\\"')
    with open(jr.path, "a", encoding="utf-8") as _fh:
        _fh.write(";;; BEGIN MemoryCluster %s\n(MemoryCluster %s)\n(SchemaVersion %s medium-memory-v1)\n(ClusterType %s Episode)\n"
                  "(ClusterSource %s iter-experience)\n(ClusterOpenedAt %s %s)\n(Contains %s %s)\n(ObservedEvent %s)\n"
                  "(About %s journal)\n(EventNote %s \"%s\")\n;;; END MemoryCluster %s\n"
                  % (_cid, _cid, _cid, _cid, _cid, _cid, _ts, _cid, _ev, _ev, _cid, _ev, _safe, _cid))
    mem._last_refresh = 0                # re-parse the sandbox journal on this turn
    mem._ensure_store_ready()            # same admit call the recall path makes (api.py recall loop), real note id
    if it["id"] not in mem.orchestrator.store:
        mem.orchestrator.store.admit(it["id"], it["content"], source_type=it.get("source_type", "recalled"),
                                     initial_sti=float(it.get("sti", 1.0)), origin_timestamp=float(it.get("origin_ts", 0)))
        from wmtm import context as _cx
        if _cx.protect_settings(mem._flags()):   # api.py recall loop: it.mark_recalled(orch.cycle_count) when protect is on
            mem.orchestrator.store.get(it["id"]).mark_recalled(mem.orchestrator.cycle_count)
    for kind in ("user", "auto"):
        f0, g0, s0 = flog(), nlines(os.path.join(gdir, "runs.jsonl")), nlines(os.path.join(sdir, "shadow.jsonl"))
        t0 = time.time()
        try:
            if kind == "user":
                req = "Status of %s and what follows from it?" % it["id"]
                mem.observe({"user": req, "assistant": None}); c = mem.context_for(req); mem.save()
            else:
                c = mem.context_for("", automated=True)
            err = None
        except Exception as e:
            c, err = None, "%s: %s" % (type(e).__name__, str(e)[:200])
        ts = round(time.time() - t0, 3); w = wait_worker()
        rec = {"i": i, "note": it["id"], "kind": kind, "turn_s": ts, "worker_wait_s": w, "err": err,
               "forget_events": flog() - f0, "gc_runs_new": nlines(os.path.join(gdir, "runs.jsonl")) - g0,
               "shadow_new": nlines(os.path.join(sdir, "shadow.jsonl")) - s0, **ctx_stats(c)}
        open(os.path.join(a.out, "ctx_%02d_%s.txt" % (i, kind)), "w").write(c or "")   # sandbox only, never committed
        log.write(json.dumps(rec) + "\n"); log.flush(); print(json.dumps(rec), flush=True)
print("LOOP_DONE", flush=True)
