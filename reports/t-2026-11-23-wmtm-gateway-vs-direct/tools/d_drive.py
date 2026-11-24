#!/usr/bin/env python3
"""t-2026-11-23-wmtm-gateway-vs-direct ARM D: the A1 driver, same blocks/context/prompt pin, but --provider anthropic --model claude-opus-5-5 --effort medium direct to the Messages API (key from ~/.config/wmtm/anthropic.env, never logged). No ParseBudget throttle (not the gateway share; slow pacing would expire the 5-min cache and re-write the catalog each call). Spend per call priced from Anthropic usage at a conservative table; hard stop on 429/usage limit or when spent + next-call estimate > USD CAP_USD.
Orig doc: t-2026-11-18-wmtm-clerk-ab ARM A1 (fresh sentence-mode semantic-parsing-hitl 660127d9), adapted from the t-2026-11-17 sentence driver: the master-adopt-v2 drive.py loop, unchanged in what it
sends (tmpl.blocks: sentence k with context_section of sentences 1..k-1; upstream parse_sentence; chat-completions,
temperature 0, timeout 300; PROMPT_CATALOG 257425b2 at semantic-parsing-hitl 24e37182).
Budget: wmtm ParseBudget task share (10/h, shared with all tasks), ledger row before each call; max 2 attempts per
sentence; hard stop on any 429/usage-limit error; hard cap MAX_CALLS for the task. Logs ids/counts/usage only.
Usage: drive.py SEL OUTDIR"""
import json, os, re, sys, time, hashlib, subprocess, argparse
TASK = "t-2026-11-23-wmtm-gateway-vs-direct"
H = os.environ.get("CLERK_AB_SPH", "../sph-660127d9"); TPL = H + "/templates"
PROMPT = TPL + "/generated/PROMPT_CATALOG.txt"; PSHA = "2826a9c35b29942f0f0d99323aa4e43aca3873973831ca287de19a3829e14098"
KEYF = os.path.expanduser("~/.config/wmtm/anthropic.env")
MODEL = os.environ.get("D_MODEL", "claude-opus-5-5"); EFFORT = os.environ.get("D_EFFORT", "medium")
CAP_USD = float(os.environ.get("D_CAP_USD", "30")); SPENT0 = float(os.environ.get("D_SPENT_BEFORE", "0"))
PRICE = {"in": float(os.environ.get("D_P_IN", "5")), "out": float(os.environ.get("D_P_OUT", "25"))}  # USD per Mtok; read 0.1x, 5m write 1.25x
WT = os.environ.get("CLERK_AB_WT", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
CAP = 20; MAX_ATT = 2; MAX_CALLS = int(os.environ.get("A1_MAX_CALLS", "260"))
LIMIT = re.compile(r"429|rate.?limit|usage.?limit|quota|too many requests|insufficient|credit", re.I)
SEL, P = sys.argv[1], sys.argv[2]
os.makedirs(P, exist_ok=True)
LOG = P + "/driver.log"; CALLS = P + "/calls.jsonl"; out = P + "/parsed.jsonl"
sys.path.insert(0, TPL); sys.path.insert(0, WT)
from tmpl import blocks as B, suite as S, manifest as MF   # noqa: E402
def log(m):
    with open(LOG, "a") as fh: fh.write(time.strftime("%Y-%m-%dT%H:%M:%S%z ") + m + "\n")
def jl(p):
    try: return [json.loads(l) for l in open(p) if l.strip()]
    except FileNotFoundError: return []
def stop(why):
    log("STOP " + why); open(P + "/STOP", "w").write(why + "\n"); sys.exit(2)
for line in open(KEYF, encoding="utf-8"):
    if line.startswith("ANTHROPIC_API_KEY="):
        os.environ["ANTHROPIC_API_KEY"] = line.rstrip("\n").split("=", 1)[1].strip().strip('"').strip("'")
if not os.environ.get("ANTHROPIC_API_KEY"): print("no key line"); sys.exit(3)
def cost(ru):
    ru = ru or {}; pi, po = PRICE["in"], PRICE["out"]
    return ((ru.get("input_tokens") or 0) * pi + (ru.get("cache_read_input_tokens") or 0) * pi * 0.1
            + (ru.get("cache_creation_input_tokens") or 0) * pi * 1.25 + (ru.get("output_tokens") or 0) * po) / 1e6
sp = S.load_parse_script(S.PARSE_SCRIPT)
class HardLimit(Exception):   # not an OSError/HTTPError: _post_json does not catch it, so no retry or long wait
    pass
_urlopen = sp.urllib.request.urlopen
def _guarded_urlopen(*a, **kw):
    try:
        return _urlopen(*a, **kw)
    except sp.urllib.error.HTTPError as exc:
        if exc.code == 429 or (exc.code in (400, 402, 403) and LIMIT.search(exc.read().decode("utf-8", "replace")[:2000])):
            raise HardLimit("HTTP %d usage/rate limit (hard stop, no retry)" % exc.code) from None
        raise
sp.urllib.request.urlopen = _guarded_urlopen
sp.PATIENT_WAITS = ()
ap = argparse.ArgumentParser(add_help=False); sp.add_provider_args(ap)
args = ap.parse_args(["--provider", "anthropic", "--model", MODEL, "--effort", EFFORT, "--timeout", "300.0", "--prompt", PROMPT])
args.dry_run = False
head = subprocess.run(["git", "-C", H, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
dirty = subprocess.run(["git", "-C", H, "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
psha = hashlib.sha256(open(PROMPT, "rb").read()).hexdigest()
if not head.startswith("660127d9") or dirty or psha != PSHA or S.stale_prompt(PROMPT):
    stop("pin check failed head=%s dirty=%s prompt=%s" % (head[:12], bool(dirty), psha[:12]))
if os.path.exists(P + "/STOP"): stop("STOP file present")
rows = jl(SEL); blocks = B.blocks_of(rows)
log("START hitl=%s prompt=%s sel=%s blocks=%d sentences=%d manifest=%s share=%s" % (
    head[:12], psha[:16], hashlib.sha256(open(SEL, "rb").read()).hexdigest()[:12], len(blocks), sum(len(b) for b in blocks), MF.current_id(), "model=%s effort=%s cap=%.2f spent_before=%.4f price=%s" % (MODEL, EFFORT, CAP_USD, SPENT0, PRICE)))
body_sha = S.prompt_body_sha(open(PROMPT, encoding="utf-8").read()); mid = MF.current_id()
for block in blocks:
    while True:
        replies = B.read_replies(out); prior, row = B.walk(block, replies)
        if row is None: break
        k = len(prior) + 1
        tried = sum(1 for c in jl(CALLS) if c["id"] == row["id"])
        if tried >= MAX_ATT:
            log("%s gave up after %d attempts; later sentences of %s not parsed" % (row["id"], tried, row["doc"])); break
        if len(jl(CALLS)) >= MAX_CALLS: stop("task call cap %d reached" % MAX_CALLS)
        context = B.context_section([{"k": p["k"], "text": p["text"], "instances": p["instances"]} for p in prior])
        if os.path.exists(P + "/STOP"): stop("STOP file present")
        if not context:   # order step 2: reuse an identical cached reply (same sentence text, no context) -- no call
            same = [r for r in jl(out) if r.get("sent") == 1 and r["text"] == row["text"] and B._good(r.get("reply"))
                    and not (r["reply"].get("item") or {}).get("context_sha256")]
            if same:
                rec = json.loads(json.dumps(same[0]["reply"])); rec["item"]["id"] = row["id"]
                rec["reused_from"] = same[0]["id"]; rec["block"] = {"doc": row.get("doc"), "k": k, "available_from": k}
                with open(out, "a", encoding="utf-8") as fh: fh.write(json.dumps({**row, "reply": rec}, ensure_ascii=False) + "\n")
                log("%s k=%d reused identical reply of %s (no call)" % (row["id"], k, same[0]["id"])); continue
        spent = SPENT0 + sum(c.get("usd") or 0 for c in jl(CALLS)); oks = [c["usd"] for c in jl(CALLS) if c.get("usd")]
        nxt = max(oks[-5:]) if oks else 1.5
        if spent + nxt > CAP_USD: stop("spend cap: spent %.4f + next-call est %.4f > %.2f" % (spent, nxt, CAP_USD))
        cid = None
        t0 = time.time(); err = None
        try:
            rec = sp.parse_sentence(row["text"], args, row["id"], context=context or None)
        except Exception as exc:
            err = (str(exc).splitlines() or [type(exc).__name__])[0][:300]
            rec = {"item": {"id": row["id"], "text": row["text"]}, "response": None, "error": "request failed: " + err}
        rec["prompt_body_sha256"] = body_sha; rec["manifest_id"] = mid
        rec["block"] = {"doc": row.get("doc"), "k": k, "available_from": k}
        with open(out, "a", encoding="utf-8") as fh: fh.write(json.dumps({**row, "reply": rec}, ensure_ascii=False) + "\n")
        ok = B._good(rec); u = rec.get("usage") or {}; ru = rec.get("raw_usage") or {}
        c = {"ts": t0, "doc": row["doc"], "id": row["id"], "k": k, "call_ids": [cid], "secs": round(time.time() - t0, 1),
             "ok": ok, "context_chars": len(context), "prompt_sha": (rec.get("prompt_sha256") or "")[:16],
             "usage": {"input": ru.get("input_tokens"), "cache_read": ru.get("cache_read_input_tokens"),
                       "cache_write": ru.get("cache_creation_input_tokens"), "output": ru.get("output_tokens"), "cached": u.get("cached")},
             "usd": round(cost(ru), 6), "error": (rec.get("error") or "")[:160] if not ok else None}
        with open(CALLS, "a") as fh: fh.write(json.dumps(c) + "\n")
        log("%s k=%d ok=%s %.0fs read=%s write=%s out=%s usd=%.4f cum=%.4f err=%s" % (row["id"], k, ok, c["secs"], c["usage"]["cache_read"], c["usage"]["cache_write"], c["usage"]["output"], c["usd"], SPENT0 + sum(x.get("usd") or 0 for x in jl(CALLS)), c["error"]))
        if (err and LIMIT.search(err)) or LIMIT.search(str(rec.get("error") or "")): stop("limit error: " + (err or rec.get("error"))[:160])
        if len(jl(CALLS)) == 1 and not (ok and (rec.get("response") or {}).get("instances") is not None):
            stop("canary: first call not a valid catalog reply (%s)" % c["error"])
log("DONE")
open(P + "/DONE", "w").write("done\n")
