#!/usr/bin/env python3
"""P4 rev3+rev4 evidence check. Run from this dir inside the wmtm repo checkout of hive/t-2026-11-05-p4-latest."""
import json, os, re, subprocess, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
ok = True
def chk(name, cond, info=""):
    global ok; ok &= bool(cond); print("PASS" if cond else "FAIL", name, info)
def git(*a): return subprocess.run(["git", *a], capture_output=True, text=True).stdout
def last(p): return json.loads(open(p).read().strip().splitlines()[-1])
root = git("rev-parse", "--show-toplevel").strip()
rc = open(os.path.join(root, "wmtm/runtime_config.py")).read()
chk("F2 pin: runtime_config pettachainer_dir default bdae8d7e", '"pettachainer-bdae8d7e"' in rc)
chk("F2 pin: vendor_runtime.sh PC_PIN=bdae8d7e", re.search(r"PC_PIN=bdae8d7e", open(os.path.join(root, "scripts/vendor_runtime.sh")).read()))
chk("F2 pin: hitl PIN default f44d7b74", re.search(r'^PIN = "f44d7b74', open(os.path.join(root, "wmtm/semparse_catalog.py")).read(), re.M))
chk("F2 pin: PETTA_PIN.md names 3681b9b", "3681b9b" in open(os.path.join(root, "PETTA_PIN.md")).read())
n = len([l for l in git("-C", root, "grep", "-n", "STOPGAP(upstream: F7)", "HEAD", "--", ".", ":!reports", ":!docs/STOPGAPS.md").splitlines() if l])
chk("F3: 0 STOPGAP(upstream: F7) markers outside reports/", n == 0, "n=%d" % n)
ps = open(os.path.join(root, "wmtm/pc_shadow.py")).read()
chk("F1: rule_goal_pool defined and called in snapshot", ps.count("rule_goal_pool(") >= 2)
chk("F1: real-engine parsed-note test exists", "def test_parsed_note_chains_on_real_engine" in open(os.path.join(root, "tests/test_p4_rule_goals.py")).read())
t = open("rev3/gates/pytest_p4_rev3.txt").read()
chk("F1: P4 rev3 subset 5 passed incl. real-engine test", "5 passed" in t and "test_parsed_note_chains_on_real_engine PASSED" in t)
f = open("rev3/gates/pytest_full.log").read().strip().splitlines()[-1]
chk("gates: full suite 0 failed", "failed" not in f and "passed" in f, f.strip("= "))
for p, lab in (("rev3/bdae8d7e/shadow_B.jsonl", "10 s"), ("rev3/bdae8d7e_default_t2/shadow_B_t2.jsonl", "default 2 s")):
    r = last(p); q = r["queries"]; pr = sum(x["ok"] for x in q)
    chk("B %s run: status ok, canary ok, negative not proved, 12/13" % lab,
        r["status"] == "ok" and r["canary"]["ok"] and not r["neg"]["ok"] and len(q) == 13 and pr == 12,
        "status=%s %d/%d" % (r["status"], pr, len(q)))
pk = [l for l in open("rev3/PROOF_KINDS.md") if l.startswith("| B |")]
ac = sum("antecedent completion" in l for l in pk); npk = sum("NOT PROVED" in l for l in pk)
chk("F3: PROOF_KINDS lists all 13 B goals: 12 antecedent completion, 1 not proved, 0 direct", len(pk) == 13 and ac == 12 and npk == 1 and not any("| direct |" in l for l in pk), "rows=%d ac=%d np=%d" % (len(pk), ac, npk))
jb = open("rev3/B_W4_JUDGMENTS_bdae8d7e.md").read()
cb, wb = len(re.findall(r"\| CORRECT", jb)), len(re.findall(r"\| WRONG", jb))
chk("F3: B judgments 10 CORRECT / 2 WRONG (B_W4_JUDGMENTS_bdae8d7e.md)", (cb, wb) == (10, 2), "%d/%d" % (cb, wb))
a = json.load(open("rev3/A_W1234.json"))
ca, wa = (len(a["correct"]), len(a["wrong"])) if isinstance(a["correct"], list) else (a["correct"], a["wrong"])
chk("A/B criterion correct(B)>=correct(A) and wrong(B)<=wrong(A)", cb >= ca and wb <= wa, "A %d/%d B %d/%d" % (ca, wa, cb, wb))
chk("F6: semparse_rules drops Equivalence", "Equivalence dropped" in ps)
chk("F6: hitl LICENSE fixture in repo", "tests/fixtures/hitl_licence/LICENSE" in git("-C", root, "ls-files", "tests/fixtures").split())
# --- P4 rev4 (review 3 findings 1-5) ---
bad = []
for dp, _, fs in os.walk("."):
    for fn in fs:
        if fn.endswith((".json", ".jsonl")):
            if '"content"' in open(os.path.join(dp, fn), errors="ignore").read(): bad.append(os.path.join(dp, fn))
chk("R3-F1: no \"content\" key in any report json/jsonl", not bad, ",".join(bad[:3]))
chk("R3-F1: no raw_spec.json tracked", "raw_spec" not in git("-C", root, "ls-files", "reports"))
pk4 = [l for l in open("rev4/PROOF_KINDS.md") if l.startswith("| (")]
chk("R3-F2: rev4 PROOF_KINDS has 13 B rows, none called antecedent completion", len(pk4) == 13 and not any("antecedent completion" in l for l in pk4), "rows=%d" % len(pk4))
def okn(v): q = last("rev4/nwdef_ab/%s/shadow.jsonl" % v)["queries"]; return sum(x["ok"] for x in q), len(q)
chk("R3-F2: nwdef A/B runs present (full, nonwdef 12/13; min_nw, min_no 1/1)", okn("full") == (12, 13) and okn("nonwdef") == (12, 13) and okn("min_nw") == (1, 1) and okn("min_no") == (1, 1))
w = json.load(open("rev4/w123/B_W123.json"))
chk("R3-F3: B W1-W3 recorded for 12 proved goals, 0 flagged", len(w) == 12 and not any(x["W1"] or x["W2"] or x["W3"] for x in w))
d = json.load(open("rev4/ab/AB_DIFF_rev4.json"))
chk("R3-F3: rev4 AB diff has a reason per row, none 'B pool 0'", d and all(x.get("why") for x in d) and not any("B pool 0" in x["why"] for x in d), "rows=%d" % len(d))
uo = open("rev4/UPSTREAM_OVERLAP.md").read()
chk("R3-F4: UPSTREAM_OVERLAP covers PC3 and R1-R8", all(("| %s" % k) in uo for k in ("PC3", "R2", "R3", "R4", "R5", "R6", "R7", "R8")))
chk("R3-F4: STOPGAP(upstream: PC-EQ1) marker in code and STOPGAPS.md", "STOPGAP(upstream: PC-EQ1" in ps and "PC-EQ1" in open(os.path.join(root, "docs/STOPGAPS.md")).read())
f4 = open("rev4/gates/pytest_full.log").read().strip().splitlines()[-1]
chk("R3-F5: rev4 full suite 0 failed", "failed" not in f4 and "passed" in f4, f4.strip("= "))
if os.path.exists("SHA256SUMS"):
    r = subprocess.run(["sha256sum", "--quiet", "-c", "SHA256SUMS"], capture_output=True, text=True)
    chk("SHA256SUMS verify", r.returncode == 0, r.stdout[-300:])
print("RESULT", "ALL PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
