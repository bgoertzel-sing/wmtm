"""WMTM -> GoalChainer v2 runner.  Runs INSIDE the GoalChainer v2 environment, never inside WMTM's interpreter:

    <v2 env>/bin/python -I v2_runner.py --mem-mb N  < job.json  > result.json

It is started by wmtm/goals/v2.py:client() as a separate process (own session, hard timeout, SIGKILL of the group).
WMTM's own process never imports goal_chainer: GoalChainer v2 is distributed as GPL-3.0-only AND MIT AND Apache-2.0,
it is installed separately (see docs/GOALS_V2.md), and nothing of it is copied into this repository.  This file is
WMTM's own code; it only calls v2's public request API (goal_chainer.requests.run_request,
goal_chainer.motivation.run_motivation_request).  Standard library only besides that API; Python >= 3.12.

Job (wmtm-gc2-job-v1): {workdir, budget {inferences, timeout_seconds}, series: [{label, header, blocks {action:
text}, order [action], observations [...], as_of, passes [{label, readings}], remove {action: [action]},
max_reviews}]}.  Per series: one per-run motivation stream (observe), then per pass up to max_reviews reviews; after
each "propose" the proposed action and its remove-group leave the domain and the rest is reviewed again; any other
disposition ends the pass.  Result (wmtm-gc2-result-v1): {versions, s, series: [{label, s, passes: [{label,
reviews: [review record without domain/policy/readset/readings]}]}]}.  Errors are reported, never raised."""
import argparse
import json
import os
import sys
import time

DROP = ("domain", "review_policy", "readset", "readings")


def _cap(mb):
    try:
        import resource
        lim = int(mb) * 1024 * 1024
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        if hard != resource.RLIM_INFINITY:
            lim = min(lim, hard)
        resource.setrlimit(resource.RLIMIT_AS, (lim, hard))
    except Exception:   # noqa: BLE001
        pass


def _versions():
    out = {"python": sys.version.split()[0]}
    try:
        from importlib import metadata
        for d in ("pymetta", "omegaclaw-goalchainer"):
            try:
                out[d] = metadata.version(d)
            except Exception:   # noqa: BLE001
                out[d] = None
    except Exception:   # noqa: BLE001
        pass
    return out


def _write(path, header, blocks, keep):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(header + "\n")
        for a in keep:
            fh.write(blocks[a] + "\n")


def run_series(s, budget, workdir, api):
    run_request, run_motivation_request, RunBudget = api
    t0 = time.time()
    d = os.path.join(workdir, "".join(ch for ch in str(s.get("label") or "s") if ch.isalnum() or ch in "-_")[:40])
    os.makedirs(d, exist_ok=True)
    header, blocks, order = s["header"], s["blocks"], list(s["order"])
    remove = {k: set(v) for k, v in (s.get("remove") or {}).items()}
    store = os.path.join(d, "motivation.sqlite3")
    sel = {"store": store, "stream": "wmtm"}
    out = {"label": s.get("label"), "passes": []}

    def B():
        return RunBudget(inference_budget=int(budget["inferences"]), timeout_seconds=float(budget["timeout_seconds"]))
    dom0 = os.path.join(d, "domain.metta")
    _write(dom0, header, blocks, order)
    if s.get("observations") and order:
        r = run_motivation_request({"domain": {"path": dom0}, "operation": "observe", "motivation": sel,
                                    "observations": s["observations"]}, budget=B())
        if not isinstance(r, dict) or not r.get("recorded") and not r.get("already_recorded"):
            out["observe_error"] = str(r)[:300]
    for p in s.get("passes") or ():
        removed, reviews = set(), []
        for i in range(max(0, int(s.get("max_reviews") or 1))):
            keep = [a for a in order if a not in removed]
            if not keep:
                break
            dom = os.path.join(d, "%s-%d.metta" % (p.get("label"), i))
            _write(dom, header, blocks, keep)
            req = {"domain": {"path": dom}, "operation": "review", "motivation": sel,
                   "context": {"review_id": "%s-%s-%d" % (s.get("label"), p.get("label"), i), "subject": "wmtm-goals",
                               "trigger": "wmtm-shadow", "as_of": s["as_of"], "authority": "advisory",
                               "readings": p.get("readings") or []}}
            try:
                r = run_request(req, budget=B())
            except Exception as e:   # noqa: BLE001
                reviews.append({"error": type(e).__name__ + ": " + str(e)[:300]})
                break
            rv = r.get("review") if isinstance(r, dict) else None
            if not isinstance(rv, dict):
                reviews.append({"error": "no review: " + json.dumps(r)[:300]})
                break
            reviews.append({k: v for k, v in rv.items() if k not in DROP})
            if rv.get("disposition") != "propose":
                break
            a = (rv.get("proposal") or {}).get("action")
            removed |= {a} | remove.get(a, set())
        out["passes"].append({"label": p.get("label"), "reviews": reviews})
    out["s"] = round(time.time() - t0, 3)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mem-mb", type=int, default=1536)
    a = ap.parse_args()
    _cap(a.mem_mb)
    out, sys.stdout = sys.stdout, sys.stderr     # anything the library prints goes to stderr, never into the result
    t0 = time.time()
    res = {"protocol": "wmtm-gc2-result-v1", "series": []}
    try:
        job = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        if job.get("protocol") != "wmtm-gc2-job-v1":
            raise ValueError("unknown job protocol")
        from goal_chainer.motivation import run_motivation_request
        from goal_chainer.requests import run_request
        from goal_chainer.runtime.budget import RunBudget
        res["versions"] = _versions()
        api = (run_request, run_motivation_request, RunBudget)
        for s in job.get("series") or ():
            try:
                res["series"].append(run_series(s, job["budget"], job["workdir"], api))
            except Exception as e:   # noqa: BLE001
                res["series"].append({"label": s.get("label"), "error": type(e).__name__ + ": " + str(e)[:300],
                                      "passes": []})
    except Exception as e:   # noqa: BLE001
        res["error"] = type(e).__name__ + ": " + str(e)[:300]
    res["s"] = round(time.time() - t0, 3)
    try:
        import resource
        res["maxrss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 1)
    except Exception:   # noqa: BLE001
        pass
    out.write(json.dumps(res))
    out.flush()


if __name__ == "__main__":
    main()
