"""rev2: one row per B run: goals, proved, canary, neg, induction goals with verdict, stv, sources, facts."""
import json, glob, os, sys
base = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "evidence", "runs_rev2")
print("\t".join(["run", "status", "goals", "proved", "canary_ok", "induction_goal", "proved_stv", "admitted", "sources", "facts"]))
for d in sorted(glob.glob(base + "/*")):
    s = json.load(open(d + "/spec.json")); a = json.load(open(d + "/admit.json"))
    ind = [g for g in s.get("goals", []) if g.startswith("(Inheritance")]
    q = {}
    for l in open(d + "/shadow.jsonl"):
        if l.strip():
            for x in json.loads(l).get("queries", []): q[x["goal"]] = x
    adm = {r["goal"]: r for r in a.get("results", [])}
    proved = sum(1 for x in q.values() if x.get("ok"))
    row = [os.path.basename(d), str(a.get("status")), str(len(s.get("goals", []))), str(proved), str(a.get("canary_ok"))]
    if not ind:
        print("\t".join(row + ["-", "-", "-", "-", "-"])); continue
    for g in ind:
        r = adm.get(g) or {}
        print("\t".join(row + [g, str((q.get(g) or {}).get("stv")), str(g in adm), ";".join(r.get("sources", [])), ";".join(r.get("facts", []))]))
