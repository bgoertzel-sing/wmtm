#!/usr/bin/env python3
"""Per-case table from build.json + shadow.jsonl (one arm dir).  -> results.json in the arm dir; markdown on stdout."""
import json, os, re, sys
E = sys.argv[1]
b = json.load(open(os.path.join(E, "build.json")))
sh = [json.loads(l) for l in open(os.path.join(E, "shadow.jsonl")) if l.strip()][-1]
q = {r["goal"]: r for r in sh.get("queries") or []}
out = {"status": sh.get("status"), "canary_ok": (sh.get("canary") or {}).get("ok"), "neg_proved": (sh.get("neg") or {}).get("ok"),
       "goals_n": sh.get("goals_n"), "proved": sh.get("pc_proved"), "timeouts": sh.get("timeouts"), "add_fail": sh.get("add_fail"),
       "pred_fail": sh.get("pred_fail"), "steps": sh.get("steps"), "cases": []}
def short(s):
    return re.sub(r"__ep_note_20991117T0000(\d\d)Z", r"@\1", s or "")
print("status=%s canary_ok=%s neg_proved=%s goals=%s proved=%s timeouts=%s add_fail=%s pred_fail=%s steps=%s\n" % (
    out["status"], out["canary_ok"], out["neg_proved"], out["goals_n"], out["proved"], out["timeouts"], out["add_fail"], out["pred_fail"], out["steps"]))
print("| case | note implication (vars kept / skolems inside) | note-impl goal | asked | proved | STV | proof |")
print("|---|---|---|---|---|---|---|")
for c in b["cases"]:
    impl = "; ".join("%s vars=%s sk=%s goals=%d" % (i["kind"], ",".join(i["variables"]) or "-", ",".join(short(x) for x in i["skolem_symbols_inside"]) or "-", len(i["goals"]))
                     for i in c["note_implications"]) or "none (no Implication atom)"
    rows = []
    for a in c["asked"]:
        r = q.get(a["goal"]) if a["goal"] else None
        rows.append({"goal": a["goal"], "note_impl_goal": a["note_impl_goal"], "rule_goal": a["rule_goal"], "stated": a["stated"],
                     "asked": bool(r), "proved": bool(r and r["ok"]), "stv": (r or {}).get("stv"), "timeout": (r or {}).get("timeout"),
                     "prior": (r or {}).get("prior"), "proof": (r or {}).get("proof")})
        print("| %s | %s | %s | %s | %s | %s | %s |" % (c["case"], impl, "yes" if a["note_impl_goal"] else "no", short(a["goal"]) or "(no symbol)",
              "yes" if rows[-1]["proved"] else ("timeout" if rows[-1]["timeout"] else "no"), rows[-1]["stv"] or "-",
              short(rows[-1]["proof"] or ("prior only: " + short(rows[-1]["prior"]) if rows[-1]["prior"] else "-"))[:300].replace("|", "/")))
    for g, why in b["note_impl_goals"].items():
        if c["doc"].replace("-", "_") in why.replace("-", "_") and g not in [a["goal"] for a in c["asked"]]:
            r = q.get(g) or {}
            rows.append({"goal": g, "note_impl_goal": True, "asked": bool(r), "proved": bool(r.get("ok")), "stv": r.get("stv"), "proof": r.get("proof")})
            print("| %s | (extra note-impl goal) | yes | %s | %s | %s | %s |" % (c["case"], short(g), "yes" if r.get("ok") else "no", r.get("stv") or "-", short(r.get("proof") or "-")[:300]))
    out["cases"].append({"case": c["case"], "implications": c["note_implications"], "asked": rows})
out["note_impl_stats"] = b["note_impl_stats"]
json.dump(out, open(os.path.join(E, "results.json"), "w"), indent=1)
print("\nnote_impl stats: " + json.dumps({k: v for k, v in b["note_impl_stats"].items() if not isinstance(v, dict)}))
