"""Goal lifecycle replay + rating export (log only, offline).

Usage: python scripts/goal_lifecycle_replay.py --proposals COPY/proposals.jsonl --journal COPY/journal.metta
       --out DIR [--since 2026-10-19] [--until 2026-10-30] [--cutoff 2026-10-23T17:13Z] [--git-repo PATH]
Writes into --out (keep it OUTSIDE git: rows hold chat-derived text):
  report.json / report.md  counts before vs after dedup + lifecycle, split at --cutoff (rc2 live), people vs self
  dropped.csv              every dropped proposal: ts, engine id, goal id, state, reason
  goals.json               goal records (id, merged engine ids, state at end, reason)
  rating_sheet.csv / .md   goals still open at the end, one row each, for humans to rate
Nothing here touches the live worker, flags or prompt.
"""
import argparse, calendar, csv, datetime, json, os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wmtm.goals import needs, lifecycle as L  # noqa: E402

RATINGS = "approve / reject / already done / wrong"


def _ts(s):
    s = s.rstrip("Z")
    fmt = "%Y-%m-%dT%H:%M" if "T" in s else "%Y-%m-%d"
    return float(calendar.timegm(time.strptime(s, fmt)))


def _iso(t):
    return datetime.datetime.utcfromtimestamp(t).strftime("%Y-%m-%dT%H:%MZ")


def journal_notes(path):
    from goals_replay import notes   # same EventNote parser as the Track R replay
    return notes(path)


def git_notes(repo):
    """Commit subjects as closure sources: (id 'commit:<sha>', ts, subject)."""
    out = subprocess.run(["git", "-C", repo, "log", "--all", "--format=%h %ct %s"], capture_output=True, text=True,
                         check=True).stdout
    res = []
    for line in out.splitlines():
        sha, ct, subj = line.split(" ", 2)
        res.append(("commit:" + sha, float(ct), subj))
    return res


def replay(props, notes, since=None, until=None, cutoff=None):
    later = [(t, [needs.sentence_digest(s) for s in needs.sentences(c)]) for _i, t, c in notes]
    lc = L.Lifecycle(notes, needs.common_terms(later))
    rows = []
    for p in sorted(props, key=lambda r: r["ts"]):
        if (since and p["ts"] < since) or (until and p["ts"] >= until):
            continue
        v = lc.observe(p)
        rows.append({"ts": p["ts"], "when": _iso(p["ts"]), "phase": "post-rc2" if cutoff and p["ts"] >= cutoff else
                     "pre-rc2", "engine_id": p.get("id"), "gid": v["gid"], "action": p.get("action"),
                     "kind": "person" if p.get("action") == "RemindPending" else "self", "who": p.get("who"),
                     "keep": v["keep"], "state": v["state"], "reason": v["reason"], "items": p.get("items") or []})
    end = rows[-1]["ts"] if rows else time.time()
    goals = []
    for g in lc.goals:
        st, why = lc.state_at(g, end)
        goals.append({"gid": g["gid"], "who": g["who"], "action": g["action"], "engine_ids": g["engine_ids"],
                      "merges": g["merges"], "state": st, "why": why, "items": g["items"], "text": L.body(g["text"])})
    return rows, goals


def counts(rows):
    out = {}
    for ph in ("pre-rc2", "post-rc2", "all"):
        for kind in ("person", "self", "all"):
            sel = [r for r in rows if (ph == "all" or r["phase"] == ph) and (kind == "all" or r["kind"] == kind)]
            out["%s/%s" % (ph, kind)] = {"before": len(sel), "distinct_engine_ids": len({r["engine_id"] for r in sel}),
                                         "after": sum(r["keep"] for r in sel),
                                         "distinct_goals_after": len({r["gid"] for r in sel if r["keep"]})}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proposals", required=True); ap.add_argument("--journal", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--since", default=""); ap.add_argument("--until", default="")
    ap.add_argument("--cutoff", default="2026-10-23T17:13Z", help="rc2 live (2026-10-23 10:13 PDT)")
    ap.add_argument("--git-repo", action="append", default=[], help="commit subjects count as closure sources")
    a = ap.parse_args()
    props = [json.loads(l) for l in open(a.proposals) if l.strip()]
    notes = journal_notes(a.journal)
    for repo in a.git_repo:
        notes += git_notes(repo)
    notes.sort(key=lambda x: x[1])
    rows, goals = replay(props, notes, _ts(a.since) if a.since else None, _ts(a.until) if a.until else None,
                        _ts(a.cutoff))
    os.makedirs(a.out, exist_ok=True)
    c = counts(rows)
    by_reason = {}
    for r in rows:
        if not r["keep"]:
            k = r["reason"].split(" ")[0].split(":")[0]
            by_reason[k] = by_reason.get(k, 0) + 1
    rep = {"rules": {"MERGE_JACCARD": L.MERGE_JACCARD, "COVER": L.COVER, "SAT_MIN": L.SAT_MIN, "SAT_FRAC": L.SAT_FRAC,
                     "STALE_DAYS": L.STALE_DAYS}, "since": a.since, "until": a.until, "cutoff": a.cutoff,
           "notes": len(notes), "counts": c, "dropped_by_reason": by_reason,
           "goal_states_at_end": {s: sum(g["state"] == s for g in goals) for s in ("open", "satisfied", "superseded",
                                                                                   "stale")}}
    json.dump(rep, open(os.path.join(a.out, "report.json"), "w"), indent=1)
    json.dump(goals, open(os.path.join(a.out, "goals.json"), "w"), indent=1)
    with open(os.path.join(a.out, "dropped.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["when", "phase", "kind", "engine_id", "goal_id", "state", "reason"])
        for r in rows:
            if not r["keep"]:
                w.writerow([r["when"], r["phase"], r["kind"], r["engine_id"], r["gid"], r["state"], r["reason"]])
    with open(os.path.join(a.out, "kept.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["when", "phase", "kind", "engine_id", "goal_id"])
        for r in rows:
            if r["keep"]:
                w.writerow([r["when"], r["phase"], r["kind"], r["engine_id"], r["gid"]])
    openg = [g for g in goals if g["state"] == "open"]
    with open(os.path.join(a.out, "rating_sheet.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["goal_id", "who", "action", "goal", "source_note", "rating (%s)" % RATINGS,
                                        "comment"])
        for g in openg:
            w.writerow([g["gid"], g["who"], g["action"], g["text"][:200], " ".join(g["items"]), "", ""])
    with open(os.path.join(a.out, "rating_sheet.md"), "w") as fh:
        fh.write("# Open goals to rate (%s)\n\nRate each row: %s.\n\n| # | goal id | who | goal | source note | rating |\n"
                 "|---|---|---|---|---|---|\n" % (_iso(rows[-1]["ts"]) if rows else "-", RATINGS))
        for n, g in enumerate(openg, 1):
            fh.write("| %d | %s | %s | %s | %s | |\n" % (n, g["gid"], g["who"], g["text"][:160].replace("|", "/"),
                                                     " ".join(g["items"])))
    with open(os.path.join(a.out, "report.md"), "w") as fh:
        fh.write("# Goal lifecycle replay\n\nwindow %s .. %s, rc2 cutoff %s, %d notes\n\n" % (
            a.since or "start", a.until or "end", a.cutoff, len(notes)))
        fh.write("| phase/kind | before | distinct engine ids | after | distinct goals after |\n|---|---|---|---|---|\n")
        for k, v in c.items():
            fh.write("| %s | %d | %d | %d | %d |\n" % (k, v["before"], v["distinct_engine_ids"], v["after"],
                                                     v["distinct_goals_after"]))
        fh.write("\nDropped by reason: %s\n\nGoal states at end: %s\n\n## Goals\n\n" % (
            json.dumps(by_reason), json.dumps(rep["goal_states_at_end"])))
        for g in goals:
            fh.write("- %s %s %s: %s | merged %s | %s\n" % (g["gid"], g["who"], g["state"], g["why"] or "-",
                                                         ",".join(g["engine_ids"]), g["text"][:90]))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
