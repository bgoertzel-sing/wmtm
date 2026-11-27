#!/usr/bin/env python3
"""L-11 (t-2026-11-24-wmtm-s5-ops): rollback triggers T1-T7 of docs/SWITCH_PLAN_S1.md section 5, as a read-only check.

Replays the live WMTM decision records over a time window (default: last 24 h) and counts how often each trigger
would have fired. Counts, field names and timestamps only; never note text or atoms.
NOT triggers (by design): share_full / cap_full / budget_zero / busy / nothing_pending / rate_limited worker or
launch rows with err null; a full admit cap (admitted == reasoner_max_admit); 429 anywhere except an integer HTTP
status field; empty admit file; no traffic.
Usage: check_live_triggers.py [--repos DIR] [--hours 24] [--since EPOCH] [--json]
Exit 0 = no trigger fired, 1 = at least one fired, 2 = records missing.
"""
import argparse, collections, glob, json, os, re, sys, time

DEFAULT_REPOS = os.environ.get("WMTM_LIVE_REPOS",
    "/home/openclaw/research-agent/projects/omegaclaw/protocosmo2/iter-port/repos")
DESIGNED = {"busy", "nothing_pending", "budget_zero", "share_full", "cap_full", "rate_limited"}
XR_NI = re.compile(r"^(xr_|nimpl:)")
HTTP_KEYS = ("http_status", "status_code", "http_code")


def rows(path):
    out = []
    for p in sorted(glob.glob(path + ".1")) + [path]:   # rotated file first, then current
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out


def ts(r):
    return float(r.get("start_ts") or r.get("ts") or r.get("end_ts") or 0)


def consecutive(flags):
    """number of rows that complete a run of >= 2 consecutive True flags"""
    n = run = 0
    for f in flags:
        run = run + 1 if f else 0
        n += run >= 2
    return n


def replay(repos, t0, t1, log=None, max_admit=None):
    M = os.path.join(repos, "memory", "_wmtm_shadow"); P = M + "/pc_shadow"; S = M + "/semparse_cache/sent1"
    if not os.path.exists(P + "/shadow.jsonl"):
        return None
    win = lambda rs: sorted((r for r in rs if t0 <= ts(r) < t1), key=ts)
    sh, al, wr, pl = (win(rows(P + "/shadow.jsonl")), win(rows(P + "/admit_log.jsonl")),
                      win(rows(S + "/worker_runs.jsonl")), win(rows(S + "/parse_log.jsonl")))
    flags = {}
    try:
        flags = json.load(open(os.path.join(repos, "memory", "_wmtm_flags.json")))
    except (OSError, ValueError):
        pass
    cap = int(max_admit or flags.get("reasoner_max_admit") or 5)
    T = {}; D = {}
    # T1: pin mismatch ImportError from the package path (vendor/wmtm-*), in the supervisor log within the window
    t1n = 0
    if log and os.path.exists(log):
        cur = None; buf = []
        stamp = re.compile(r"Step (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)")
        with open(log, encoding="utf-8", errors="replace") as fh:
            fh.seek(max(0, os.path.getsize(log) - 200_000_000))
            for line in fh:
                m = stamp.search(line)
                if m:
                    cur = time.mktime(time.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")); buf = []
                if cur is None or not (t0 <= cur < t1):
                    continue
                buf = (buf + [line])[-40:]
                if "wmtm pin mismatch" in line and "ImportError" in line and \
                        any(re.search(r'File ".*/vendor/wmtm-[^/]+/', b) for b in buf):
                    t1n += 1
    T["T1_pin_package"] = t1n
    # T2: 2 consecutive shadow rows with status not ok and not a designed stop
    bad = [r.get("status") != "ok" and not (r.get("status") in DESIGNED and r.get("err") is None) for r in sh]
    T["T2_shadow_failure"] = consecutive(bad)
    D["shadow_status"] = dict(collections.Counter(str(r.get("status")) for r in sh))
    # T3: canary.ok false, add_fail > 0 or pred_fail > 0 (any one row)
    t3 = [r for r in sh if (r.get("canary") is not None and not (r.get("canary") or {}).get("ok"))
          or (r.get("add_fail") or 0) > 0 or (r.get("pred_fail") or 0) > 0]
    T["T3_canary"] = len(t3)
    D["T3_by_field"] = {"canary_ok_false": sum(1 for r in sh if r.get("canary") is not None and not (r.get("canary") or {}).get("ok")),
                        "add_fail_gt0": sum(1 for r in sh if (r.get("add_fail") or 0) > 0),
                        "pred_fail_gt0": sum(1 for r in sh if (r.get("pred_fail") or 0) > 0)}
    D["T3_first_last_utc"] = [time.strftime("%FT%TZ", time.gmtime(ts(r))) for r in (t3[:1] + t3[-1:])] if t3 else []
    D["neg_canary_timeouts"] = sum(1 for r in sh if (r.get("neg") or {}).get("timeout"))
    # T4: timeouts > 0 or skipped_budget > 0 in 2 consecutive shadow rows
    T["T4_timeouts_budget"] = consecutive([(r.get("timeouts") or 0) > 0 or (r.get("skipped_budget") or 0) > 0 for r in sh])
    # T5: xr/ni restatement admitted, or more than the admit cap in one run (a FULL cap is normal)
    over = [r for r in al if isinstance(r.get("admitted"), int) and r["admitted"] > cap]
    rest = 0
    try:
        adm = json.load(open(P + "/admit.json")) if os.path.getsize(P + "/admit.json") else {}
        trivial = set(map(str, adm.get("trivial_refused") or []))
        for x in adm.get("results") or []:
            if isinstance(x, dict) and XR_NI.match(str(x.get("rule") or "")) and str(x.get("goal")) in trivial:
                rest += 1
    except (OSError, ValueError, AttributeError):
        pass
    T["T5_admission_quality"] = len(over) + rest
    D["admit_rows"] = len(al); D["admit_cap"] = cap
    D["admit_full_cap_rows_not_trigger"] = sum(1 for r in al if r.get("admitted") == cap)
    # T6: integer HTTP status field == 429, >= 3 within one rolling hour (never a substring match)
    hits = sorted(ts(r) for r in pl for k in HTTP_KEYS if isinstance(r.get(k), int) and not isinstance(r.get(k), bool) and r[k] == 429)
    T["T6_http_429"] = sum(1 for i, t in enumerate(hits) if sum(1 for u in hits[:i + 1] if t - u < 3600) >= 3)
    D["http_429_rows"] = len(hits); D["parse_log_rows"] = len(pl)
    D["parse_log_has_http_field"] = any(k in r for r in pl for k in HTTP_KEYS)
    # T7: human-confirmed W among admitted xr/ni conclusions: needs a verdict file; none exists pre-switch
    T["T7_wrong_conclusion"] = 0
    D["T7_note"] = "needs human verdicts on admitted xr/ni conclusions; pre-switch there are no xr/ni rules"
    # non-triggers seen (counted, never fire)
    D["worker_rows"] = dict(collections.Counter(str(r.get("status")) for r in wr))
    D["worker_designed_stops_err_null"] = sum(1 for r in wr if r.get("status") in DESIGNED)
    D["shadow_rows"] = len(sh)
    return {"window_utc": [time.strftime("%FT%TZ", time.gmtime(t0)), time.strftime("%FT%TZ", time.gmtime(t1))],
            "triggers": T, "fired": sorted(k for k, v in T.items() if v), "detail": D}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos", default=DEFAULT_REPOS)
    ap.add_argument("--hours", type=float, default=24.0)
    ap.add_argument("--since", type=float, default=None)
    ap.add_argument("--until", type=float, default=None)
    ap.add_argument("--log", default=os.path.expanduser("~/.openclaw/protocosmo2-supervisor.log"))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    t1 = a.until or time.time(); t0 = a.since or t1 - a.hours * 3600
    out = replay(a.repos, t0, t1, a.log)
    if out is None:
        print("error: no shadow records under", a.repos); return 2
    if a.json:
        print(json.dumps(out, sort_keys=True))
    else:
        print("window", *out["window_utc"])
        for k, v in out["triggers"].items():
            print(" ", k, v)
        print("fired:", ", ".join(out["fired"]) or "none")
    return 1 if out["fired"] else 0


if __name__ == "__main__":
    sys.exit(main())
