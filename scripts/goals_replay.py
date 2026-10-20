"""Track R offline replay: run the goal adapter over COPIES of a bot's journal (and semparse cache) day by day.

Usage: python scripts/goals_replay.py --journal COPY/journal.metta [--semparse COPY/semparse_cache] --since 2026-10-05
       --until 2026-10-19 --out .local-data/track_r  (gitignored; real notes never go into git)
Per replay day D: the active set = the notes from the window_days before the end of D (STI by recency), now = end of D.
Per-unit checks: the goal canary must pass before anything runs; each proposal passes engine.check_proposal.
"""
import argparse, calendar, csv, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wmtm.goals import engine

NOTE = re.compile(r'\(EventNote ev-(ep-note-(\d{8}T\d{6})Z) "((?:[^"\\]|\\.)*)"\)')


def notes(path):
    txt = open(path, encoding="utf-8", errors="replace").read()
    out = {}
    for m in NOTE.finditer(txt):
        ts = calendar.timegm(time.strptime(m.group(2), "%Y%m%dT%H%M%S"))
        out[m.group(1)] = (ts, m.group(3).replace('\\"', '"').replace("\\n", "\n"))
    return sorted(((i, t, c) for i, (t, c) in out.items()), key=lambda x: x[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--journal", required=True); ap.add_argument("--semparse", default="")
    ap.add_argument("--since", required=True); ap.add_argument("--until", required=True)
    ap.add_argument("--window-days", type=float, default=3.0); ap.add_argument("--k", type=int, default=60)
    ap.add_argument("--out", required=True); ap.add_argument("--goalchainer-src", default=""); ap.add_argument("--flags", default="", help="copy of _wmtm_flags.json (speaker_map)")
    ap.add_argument("--requests", default="", help="R2: request history jsonl {ts, who, text} (local copy only)")
    a = ap.parse_args()
    cfg = {"goalchainer": True, "goalchainer_src": a.goalchainer_src, "semparse_dir": a.semparse,
           "speaker_map": (json.load(open(a.flags)).get("speaker_map") or {}) if a.flags else {},
           "speaker_self": (json.load(open(a.flags)).get("speaker_self") or "") if a.flags else "",
           "goal_requests": [json.loads(l) for l in open(a.requests)] if a.requests else []}
    can = engine.goal_canary(cfg)
    if not can.get("ok"):
        sys.exit("goal canary failed: %r" % can)
    ns = notes(a.journal)
    t0 = calendar.timegm(time.strptime(a.since, "%Y-%m-%d")); t1 = calendar.timegm(time.strptime(a.until, "%Y-%m-%d")) + 86400
    os.makedirs(a.out, exist_ok=True)
    seen, rows, days, hist = {}, [], [], []
    q = engine.cached_queries(cfg, {i for i, _, _ in ns}) if a.semparse else {}
    for day in range(int(t0), int(t1), 86400):
        now = day + 86400
        win = [(i, t, c) for i, t, c in ns if now - a.window_days * 86400 <= t < now][-a.k:]
        if not win:
            continue
        raw = [{"id": i, "content": c, "sti": 0.2 + 0.8 * (t - (now - a.window_days * 86400)) / (a.window_days * 86400),
                "source_type": "recalled", "origin_ts": t, **({"queries": q[i]} if i in q else {})} for i, t, c in win]
        r = engine.propose(raw, cfg, {"autonomous": False, "recent": set(seen), "history": list(hist)}, now=now)
        bad = [p for p in r["proposals"] if engine.check_proposal(p)]
        assert not bad, bad
        days.append({"day": time.strftime("%Y-%m-%d", time.gmtime(day)), "notes": len(win), "needs": r["needs"],
                     "candidates": len(r["candidates"]), "vetoed": len(r["vetoed"]), "proposed": len(r["all_proposed"]),
                     "logged": 0, "deontic_impl": r["deontic_impl"], "suppressed": len(r.get("suppressed") or ())})
        for p in r["proposals"]:
            if p["id"] in seen:
                continue
            seen[p["id"]] = 1; days[-1]["logged"] += 1
            hist.append({"ts": now, "who": p.get("who"), "topic": p.get("topic") or [], "action": p["action"]})
            rows.append(dict(day=days[-1]["day"], **{k: p[k] for k in engine.FIELDS}, who=p.get("who"),
                             topic=p.get("topic")))
    with open(os.path.join(a.out, "proposals.jsonl"), "w") as fh:
        for x in rows:
            fh.write(json.dumps(x) + "\n")
    with open(os.path.join(a.out, "days.jsonl"), "w") as fh:
        for x in days:
            fh.write(json.dumps(x) + "\n")
    print(json.dumps({"canary": can, "notes": len(ns), "days": len(days), "proposals": len(rows)}))


if __name__ == "__main__":
    main()
