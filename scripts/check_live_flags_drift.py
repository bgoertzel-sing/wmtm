#!/usr/bin/env python3
"""L-02 (t-2026-11-24-wmtm-s5-ops): drift check between the live WMTM flags file and config/live-flags.json.

Read-only. Compares sha256 and the key set; on a sha mismatch it also lists the keys whose values differ.
Prints key names and hashes only, never values. Exit 0 = same, 1 = drift, 2 = a file is missing or not JSON.
Usage: check_live_flags_drift.py [--live PATH] [--repo PATH] [--json]
Default live path: $WMTM_LIVE_FLAGS or <protocosmo2 iter-port repos>/memory/_wmtm_flags.json (pop-os).
"""
import argparse, hashlib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LIVE = os.environ.get("WMTM_LIVE_FLAGS",
    "/home/openclaw/research-agent/projects/omegaclaw/protocosmo2/iter-port/repos/memory/_wmtm_flags.json")
DEFAULT_REPO = os.path.join(HERE, "..", "config", "live-flags.json")


def load(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    return hashlib.sha256(raw).hexdigest(), json.loads(raw)


def compare(live, repo):
    try:
        ls, ld = load(live)
        rs, rd = load(repo)
    except (OSError, ValueError) as e:
        return 2, {"status": "error", "error": type(e).__name__, "path": getattr(e, "filename", None)}
    out = {"live_sha256": ls, "repo_sha256": rs,
           "only_live": sorted(set(ld) - set(rd)), "only_repo": sorted(set(rd) - set(ld)),
           "value_differs": sorted(k for k in set(ld) & set(rd) if ld[k] != rd[k])}
    same = ls == rs
    out["status"] = "same" if same else "drift"
    if not same and not (out["only_live"] or out["only_repo"] or out["value_differs"]):
        out["note"] = "content equal as JSON, bytes differ (formatting/order)"
    return (0 if same else 1), out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", default=DEFAULT_LIVE)
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rc, out = compare(a.live, a.repo)
    if a.json:
        print(json.dumps(out, sort_keys=True))
    elif rc == 2:
        print("error", out["error"], out.get("path"))
    else:
        print(out["status"], "live", out["live_sha256"][:8], "repo", out["repo_sha256"][:8])
        for k in ("only_live", "only_repo", "value_differs"):
            if out[k]:
                print(" ", k, ", ".join(out[k]))
        if out.get("note"):
            print(" ", out["note"])
    return rc


if __name__ == "__main__":
    sys.exit(main())
