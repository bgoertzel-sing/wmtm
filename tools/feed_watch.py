#!/usr/bin/env python3
"""feed_watch: tell a parse feed that has stopped from one that is idle (L-03, t-2026-11-15-wmtm-feed-watch).

Standalone and read-only.  It imports nothing from wmtm: the feed's own code path (feed_rows / launch_worker /
ParseCache.budget) is exactly what could fail silently, so this script reads the files directly:

  * the bot's flags file <state_dir>/_wmtm_flags.json (which cache is active, the share, the caps);
  * the active cache's queue.json and cache.jsonl (pending = queued hashes not yet in the cache; only the
    keys and numbers are read, never the queued text);
  * the live share's ledger <share dir>/share_ledger.jsonl and the share's parse logs (parse_log.jsonl in the
    share root, ctx1/ and spk1/), counted the way wmtm/parse_budget.py counts them;
  * the active cache's worker_runs.jsonl (+ .1), worker.pid and, when present, launch_decisions.jsonl (the
    one-line-per-decision record added in the same task).

Verdicts (exit codes):
  OK     0  feed off by flag; or nothing queued (idle); or the budget is not free (waiting for the share/cap);
            or a worker is running and younger than the stall window; or a run is recorded within the window.
  ALERT  1  items are queued, the budget is free, no worker run is recorded within the window (default 2 h) and
            no live worker younger than the window; or the decision record ends in >= 3 errors within the window.
  ERROR  3  the check cannot judge: unreadable flags, the feed not on the live share, a share dir that is not the
            feed's, a share or cap of 0, a missing cache dir, a corrupt queue, ledger rows from the future.
            Never reported as OK.
  (2 = usage error, from argparse.)

With --alert, ALERT and ERROR file one proposal through the bots' existing alert path ("hive-task propose",
this agent's own hive identity, as the gateway patch guard of t-2026-11-11 does), titled
"ALERT pop-os: parse feed stalled ..." so the chief of staff tags andy.  The same finding is not re-filed
within --realert-hours (default 24); going back to OK resets it.  Every run writes <status-dir>/last.json and
appends to <status-dir>/history.jsonl (size-capped).  Nothing it prints or stores contains note text.

  feed_watch.py --state-dir <bot memory dir>                      verdict only (dry run, the default)
  feed_watch.py --state-dir <bot memory dir> --alert              as installed in the timer
  ... --now EPOCH --stall-hours H --flags FILE --status-dir DIR --json --test-label TEXT --hive-task PATH
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time

HOUR = 3600.0
TAIL_BYTES = 1 << 20            # same tail as wmtm/parse_budget.py LOG_TAIL_BYTES
SUBCACHES = ("", "ctx1", "spk1")
FLAGS_FILENAME = "_wmtm_flags.json"
RUNTIME_SUBDIR = "_wmtm_shadow"
HIVE_TASK = "/opt/hive/agent-adapter/openclaw/hive-task"
DEFAULT_STATUS_DIR = os.path.join(os.path.expanduser("~"), ".local/state/parse-feed-watch")
HISTORY_MAX_BYTES = 512 * 1024
FUTURE_SLACK_S = 600            # ledger/log rows further in the future than this mean a clock problem
ERROR_STREAK = 3                # trailing error decisions (in the window) that count as a failing hook
EXIT = {"OK": 0, "ALERT": 1, "ERROR": 3}
# runtime_config SPEC defaults for the keys read here (wmtm ddd2096)
DEFAULTS = {"semparse_feed": False, "speaker_link": False, "semparse_context": False, "parse_role": "task",
            "parse_live_dir": "", "parse_share_live_per_hour": 10, "parse_cap_per_hour": 20,
            "runtime_dir": "", "semparse_dir": ""}


class CannotJudge(Exception):
    """The configuration or the files do not let the check judge the feed (verdict ERROR)."""

    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


# ------------------------------------------------------------------ reading
def _bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _int(key, v):
    try:
        if isinstance(v, bool):
            raise ValueError
        return int(v)
    except (TypeError, ValueError):
        raise CannotJudge("bad_flag", "flag %s is not an integer" % key)


def load_flags(path):
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except OSError as e:
        raise CannotJudge("flags_unreadable", "flags file unreadable (%s): %s" % (type(e).__name__, path))
    except ValueError:
        raise CannotJudge("flags_unreadable", "flags file is not JSON: %s" % path)
    if not isinstance(raw, dict):
        raise CannotJudge("flags_unreadable", "flags file is not a JSON object: %s" % path)
    return raw


def resolve(state_dir, raw):
    """The few keys the feed's launch depends on, resolved like wmtm.runtime_config.resolve (from the flags file
    only: the bot's own environment is not visible here, see the deploy plan)."""
    cfg = dict(DEFAULTS)
    for k in ("semparse_feed", "speaker_link", "semparse_context"):
        if k in raw:
            cfg[k] = _bool(raw[k])
    for k in ("parse_share_live_per_hour", "parse_cap_per_hour"):
        if k in raw:
            cfg[k] = _int(k, raw[k])
    for k in ("parse_role", "parse_live_dir", "runtime_dir", "semparse_dir"):
        if k in raw and raw[k] is not None:
            cfg[k] = str(raw[k])
    cfg["parse_role"] = (cfg["parse_role"] or "task").strip().lower()
    sd = os.path.abspath(state_dir)

    def path(v):
        if not v:
            return ""
        v = os.path.expanduser(v)
        return v if os.path.isabs(v) else os.path.normpath(os.path.join(sd, v))

    for k in ("parse_live_dir", "runtime_dir", "semparse_dir"):
        cfg[k] = path(cfg[k])
    cfg["runtime_dir"] = cfg["runtime_dir"] or os.path.join(sd, RUNTIME_SUBDIR)
    cfg["semparse_dir"] = cfg["semparse_dir"] or os.path.join(cfg["runtime_dir"], "semparse_cache")
    return cfg


def active_dir(cfg):
    """The cache feed_rows feeds: spk1 with speaker_link, else ctx1 with semparse_context, else the base dir."""
    base = cfg["semparse_dir"]
    b = os.path.basename(os.path.normpath(base))
    if cfg["speaker_link"] and b != "spk1":
        return os.path.join(base, "spk1")
    if cfg["semparse_context"] and b != "ctx1":
        return os.path.join(base, "ctx1")
    return base


def live_root(d):
    d = os.path.normpath(d)
    return os.path.dirname(d) if os.path.basename(d) in ("ctx1", "spk1") else d


def _rows(path, max_bytes=None):
    """dict rows of a jsonl file (whole file, or only its last max_bytes); torn lines skipped; missing = []."""
    try:
        with open(path, "rb") as fh:
            start = 0
            if max_bytes:
                fh.seek(0, os.SEEK_END)
                start = max(0, fh.tell() - max_bytes)
                fh.seek(start)
            data = fh.read()
    except OSError:
        return []
    if start:
        data = data.split(b"\n", 1)[1] if b"\n" in data else b""
    out = []
    for line in data.splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict):
            out.append(r)
    return out


def _ts(r, key="ts"):
    t = r.get(key)
    return float(t) if isinstance(t, (int, float)) and not isinstance(t, bool) else None


def share_used(share_dir, now):
    """(used in the rolling hour, rows from the future) for the live share: ledger call_ids + parse-log rows
    (rows with call_ids joined to the ledger, rows without count one, mocked rows none) -- parse_budget's rule."""
    ids, extra, future = set(), 0, 0
    for r in _rows(os.path.join(share_dir, "share_ledger.jsonl"), TAIL_BYTES):
        t = _ts(r)
        if t is None:
            continue
        if t > now + FUTURE_SLACK_S:
            future += 1
        if now - t < HOUR and r.get("call_id"):
            ids.add(r["call_id"])
    seen = set(ids)
    extra = 0
    for sub in SUBCACHES:
        for r in _rows(os.path.join(share_dir, sub, "parse_log.jsonl"), TAIL_BYTES):
            t = _ts(r)
            if t is None:
                continue
            if t > now + FUTURE_SLACK_S:
                future += 1
            if now - t >= HOUR or r.get("mocked") is True:
                continue
            cids = r.get("call_ids")
            if isinstance(cids, list):
                for c in cids:
                    if c not in seen:
                        seen.add(c)
                        extra += 1
            else:
                extra += 1
    return len(ids) + extra, future


def own_used(d, now):
    """The active cache's own hourly cap, as ParseCache.used_last_hour counts it (every row of its parse_log)."""
    return sum(1 for r in _rows(os.path.join(d, "parse_log.jsonl")) if now - (_ts(r) or 0) < HOUR)


def pending(d):
    """(pending count, oldest first_seen) -- queued hashes not in cache.jsonl.  Reads keys and numbers only."""
    qp = os.path.join(d, "queue.json")
    try:
        with open(qp, encoding="utf-8") as fh:
            q = json.load(fh)
    except FileNotFoundError:
        q = {}
    except OSError as e:
        raise CannotJudge("queue_unreadable", "queue unreadable (%s): %s" % (type(e).__name__, qp))
    except ValueError:
        raise CannotJudge("queue_corrupt", "queue.json is not JSON (the feed would read it as empty): %s" % qp)
    if not isinstance(q, dict):
        raise CannotJudge("queue_corrupt", "queue.json is not a JSON object: %s" % qp)
    done = {r.get("hash") for r in _rows(os.path.join(d, "cache.jsonl"))}
    waiting = [h for h in q if h not in done]
    seen = [q[h].get("first_seen") for h in waiting if isinstance(q[h], dict)]
    seen = [float(s) for s in seen if isinstance(s, (int, float)) and not isinstance(s, bool)]
    return len(waiting), (min(seen) if seen else None)


def last_run(d):
    best = None
    for p in (os.path.join(d, "worker_runs.jsonl"), os.path.join(d, "worker_runs.jsonl.1")):
        for r in _rows(p, TAIL_BYTES):
            for k in ("end_ts", "ts"):
                t = _ts(r, k)
                if t is not None and (best is None or t > best):
                    best = t
    return best


def worker(d, now):
    """{"pid", "alive", "age_s"} for the worker named in worker.pid (alive = a running wmtm.workers.* process)."""
    p = os.path.join(d, "worker.pid")
    try:
        with open(p) as fh:
            pid = int(fh.read().strip())
        age = now - os.path.getmtime(p)
    except (OSError, ValueError):
        return {"pid": None, "alive": False, "age_s": None}
    alive = True
    try:
        os.kill(pid, 0)
    except PermissionError:
        pass
    except OSError:
        alive = False
    if alive:
        try:
            with open("/proc/%d/stat" % pid) as fh:
                if fh.read().rsplit(")", 1)[1].split()[0] == "Z":
                    alive = False
            with open("/proc/%d/cmdline" % pid, "rb") as fh:
                if b"wmtm.workers." not in fh.read():
                    alive = False          # pid reused by something else
        except (OSError, IndexError):
            alive = False
    return {"pid": pid, "alive": alive, "age_s": round(age, 1)}


def decisions(d, now, window):
    """Summary of launch_decisions.jsonl (+ .1): last decision, counts in the window, trailing error streak."""
    rows = _rows(os.path.join(d, "launch_decisions.jsonl.1"), TAIL_BYTES) + \
        _rows(os.path.join(d, "launch_decisions.jsonl"), TAIL_BYTES)
    rows = [r for r in rows if _ts(r) is not None]
    if not rows:
        return {"present": os.path.exists(os.path.join(d, "launch_decisions.jsonl"))}
    rows.sort(key=_ts)
    last = rows[-1]
    by = {}
    for r in rows:
        if now - _ts(r) < window:
            by[str(r.get("decision"))] = by.get(str(r.get("decision")), 0) + 1
    streak, types = 0, set()
    for r in reversed(rows):
        if r.get("decision") != "error":
            break
        streak += 1
        types.add(str(r.get("error") or "?")[:60])
    return {"present": True, "last": {"ts": _ts(last), "decision": str(last.get("decision")),
                                      "error": (str(last.get("error"))[:60] if last.get("error") else None)},
            "in_window": by, "error_streak": streak, "error_types": sorted(types)}


def _ago(s):
    if s is None:
        return "never"
    return "%.1f h" % (s / HOUR) if s >= HOUR else "%d min" % int(s // 60)


def _utc(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if t else None


# ------------------------------------------------------------------ the check
def judge(state_dir, flags_path=None, now=None, stall_s=2 * HOUR):
    """-> {"verdict": OK|ALERT|ERROR, "code", "reasons": [...], "facts": {...}}.  Read-only."""
    now = time.time() if now is None else float(now)
    facts = {"now": _utc(now), "state_dir": os.path.abspath(state_dir), "stall_h": stall_s / HOUR}

    def out(verdict, code, *reasons):
        return {"verdict": verdict, "code": code, "reasons": list(reasons), "facts": facts}

    try:
        fp = flags_path or os.path.join(state_dir, FLAGS_FILENAME)
        facts["flags"] = fp
        cfg = resolve(state_dir, load_flags(fp))
        if not cfg["semparse_feed"]:
            return out("OK", "feed_off", "semparse_feed is off in the flags: the feed is not meant to run")
        if cfg["parse_role"] != "live":
            raise CannotJudge("not_live_share", "the live feed is not on the live share (parse_role=%s)"
                              % cfg["parse_role"])
        d = active_dir(cfg)
        root = os.path.realpath(live_root(cfg["semparse_dir"]))
        share_dir = os.path.realpath(cfg["parse_live_dir"]) if cfg["parse_live_dir"] else root
        facts.update(active_dir=d, share_dir=share_dir)
        if not os.path.isdir(share_dir):
            raise CannotJudge("share_dir_missing", "share dir does not exist: %s" % share_dir)
        if share_dir != root:
            raise CannotJudge("share_dir_mismatch", "the share ledger dir (%s) is not the feed's cache root (%s): "
                              "the budget would be counted where the feed does not log" % (share_dir, root))
        if not os.path.isdir(d):
            raise CannotJudge("cache_dir_missing", "active cache dir does not exist: %s" % d)
        share, cap = cfg["parse_share_live_per_hour"], cfg["parse_cap_per_hour"]
        if share <= 0 or cap <= 0:
            raise CannotJudge("budget_never_free", "share %d/h, cap %d/h: the budget can never be free" % (share, cap))
        used, future = share_used(share_dir, now)
        if future:
            raise CannotJudge("future_rows", "%d ledger/log rows are dated more than %d s in the future" %
                              (future, FUTURE_SLACK_S))
        own = own_used(d, now)
        n, oldest = pending(d)
        left = 0 if cap - own <= 0 else min(cap - own, max(0, share - used))
        lr = last_run(d)
        since = None if lr is None else now - lr
        w = worker(d, now)
        dec = decisions(d, now, stall_s)
        facts.update(pending=n, oldest_pending_age=_ago(None if oldest is None else now - oldest),
                     share={"per_hour": share, "used_last_hour": used, "remaining": max(0, share - used)},
                     own_cap={"per_hour": cap, "used_last_hour": own}, budget_left=left,
                     last_run=_utc(lr), since_last_run=_ago(since), worker=w, decisions=dec)
    except CannotJudge as e:
        return out("ERROR", e.code, str(e))

    if dec.get("error_streak", 0) >= ERROR_STREAK and now - dec["last"]["ts"] < stall_s:
        return out("ALERT", "hook_errors", "the feed hook's last %d launch decisions are errors (%s), the latest %s ago"
                   % (dec["error_streak"], ", ".join(dec["error_types"]), _ago(now - dec["last"]["ts"])))
    if n == 0:
        return out("OK", "idle", "idle: nothing queued (last run %s ago)" % _ago(since))
    if left <= 0:
        return out("OK", "budget_full", "%d queued, budget not free (share %d/%d used, own cap %d/%d): waiting"
                   % (n, used, share, own, cap))
    if w["alive"] and w["age_s"] is not None and w["age_s"] < stall_s:
        return out("OK", "running", "%d queued, worker %d running for %s" % (n, w["pid"], _ago(w["age_s"])))
    if since is not None and since < stall_s:
        return out("OK", "recent_run", "%d queued, budget free (%d left), last run %s ago" % (n, left, _ago(since)))
    hung = (" (worker %d alive but started %s ago: hung?)" % (w["pid"], _ago(w["age_s"]))) if w["alive"] else ""
    return out("ALERT", "stalled", "%d queued (oldest waiting %s), budget free (%d left: share %d/%d used, own cap "
               "%d/%d), no worker run for %s (last %s)%s" % (n, facts["oldest_pending_age"], left, used, share, own,
                                                              cap, _ago(since), _utc(lr) or "never", hung))


# ------------------------------------------------------------------ alert + status
def alert_text(res, status_dir, test_label=""):
    test = "TEST (%s), no action needed, please decline. " % test_label if test_label else ""
    f = res["facts"]
    if res["verdict"] == "ALERT":
        title = "ALERT pop-os: parse feed stalled (%s)" % f["now"]
    else:
        title = "ALERT pop-os: parse feed stalled? the watch cannot judge it (%s)" % f["now"]
    lines = [test + title, "For andy. The read-only parse-feed watch on pop-os (L-03) found:"]
    lines += ["- " + r for r in res["reasons"]]
    dec = f.get("decisions") or {}
    if dec.get("last"):
        err = (" (" + dec["last"]["error"] + ")") if dec["last"].get("error") else ""
        lines.append("Last launch decision: %s at %s%s." % (dec["last"]["decision"], _utc(dec["last"]["ts"]), err))
    lines.append("Read directly: flags %s; cache %s; share ledger dir %s." % (f.get("flags"), f.get("active_dir"),
                                                                              f.get("share_dir")))
    lines.append("Status: %s/last.json. Runbook: the feed-watch deploy plan (t-2026-11-15-wmtm-feed-watch)."
                 % status_dir)
    return "\n".join(lines)


def propose(text, hive_task):
    r = subprocess.run([hive_task, "propose", "andy (operator) via the pop-os parse-feed-watch timer", text],
                       capture_output=True, text=True, timeout=600)
    return r.returncode, (r.stdout + r.stderr).strip()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Read-only parse-feed stall check (L-03).")
    ap.add_argument("--state-dir", required=True, help="the bot's memory dir (holds _wmtm_flags.json)")
    ap.add_argument("--flags", default=None, help="flags file (default <state-dir>/_wmtm_flags.json)")
    ap.add_argument("--now", type=float, default=None)
    ap.add_argument("--stall-hours", type=float, default=2.0)
    ap.add_argument("--alert", action="store_true", help="file a hive proposal on ALERT/ERROR (timer mode)")
    ap.add_argument("--realert-hours", type=float, default=24.0)
    ap.add_argument("--status-dir", default=DEFAULT_STATUS_DIR)
    ap.add_argument("--hive-task", default=HIVE_TASK)
    ap.add_argument("--test-label", default="")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    res = judge(a.state_dir, a.flags, a.now, a.stall_hours * HOUR)
    now = time.time() if a.now is None else a.now
    if a.json:
        print(json.dumps(res, indent=1, sort_keys=True))
    else:
        print("parse-feed-watch %s %s [%s]" % (res["verdict"], res["facts"]["now"], res["code"]))
        for r in res["reasons"]:
            print("  " + r)
    rec = {"ts": now, "verdict": res["verdict"], "code": res["code"], "reasons": res["reasons"], "alert": None,
           "test_label": a.test_label}
    try:
        os.makedirs(a.status_dir, exist_ok=True)
        prev = {}
        try:
            with open(os.path.join(a.status_dir, "last.json"), encoding="utf-8") as fh:
                prev = json.load(fh)
        except (OSError, ValueError):
            pass
        key = res["verdict"] + ":" + res["code"]
        last_alert = prev.get("last_alert") if isinstance(prev, dict) else None
        rec["last_alert"] = None if res["verdict"] == "OK" else last_alert
        if res["verdict"] != "OK" and a.alert:
            repeat = (isinstance(last_alert, dict) and last_alert.get("key") == key and
                      now - float(last_alert.get("ts") or 0) < a.realert_hours * HOUR)
            if repeat:
                rec["alert"] = {"skipped": "same finding alerted %s ago" % _ago(now - float(last_alert["ts"]))}
                print("  alert not re-filed: " + rec["alert"]["skipped"])
            else:
                try:
                    rc_, out = propose(alert_text(res, a.status_dir, a.test_label), a.hive_task)
                except (OSError, subprocess.SubprocessError) as e:
                    rc_, out = -1, type(e).__name__
                rec["alert"] = {"via": "hive-task propose", "rc": rc_, "output": out[-1000:]}
                if rc_ == 0:
                    rec["last_alert"] = {"key": key, "ts": now}
                print("  alert via hive-task propose: rc=%d" % rc_)
        rec["facts"] = res["facts"]
        tmp = os.path.join(a.status_dir, "last.json.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(rec, fh, indent=1)
        os.replace(tmp, os.path.join(a.status_dir, "last.json"))
        hp = os.path.join(a.status_dir, "history.jsonl")
        try:
            if os.path.getsize(hp) > HISTORY_MAX_BYTES:
                os.replace(hp, hp + ".1")
        except OSError:
            pass
        with open(hp, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({k: rec[k] for k in ("ts", "verdict", "code", "reasons", "alert")}) + "\n")
    except OSError as e:
        print("  status not written (%s)" % type(e).__name__, file=sys.stderr)
    return EXIT[res["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
