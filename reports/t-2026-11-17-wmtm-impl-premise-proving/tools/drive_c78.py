#!/usr/bin/env python3
"""t-2026-11-17-wmtm-variable-implication-test sentence driver: the master-adopt-v2 drive.py loop, unchanged in what it
sends (tmpl.blocks: sentence k with context_section of sentences 1..k-1; upstream parse_sentence; chat-completions,
temperature 0, timeout 300; PROMPT_CATALOG 257425b2 at semantic-parsing-hitl 24e37182).
Budget: wmtm ParseBudget task share (10/h, shared with all tasks), ledger row before each call; max 2 attempts per
sentence; hard stop on any 429/usage-limit error; hard cap MAX_CALLS for the task. Logs ids/counts/usage only.
Usage: drive.py SEL OUTDIR"""
import json, os, re, sys, time, hashlib, subprocess, argparse
TASK = "t-2026-11-17-wmtm-impl-premise-proving"
H = "/home/openclaw/scratch/pma/sph-24e37182"; TPL = H + "/templates"
PROMPT = TPL + "/generated/PROMPT_CATALOG.txt"; PSHA = "257425b2c1593569789317f0f007f57f21f856df868b382adc0880c1c3414809"
ENVF = "/home/openclaw/.openclaw/protocosmo2.env"
WT = os.path.abspath("/home/openclaw/research-agent/projects/omegaclaw/ipp/wmtm-wt")
CAP = 10; MAX_ATT = 2; MAX_CALLS = 4
LIMIT = re.compile(r"429|rate.?limit|usage.?limit|quota|too many requests|insufficient|credit", re.I)
SEL, P = sys.argv[1], sys.argv[2]
os.makedirs(P, exist_ok=True)
LOG = P + "/driver.log"; CALLS = P + "/calls.jsonl"; out = P + "/parsed.jsonl"
sys.path.insert(0, TPL); sys.path.insert(0, WT)
from tmpl import blocks as B, suite as S, manifest as MF   # noqa: E402
from wmtm.parse_budget import ParseBudget                  # noqa: E402
def log(m):
    with open(LOG, "a") as fh: fh.write(time.strftime("%Y-%m-%dT%H:%M:%S%z ") + m + "\n")
def jl(p):
    try: return [json.loads(l) for l in open(p) if l.strip()]
    except FileNotFoundError: return []
def stop(why):
    log("STOP " + why); open(P + "/STOP", "w").write(why + "\n"); sys.exit(2)
env = {}
for line in open(ENVF, encoding="utf-8"):
    if "=" in line and not line.startswith("#"):
        k, v = line.rstrip("\n").split("=", 1); env[k.strip().replace("export ", "", 1).strip()] = v.strip().strip('"').strip("'")
os.environ["AI_API_KEY"] = os.environ.get("AI_API_KEY") or env.get("AI_API_KEY", "")
sp = S.load_parse_script(S.PARSE_SCRIPT)
ap = argparse.ArgumentParser(add_help=False); sp.add_provider_args(ap)
args = ap.parse_args(["--provider", "chat-completions", "--base-url", env["BASE_URL"], "--api-key-env", "AI_API_KEY",
                      "--model", env["LLM_MODEL"], "--timeout", "300.0", "--temperature", "0", "--prompt", PROMPT])
args.dry_run = False
head = subprocess.run(["git", "-C", H, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
dirty = subprocess.run(["git", "-C", H, "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
psha = hashlib.sha256(open(PROMPT, "rb").read()).hexdigest()
if not head.startswith("24e37182") or dirty or psha != PSHA or S.stale_prompt(PROMPT):
    stop("pin check failed head=%s dirty=%s prompt=%s" % (head[:12], bool(dirty), psha[:12]))
if os.path.exists(P + "/STOP"): stop("STOP file present")
rows = jl(SEL); blocks = B.blocks_of(rows)
budget = ParseBudget("task", cfg={"parse_budget_dir": "~/.wmtm/parse_budget", "parse_share_tasks_per_hour": CAP,
                                  "parse_live_dir": "", "parse_share_max_wait_s": 3700}, own_log=CALLS)
log("START hitl=%s prompt=%s sel=%s blocks=%d sentences=%d manifest=%s share=%s" % (
    head[:12], psha[:16], hashlib.sha256(open(SEL, "rb").read()).hexdigest()[:12], len(blocks), sum(len(b) for b in blocks), MF.current_id(), budget.status()))
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
        cid = budget.acquire({"task": TASK, "id": row["id"]}, wait=True)
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
             "usage": {"prompt_tokens": ru.get("prompt_tokens"), "cached": u.get("cached"), "output": ru.get("completion_tokens"),
                       "total": ru.get("total_tokens")}, "error": (rec.get("error") or "")[:160] if not ok else None}
        with open(CALLS, "a") as fh: fh.write(json.dumps(c) + "\n")
        log("%s k=%d ok=%s %.0fs cached=%s err=%s" % (row["id"], k, ok, c["secs"], c["usage"]["cached"], c["error"]))
        if (err and LIMIT.search(err)) or LIMIT.search(str(rec.get("error") or "")): stop("limit error: " + (err or rec.get("error"))[:160])
        if len(jl(CALLS)) == 1 and not (ok and (rec.get("response") or {}).get("instances") is not None):
            stop("canary: first call not a valid catalog reply (%s)" % c["error"])
log("DONE")
open(P + "/DONE", "w").write("done\n")
