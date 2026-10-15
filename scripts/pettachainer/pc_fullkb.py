#!/usr/bin/env python3
"""Track D: full seeded-rule KB + real-LLM atoms (replay) -> PeTTaChainer deduction, under a hard RSS cap.
Usage: <venv>/bin/python3 scripts/pc_fullkb.py --vendor .vendor36 [--exclude a,b] [--include a,b] [--max-rss-mb 2800]
Sanity gate: known-answer canary (Grace) through the same load path first; RSS watchdog os._exit(5)."""
import argparse, json, os, sys, time, threading
W = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ap = argparse.ArgumentParser()
ap.add_argument("--vendor", default=".vendor36")
ap.add_argument("--atoms", default=os.environ.get("PC_REPLAY_ATOMS", os.path.join(W, ".local-data/replay_atoms.json")),
                help="JSON {item_id: [atom,...]} of replayed parses; LOCAL ONLY (gitignored .local-data/), never commit real-memory atoms")
ap.add_argument("--neg", default=os.environ.get("PC_NEG_GOAL", "(Member grace robot)"), help="negative-control goal (must not be derivable)")
ap.add_argument("--seeded", default=os.environ.get("SEMPARSE_SEEDED", os.path.join(W, ".semparse-hitl/seeded_rules.metta")))
ap.add_argument("--include", default=""); ap.add_argument("--exclude", default="")
ap.add_argument("--max-rss-mb", type=int, default=2800)
ap.add_argument("--steps", type=int, default=30)
ap.add_argument("--no-atoms", action="store_true")
ap.add_argument("--goals", type=int, default=5)
ap.add_argument("--force-rejected", action="store_true", help="diagnostic: add_atom the adapter-rejected (Or-inside-And) atoms raw")
a = ap.parse_args()
sys.path.insert(0, os.path.join(W, a.vendor)); sys.path.insert(0, W)
def rss(): return int(open("/proc/self/status").read().split("VmRSS:")[1].split()[0]) // 1024
stage = ["init"]; peak = [0]
def wd():
    while True:
        time.sleep(0.1); m = rss(); peak[0] = max(peak[0], m)
        if m > a.max_rss_mb:
            print("ABORT rss %d MB > %d during %s" % (m, a.max_rss_mb, stage[0]), flush=True); os._exit(5)
threading.Thread(target=wd, daemon=True).start()
from pettachainer.pettachainer import PeTTaChainer
from wmtm import semparse_adapter as sp
MEM_INH = "(: mem_inh (Implication (Premises (Member $x $a) (Inheritance $a $b)) (Conclusions (Member $x $b))) (STV 1.0 0.99))"
inc = set(filter(None, a.include.split(","))); exc = set(filter(None, a.exclude.split(",")))
def q(h, c): return h.query("(: $prf %s $tv)" % c, steps=a.steps, timeout_sec=0)
def load_seeded(h):
    ok = bad = 0; names = []
    for src, node, err in sp.split_toplevel(open(a.seeded).read() + "\n" + MEM_INH):
        if err or sp.check_statement(node): bad += 1; continue
        if inc and node[1] not in inc: continue
        if node[1] in exc: continue
        for n in sp.normalise(node):
            stage[0] = "seed " + node[1]
            try: h.add_atom(sp.to_str(n)); ok += 1; names.append(node[1])
            except Exception: bad += 1
    return ok, bad, names
t0 = time.time()
# canary
h = PeTTaChainer(); load_seeded(h)
for x in ["(: cf (Member grace pilot) (STV 1.0 0.99))", "(: cg (Inheritance pilot person) (STV 1.0 0.99))"]: h.add_atom(x)
stage[0] = "canary"; r = q(h, "(Member grace person)"); neg = q(h, "(Member grace robot)")
print("CANARY (Member grace person) ->", str(r)[:200], "| neg ->", neg, "| rss", rss(), flush=True)
if "(Member grace person)" not in str(r) or neg: print("CANARY FAILED"); sys.exit(3)
del h
h = PeTTaChainer(); ok, bad, names = load_seeded(h)
print("seeded loaded=%d failed=%d distinct_rules=%d rss=%d MB" % (ok, bad, len(set(names)), rss()), flush=True)
saved = json.load(open(a.atoms)); allacc = []
if not a.no_atoms:
    for k, atoms in saved.items():
        pre = sp.safe_id(k)
        txt = "\n".join(x.replace(pre + "__", "").replace("__" + pre, "") for x in atoms)
        ad = sp.SemParseAdapter(lambda s, u, t=txt: t, loader=h, reject_log="/tmp/pc_fullkb_rejects.jsonl")
        stage[0] = "atoms " + k; r = ad.parse_item(k, "REPLAY")
        allacc += r.accepted
        print("item %s accepted=%d rejected=%d rss=%d" % (k, len(r.accepted), len(r.rejected), rss()), flush=True)
if a.force_rejected:
    for line in open("/tmp/pc_fullkb_rejects.jsonl"):
        r = json.loads(line)
        if "Or inside And" in r["reason"]:
            stage[0] = "forced " + r["atom"][:60]; h.add_atom(r["atom"])
            print("FORCED rejected atom loaded rss=%d" % rss(), flush=True)
nodes = [sp.parse_one(sp.tokenize(s), 0)[0][2] for s in allacc]
mem = [c for c in nodes if c[0] == "Member" and len(c) == 3]
inh = [c for c in nodes if c[0] == "Inheritance" and len(c) == 3]
asserted = {sp.to_str(c) for c in nodes}; seen = set(); goals = []
for m in mem:
    for i in inh:
        if m[2] == i[1]: goals.append(["Member", m[1], i[2]])
goals = [g for g in goals if sp.to_str(g) not in asserted and not (sp.to_str(g) in seen or seen.add(sp.to_str(g)))]
print("atoms=%d goals=%d load_s=%.1f rss=%d" % (len(allacc), len(goals), time.time() - t0, rss()), flush=True)
derived = 0
for g in goals[:a.goals]:
    stage[0] = "query " + sp.to_str(g); t = time.time(); r = q(h, sp.to_str(g))
    derived += bool(r)
    print("QUERY %s -> %s  [%.1fs rss=%d peak=%d]" % (sp.to_str(g), str(r)[:260], time.time() - t, rss(), peak[0]), flush=True)
stage[0] = "neg"; r = q(h, a.neg)
print("NEG", a.neg, "->", r, flush=True)
print("SUMMARY vendor=%s rules=%d atoms=%d derived=%d/%d peak_rss=%d MB time=%.0fs" % (
    a.vendor, len(set(names)), len(allacc), derived, min(len(goals), a.goals), peak[0], time.time() - t0), flush=True)
