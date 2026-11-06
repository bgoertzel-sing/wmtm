"""Track H parse worker: ``python -m wmtm.workers.semparse_feed --dir D [--config C]``.

Launched detached by wmtm/parse_cache.py; never waited on.  Drains the parse queue under the hourly cap with the
Track C SemParseAdapter: LLM via the existing OpenAI-compatible gateway through Man Hin's upstream chat-completions
provider (parse_cache.gateway_llm_usage; BASE_URL / LLM_MODEL / AI_API_KEY from the
environment, else from the env file named by ``llm_env_file``; the file is only read, never copied), load check in
PeTTaChainer (PeTTa rT 3681b9b + PeTTaChainer rT 202b9379, paths from the runtime config).

Gates before any LLM spend:
  * mode ``semparse_mode`` (default "catalog"): the hitl checkout ``semparse_hitl`` must be semantic-parsing-hitl
    @1f1a7a6f with its MIT LICENSE (semparse_catalog.verify_checkout), and the prompt sent is its
    templates/generated/PROMPT_CATALOG.txt (no legacy preamble); mode "legacy" sends ``semparse_prompt``;
  * the prompt file must exist and match ``semparse_prompt_sha256`` (default: PROMPT_CATALOG.txt @1f1a7a6f);
  * a no-LLM load canary (Grace pilot facts + mem_inh) must prove (Member grace person) and not
    (Member grace robot) through the same loader.
Optional --llm-canary also parses the canary sentence through the LLM (costs one parse; counted against the cap).
Address space is capped (worker_mem_mb).  One status line per run in worker_runs.jsonl (size-capped).
"""
import argparse, hashlib, json, os, sys, time

from wmtm import runtime_config as rc

ap = argparse.ArgumentParser()
ap.add_argument("--dir", required=True)
ap.add_argument("--config", default=None, help="worker_config.json written by the launcher (default: env/defaults)")
ap.add_argument("--n", type=int, default=None)
ap.add_argument("--petta", default=None)
ap.add_argument("--vendor", default=None, help="PeTTaChainer dir (contains pettachainer/)")
ap.add_argument("--prompt", default=None)
ap.add_argument("--no-loader", action="store_true", help="skip the PeTTa load check (tests only)")
ap.add_argument("--llm-canary", action="store_true")
a = ap.parse_args()
CFG = rc.load_worker_config(a.config) if a.config else rc.resolve()
a.petta = a.petta or CFG["petta_dir"]
a.vendor = a.vendor or CFG["pettachainer_dir"]
MODE = (os.environ.get("WMTM_SEMPARSE_MODE") or CFG.get("semparse_mode") or "catalog").strip().lower()
HITL = CFG.get("semparse_hitl") or None
MEM_CAP = rc.apply_mem_cap(CFG.get("worker_mem_mb"))
PRIO_GUARD = rc.PriorityGuard(CFG)          # SCHED_IDLE + nice set here in the child, re-asserted while it runs
PRIO = PRIO_GUARD.start()

from wmtm.parse_cache import ParseCache, process_queue, gateway_llm_usage  # noqa: E402

cache = ParseCache(a.dir, cfg=CFG)
status = {"ts": time.time(), "pid": os.getpid(), "mem_cap_mb": (MEM_CAP or 0) // (1 << 20), "prio": PRIO,
          "cap_per_hour": cache.per_hour}


def finish(code):
    status["end_ts"] = time.time()
    status["prio_end"] = PRIO_GUARD.stats()     # actual policy/nice at the end + how often it had to be re-asserted
    rc.append_jsonl(os.path.join(a.dir, "worker_runs.jsonl"), status, CFG.get("jsonl_max_bytes"))
    try:
        if open(cache.pidfile).read().strip() == str(os.getpid()):
            os.unlink(cache.pidfile)
    except OSError:
        pass
    sys.exit(code)


try:
    status["mode"] = MODE
    if MODE == "catalog":
        from wmtm import semparse_catalog as _sc
        try:
            HITL = _sc.hitl_root(HITL)       # wrong pin / missing or altered LICENSE -> refuse before any spend
        except (_sc.HitlPinError, FileNotFoundError) as e:
            status.update(status="hitl_pin", error=str(e)[:200]); finish(5)
        a.prompt = a.prompt or _sc.prompt_path(HITL)
    else:
        a.prompt = a.prompt or CFG["semparse_prompt"]
    try:
        with open(a.prompt, "rb") as fh:
            got = hashlib.sha256(fh.read()).hexdigest()
    except OSError as e:
        status.update(status="prompt_missing", error=type(e).__name__); finish(5)
    want = CFG.get("semparse_prompt_sha256") or ""
    if want and got != want:
        status.update(status="prompt_mismatch", prompt_sha256=got); finish(5)
    loader = None
    if not a.no_loader:
        sys.path.insert(0, os.path.join(a.petta, "python")); sys.path.insert(0, a.vendor)
        os.environ["PETTA_PATH"] = a.petta
        from pettachainer.pettachainer import PeTTaChainer
        loader = PeTTaChainer()
        for s in ["(: mem_inh (Implication (And (Member $x $a) (Inheritance $a $b)) (Member $x $b)) (STV 1.0 0.99))",
                  "(: cf (Member grace pilot) (STV 1.0 0.99))", "(: cg (Inheritance pilot person) (STV 1.0 0.99))"]:
            loader.add_atom(s)
        pos = str(loader.query("(: $prf (Member grace person) $tv)", steps=30, timeout_sec=0))
        neg = str(loader.query("(: $prf (Member grace robot) $tv)", steps=30, timeout_sec=0))
        status["load_canary"] = ("Member grace person" in pos) and ("Member grace robot" not in neg)
        if not status["load_canary"]:
            status["status"] = "canary_fail"; finish(3)
    llm = gateway_llm_usage(env_file=CFG.get("llm_env_file") or None, hitl=HITL,   # upstream provider (review-7)
                            workdir=os.path.join(a.dir, "provider"))
    status["model"] = getattr(llm, "model", None)
    from wmtm.semparse_adapter import SemParseAdapter
    if a.llm_canary:
        r = SemParseAdapter(llm, loader=loader, prompt_path=a.prompt, mode=MODE, hitl_root=HITL,
                           preamble=MODE == "legacy" and bool(CFG.get("semparse_preamble", True))).parse_item("canary1", "Grace is a pilot. Pilots are people.")
        u = llm.last_usage or {}
        with cache._lock():   # canary spend counts against the hourly cap
            rc.append_jsonl(cache.log_path, {"ts": time.time(), "item_id": "canary1", "status": "canary",
                                             "total_tokens": u.get("total_tokens"), "prompt_tokens": u.get("prompt_tokens"),
                                             "completion_tokens": u.get("completion_tokens")}, cache.log_max_bytes)
        ok = bool(r.accepted) and loader is not None and "Member grace person" in str(
            loader.query("(: $prf (Member grace person) $tv)", steps=30, timeout_sec=0))
        status["llm_canary"] = {"ok": ok, "accepted": len(r.accepted), "error": r.error}
        if not ok:
            status["status"] = "llm_canary_fail"; finish(3)
    pre = MODE == "legacy" and CFG.get("semparse_preamble", True)   # the preamble targets MeTTa output, not JSON
    ad = SemParseAdapter(llm, loader=loader, prompt_path=a.prompt, mode=MODE, hitl_root=HITL, reject_log=cache.reject_log,
                         max_chars=cache.max_chars, reject_log_max_bytes=cache.log_max_bytes, preamble=bool(pre))
    status.update(preamble=ad.preamble, file_sha256=ad.file_sha256, prompt_sha256=ad.prompt_sha256)   # v0.5: what is sent
    from wmtm.parse_cache import CTX_VERSION, SPK_VERSION, process_queue_ctx, process_queue_spk
    if CFG.get("speaker_link") and os.path.basename(os.path.normpath(a.dir)) == SPK_VERSION:
        # Track Q (opt-in, flags key speaker_link): speaker-linked text; old caches untouched, no backfill
        status["speaker_link"] = True
        base = ParseCache(os.path.dirname(os.path.normpath(a.dir)), cfg=CFG)
        recs = process_queue_spk(cache, llm, ad, n=a.n, cfg=CFG, base=base)
        status["speaker_stats"] = {"resolved": sum(1 for r in recs if r.get("speaker")),
                                   "by_source": {k: sum(r.get("speaker_source") == k for r in recs)
                                                 for k in sorted({str(r.get("speaker_source")) for r in recs})}}
    elif CFG.get("semparse_context") and os.path.basename(os.path.normpath(a.dir)) == CTX_VERSION:
        # Track O (opt-in, flags key semparse_context): parse with CONTEXT from the base cache + earlier ctx1 parses
        status["context"] = True
        base = ParseCache(os.path.dirname(os.path.normpath(a.dir)), cfg=CFG)
        recs = process_queue_ctx(cache, base, llm, ad, n=a.n, cfg=CFG)
    else:
        recs = process_queue(cache, llm, loader=loader, n=a.n, prompt_path=a.prompt, adapter=ad)
    status.update(status="ok", parsed=len(recs), by_status={s: sum(r["status"] == s for r in recs) for s in {r["status"] for r in recs}})
    finish(0)
except SystemExit:
    raise
except Exception as e:
    status.update(status="error", error=type(e).__name__ + ": " + str(e)[:200]); finish(4)
