#!/usr/bin/env python3
"""t-2026-11-12-wmtm-sentence-reasoning: judge and recompute from the evidence folder only.  Prints ids and counts only.

Usage (from the repo root):  python3 reports/t-2026-11-12-wmtm-sentence-reasoning/tools/recompute.py [EVIDENCE_DIR] [--tsv OUT]
EVIDENCE_DIR defaults to /var/tmp/hive-evidence-t-2026-11-12-wmtm-sentence-reasoning.

Per run (<set>_<parse>_<induction flag>, set M17 = s1's 17 complete notes, P5 = s3's 5 pilot notes, P4 = s2's 4
complete pilot notes; parse s1/s2/s3 = sentence stores = B, r1/r2/r3 = whole-note stores = A):
 - every proved conclusion (admit.json results) gets an id g_<sha256(goal)[:10]>, premise ids (sp labels in the proof),
   source note ids, the reader's trivial reason (pc_admit.trivial_reason, the trivial filter), and a verdict:
   mechanical W1 (premises from >1 note plus an sk_ fact, DEVIATION_1 nwdef join kept, v2 rule: an identical
   class-level fact in two notes is NOT W1), W2, W3 (judge_v2), else the F3 v3 W4 table, else hand_verdicts.json;
 - C/W/U, trivial / non-trivial, W1 count; the A/B count rule (B C >= A C and B W <= A W) for each sentence parse
   against each whole-note parse on the same notes, before and after the trivial filter;
 - the reader replay (pc_admit.load_candidates, default config: trivial filter on, cap reasoner_max_admit=5);
 - Mesto s11: every A conclusion the B parse on the same notes does not prove, with the reason.
Also checks SHA256SUMS and the 0-parse-call evidence."""
import json, os, re, sys, hashlib, glob, collections, tempfile, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, REPO); sys.path.insert(0, os.path.join(REPO, "reports", "t-2026-11-10-wmtm-normaliser-v2", "tools"))
import judge_v2 as J
from wmtm import pc_admit as P
from wmtm import runtime_config as rc
_av = sys.argv[1:]
args = [a for i, a in enumerate(_av) if not a.startswith("--") and not (i > 0 and _av[i - 1] == "--tsv")]
EV = args[0] if args else "/var/tmp/hive-evidence-t-2026-11-12-wmtm-sentence-reasoning"
TSV = sys.argv[sys.argv.index("--tsv") + 1] if "--tsv" in sys.argv else None
W4 = json.load(open(os.path.join(REPO, "reports", "t-2026-11-10-wmtm-narrow-preload", "evidence", "W4_f3v3.json")))
HAND = json.load(open(os.path.join(EV, "hand_verdicts.json")))
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
gid = lambda g: "g_" + hashlib.sha256(g.encode()).hexdigest()[:10]
ok = True
# ---- SHA256SUMS
bad = 0; n_sum = 0
for line in open(os.path.join(EV, "SHA256SUMS")):
    h, p = line.rstrip("\n").split("  ", 1); n_sum += 1
    if sha(os.path.join(EV, p)) != h: bad += 1; print("SHA MISMATCH", p)
print("SHA256SUMS files", n_sum, "mismatches", bad); ok &= bad == 0
# ---- 0 parse calls
pc = json.load(open(os.path.join(EV, "parse_calls.json")))
live = sum(len(os.listdir(d)) for d in glob.glob(os.path.join(EV, "runs", "*", "no_live_cache")) if os.path.isdir(d))
print("parse calls: v3 call log lines before", pc["before"]["lines"], "after", pc["after"]["lines"], "same sha",
      pc["before"]["sha256"] == pc["after"]["sha256"], "| new calls", pc["after"]["lines"] - pc["before"]["lines"],
      "| live parse-cache files in runs", live, "| refusal stubs hit", pc.get("stub_hits", 0))
ok &= pc["after"]["lines"] == pc["before"]["lines"] and pc["before"]["sha256"] == pc["after"]["sha256"] and live == 0
# ---- per run
def extract(d):
    s = json.load(open(os.path.join(d, "spec.json")))
    src = s["atom_src"] if isinstance(s["atom_src"], dict) else dict(s["atom_src"])
    prem = {}
    for a in s["atoms"]:
        m = re.match(r"\(: (\w+) (\(.*\)) \(STV", a)
        if m and m.group(1) in src: prem[m.group(1)] = {"src": src[m.group(1)], "fact": m.group(2)}
    rej = sorted({x["fact"] for x in (s.get("gate") or {}).get("decisions", []) if x.get("action") == "reject"})
    nw = {}
    for a in s["atoms"]:
        for sym in set(re.findall(r"\b(\w+?__nw_[0-9a-f]+)\b", a)):
            m = re.match(r"\(: (\w+) ", a)
            if m and m.group(1) in src: nw.setdefault(sym, set()).add(src[m.group(1)])
    return {"shadow": os.path.join(d, "shadow.jsonl"), "premises": prem, "gate_rejected": rej,
            "nw_symbol_notes": {x: sorted(v) for x, v in nw.items()}}, s
runs = {}
for d in sorted(glob.glob(os.path.join(EV, "runs", "*"))):
    name = os.path.basename(d); e, spec = extract(d)
    _, v = J.judge(e, W4, True)
    rec = json.loads(open(e["shadow"]).read().strip().splitlines()[-1])
    a = json.load(open(os.path.join(d, "admit.json")))
    rows = []
    for x in a["results"]:
        g = x["goal"]; vv, why = v.get(g, ("UNJUDGED", "-"))
        hv = HAND.get(gid(g)); unc = False
        if vv == "UNJUDGED" and hv: vv, unc, why = hv["verdict"], bool(hv.get("uncertain")), "hand"
        prem = sorted(set(re.findall(r"\bsp\d+\b", x["proof"])))
        rows.append({"id": gid(g), "verdict": vv, "basis": why, "uncertain": unc,
                     "trivial": P.trivial_reason(x["proof"], x.get("rules")) or "", "sources": sorted(set(x.get("sources") or [])),
                     "premises": prem, "w1": why == "W1"})
    # reader replay: default config, trivial filter on, cap 5
    t = tempfile.mkdtemp(); shutil.copy(os.path.join(d, "admit.json"), t + "/admit.json")
    cfg = dict(rc.resolve(environ={})); cfg["shadow_dir"] = t; cfg["reasoner_max_admit_age_s"] = 10 ** 12; cfg["reasoner_max_age_s"] = 10 ** 12
    c, info = P.load_candidates(cfg, None, now=float(a.get("spec_ts") or a.get("ts")) + 1,
                                live_ids=sorted({s_ for x in a["results"] for s_ in (x.get("sources") or [])}))
    shutil.rmtree(t)
    runs[name] = {"rows": rows, "goals_n": rec.get("goals_n"), "proved": rec.get("pc_proved"), "canary": (rec.get("canary") or {}).get("ok"),
                  "timeouts": rec.get("timeouts"), "facts": rec.get("facts"), "atoms": rec.get("atoms"), "notes": spec.get("items") if isinstance(spec.get("items"), int) else len(spec.get("items") or []),
                  "admitted": len(c or []), "trivial_refused": info.get("trivial_refused_n"), "filter": info.get("trivial_filter"),
                  "cap": cfg.get("reasoner_max_admit"), "goal_ids": sorted({r["id"] for r in rows})}
def counts(rows):
    k = collections.Counter(r["verdict"] for r in rows)
    return {"C": k["CORRECT"], "W": k["WRONG"], "U": k["UNCLEAR"], "unj": k["UNJUDGED"],
            "triv": sum(1 for r in rows if r["trivial"]), "nontriv": sum(1 for r in rows if not r["trivial"]),
            "nontriv_C": sum(1 for r in rows if not r["trivial"] and r["verdict"] == "CORRECT"),
            "W1": sum(r["w1"] for r in rows), "unc": sum(r["uncertain"] for r in rows)}
print("run\tnotes\tgoals\tproved\tcanary\tC\tW\tU\tunjudged\ttrivial\tnon_trivial\tnon_trivial_C\tW1\tuncertain\tadmitted(filter on,cap)\ttrivial_refused")
for n, r in runs.items():
    c = counts(r["rows"])
    print("\t".join(map(str, [n, r["notes"], r["goals_n"], r["proved"], r["canary"], c["C"], c["W"], c["U"], c["unj"], c["triv"], c["nontriv"],
                              c["nontriv_C"], c["W1"], c["unc"], "%s (%s,%s)" % (r["admitted"], r["filter"], r["cap"]), r["trivial_refused"]])))
    ok &= r["canary"] is True and r["timeouts"] == 0 and c["unj"] == 0
# induction flag on/off must give the same conclusions (shadow_induction min 3)
same = all(runs[n]["goal_ids"] == runs[n.replace("_False", "_True")]["goal_ids"] for n in runs if n.endswith("_False"))
print("induction on (min3) vs off: identical conclusion sets in all pairs:", same)
print("\ncount rule (B sentence vs A whole-note, same notes; B C >= A C and B W <= A W), before / after the trivial filter")
for st, b in (("M17", "s1"), ("P5", "s3"), ("P4", "s2")):
    B_ = runs["%s_%s_False" % (st, b)]; cb = counts(B_["rows"])
    cb_after = counts([r for r in B_["rows"] if not r["trivial"]])
    for a_ in ("r1", "r2", "r3"):
        A_ = runs["%s_%s_False" % (st, a_)]; ca = counts(A_["rows"]); ca_after = counts([r for r in A_["rows"] if not r["trivial"]])
        rule = lambda x, y: "HOLDS" if (x["C"] >= y["C"] and x["W"] <= y["W"]) else "FAILS"
        print("%s %s vs %s: B %dC/%dW vs A %dC/%dW -> %s | after filter B %dC/%dW vs A %dC/%dW -> %s" % (
            st, b, a_, cb["C"], cb["W"], ca["C"], ca["W"], rule(cb, ca), cb_after["C"], cb_after["W"], ca_after["C"], ca_after["W"], rule(cb_after, ca_after)))
        # Mesto s11: A conclusions B does not prove, with reason
        bset = set(B_["goal_ids"]); bpool = set()
        sb = json.load(open(os.path.join(EV, "runs", "%s_%s_False" % (st, b), "spec.json")))
        bpool = {gid(g if isinstance(g, str) else g[0]) for g in sb.get("goals") or []}
        batoms = "\n".join(sb["atoms"])
        aadm = {gid(x["goal"]): x for x in json.load(open(os.path.join(EV, "runs", "%s_%s_False" % (st, a_), "admit.json")))["results"]}
        for r in A_["rows"]:
            if r["id"] in bset: continue
            g = aadm[r["id"]]["goal"]; sk = g.split()[1]
            why = ("in B goal pool, not proved" if r["id"] in bpool else
                   "not in B goal pool; entity symbol absent from the B store" if sk not in batoms else
                   "not in B goal pool; entity present, restriction statement absent or not recovered")
            print("   s11 drop %s (A %s, %s, trivial=%s): %s" % (r["id"], a_, r["verdict"], bool(r["trivial"]), why))
        for r in B_["rows"]:
            if r["id"] not in set(A_["goal_ids"]): print("   s11 B-only %s (%s, trivial=%s)" % (r["id"], r["verdict"], bool(r["trivial"])))
allB = [r for n, x in runs.items() if re.match(r"^(M17_s1|P5_s3|P4_s2)_False$", n) for r in x["rows"]]
key = [r["id"] for r in allB if not r["trivial"] and r["verdict"] == "CORRECT"]
print("\nKEY: B (sentence) conclusions that are non-trivial AND correct:", len(key), key)
newB = sorted({r["id"] for r in allB} - {i for n, x in runs.items() if re.search(r"_r[123]_False$", n) for i in x["goal_ids"]})
print("B conclusions not proved by any whole-note parse on the same note sets:", len(newB), newB)
if TSV:
    with open(TSV, "w") as fh:
        fh.write("run\tconclusion\tverdict\tbasis\tuncertain\ttrivial\tW1\tsource_notes\tpremise_ids\n")
        for n, x in runs.items():
            for r in x["rows"]:
                fh.write("\t".join([n, r["id"], r["verdict"], r["basis"], str(r["uncertain"]), r["trivial"] or "-", str(r["w1"]),
                                    ";".join(r["sources"]), ";".join(r["premises"])]) + "\n")
print("RECOMPUTE_OK" if ok else "RECOMPUTE_FAIL")
