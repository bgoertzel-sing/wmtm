#!/usr/bin/env python3
"""t-2026-11-15-wmtm-sentence-feed: the parse worker in semparse_mode sentence, as a subprocess, 0 parse calls.
A private temp live dir, the 24e37182 checkout made by scripts/fetch_semparse_hitl.sh from the local clone, an empty
sent1 queue (so the loop has nothing to send), BASE_URL pointing at a closed local port (never contacted).
Cases: (a) prompt sha flag at its f44d7b74 default -> prompt_mismatch, exit 5; (b) hitl at f44d7b74 -> hitl_pin, exit
5; (c) the flags of the switch plan (hitl 24e37182, prompt sha 257425b2) -> status ok, mode sentence, parsed 0,
share role live.  Prints the worker_runs rows (counts and statuses only).
Usage: python3 reports/t-2026-11-15-wmtm-sentence-feed/tools/worker_smoke.py"""
import json, os, shutil, subprocess, sys, tempfile
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, REPO)
from wmtm import runtime_config as rc, semparse_sentence as SS   # noqa: E402
SRC = os.path.expanduser("~/scratch/pma/sph-24e37182")
tmp = tempfile.mkdtemp(prefix="sfd_smoke_")
try:
    hitl = {}
    for pin in ("24e37182", "f44d7b74"):
        d = os.path.join(tmp, "semparse-hitl-" + pin)
        subprocess.run(["bash", os.path.join(REPO, "scripts", "fetch_semparse_hitl.sh"), d, pin], check=True,
                       env=dict(os.environ, SEMPARSE_SRC=SRC), capture_output=True)
        hitl[pin] = d
    out = {}
    for case, pin, psha in (("a_default_prompt_sha", "24e37182", None), ("b_wrong_pin", "f44d7b74", None),
                            ("c_switch_flags", "24e37182", "257425b2c1593569789317f0f007f57f21f856df868b382adc0880c1c3414809")):
        live = os.path.join(tmp, case, "live")
        d = os.path.join(live, SS.SENT_VERSION)
        os.makedirs(d)
        cfg = rc.resolve()
        cfg.update(semparse_dir=d, parse_role="live", parse_live_dir=live, parse_share_live_per_hour=20,
                   parse_cap_per_hour=20, parse_budget_dir=os.path.join(tmp, case, "pb"), semparse_mode="sentence",
                   semparse_feed=True, semparse_hitl=hitl[pin], llm_env_file="")
        if psha:
            cfg["semparse_prompt_sha256"] = psha
        cp = os.path.join(d, "worker_config.json")
        rc.write_json_atomic(cp, cfg)
        env = dict(os.environ, PYTHONPATH=REPO, BASE_URL="http://127.0.0.1:9/v1", LLM_MODEL="smoke")
        env.pop("WMTM_SEMPARSE_HITL", None); env.pop("WMTM_SEMPARSE_MODE", None)
        r = subprocess.run([sys.executable, "-m", "wmtm.workers.semparse_feed", "--dir", d, "--config", cp, "--no-loader"],
                           cwd=REPO, env=env, capture_output=True, text=True, timeout=300)
        st = [json.loads(l) for l in open(os.path.join(d, "worker_runs.jsonl"))][-1]
        led = os.path.join(live, "share_ledger.jsonl")
        out[case] = {"rc": r.returncode, "status": st.get("status"), "mode": st.get("mode"), "parsed": st.get("parsed"),
                     "notes": st.get("notes"), "share": st.get("share"), "error": (st.get("error") or "")[:120],
                     "prompt_sha256": (st.get("prompt_sha256") or "")[:8] or None,
                     "ledger_rows": sum(1 for _ in open(led)) if os.path.exists(led) else 0}
    print(json.dumps(out, indent=1, sort_keys=True))
finally:
    shutil.rmtree(tmp, ignore_errors=True)
