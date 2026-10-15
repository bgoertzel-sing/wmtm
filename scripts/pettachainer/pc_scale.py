#!/usr/bin/env python3
"""Track E scaling: full seeded KB (109 rules + mem_inh) + N atoms on a vendored PeTTaChainer, under RSS watchdog.
Atoms = replayed LLM parses from a LOCAL file (--atoms / $PC_REPLAY_ATOMS, default .local-data/replay_atoms.json, gitignored), accepted by semparse_adapter
plus SYNTHETIC copies of those same atoms with renamed symbols (same shapes, same relation heads):
  --mode disjoint : every non-head symbol renamed per copy (copy k: foo -> foo_ck) -> independent sub-KBs
  --mode shared   : only atom names + sk_* skolems renamed; class vocabulary shared (more candidate premises per goal)
Queries: the 8 real Member-x-Inheritance goals + up to 4 goals from the last synthetic copy + negative control.
Prints one JSON line: SCALE {...}.  Sanity gate: Grace canary first, through the same handle/rules."""
import argparse, json, os, sys, time, threading, statistics
W = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ap = argparse.ArgumentParser()
ap.add_argument("--vendor", default=".vendor36")
ap.add_argument("--atoms", default=os.environ.get("PC_REPLAY_ATOMS", os.path.join(W, ".local-data/replay_atoms.json")),
                help="JSON {item_id: [atom,...]} of replayed parses; LOCAL ONLY (gitignored .local-data/), never commit real-memory atoms")
ap.add_argument("--neg", default=os.environ.get("PC_NEG_GOAL", "(Member grace robot)"), help="negative-control goal (must not be derivable)")
ap.add_argument("--seeded", default=os.environ.get("SEMPARSE_SEEDED", os.path.join(W, ".semparse-hitl/seeded_rules.metta")))
ap.add_argument("--log-proofs", action="store_true", help="include proof terms in output (may contain local data; do not commit)")
ap.add_argument("--n", type=int, default=300)
ap.add_argument("--mode", default="disjoint", choices=["disjoint", "shared"])
ap.add_argument("--steps", type=int, default=30)
ap.add_argument("--max-rss-mb", type=int, default=3000)
ap.add_argument("--no-prune", action="store_true", help="disable bounded-agenda pruning")
ap.add_argument("--tail", type=int, default=0, help="diagnostic: after loading, add the first T real atoms renamed _c99 (T=10 = 3 induction/aggregation rules + facts)")
ap.add_argument("--real-goals", type=int, default=8)
ap.add_argument("--syn-goals", type=int, default=4)
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
def q(h, c): return h.query("(: $prf %s $tv)" % c, steps=a.steps, timeout_sec=0)
def load_seeded(h):
    n = 0
    for src, node, err in sp.split_toplevel(open(a.seeded).read() + "\n" + MEM_INH):
        if err or sp.check_statement(node): continue
        for x in sp.normalise(node): h.add_atom(sp.to_str(x)); n += 1
    return n
t0 = time.time()
h = PeTTaChainer(); load_seeded(h)
for x in ["(: cf (Member grace pilot) (STV 1.0 0.99))", "(: cg (Inheritance pilot person) (STV 1.0 0.99))"]: h.add_atom(x)
stage[0] = "canary"
if "(Member grace person)" not in str(q(h, "(Member grace person)")) or q(h, "(Member grace robot)"):
    print("CANARY FAILED", flush=True); sys.exit(3)
del h
# real atoms via the adapter (no loader: collect accepted strings only)
real = []
for k, atoms in json.load(open(a.atoms)).items():
    pre = sp.safe_id(k); txt = "\n".join(x.replace(pre + "__", "").replace("__" + pre, "") for x in atoms)
    r = sp.SemParseAdapter(lambda s, u, t=txt: t, loader=None, reject_log="/tmp/pc_scale_rejects.jsonl").parse_item(k, "REPLAY")
    real += r.accepted
def isnum(s):
    try: float(s); return True
    except ValueError: return False
def ren(node, k, top=False):
    if isinstance(node, str):
        if node.startswith("$") or node.startswith('"') or isnum(node): return node
        if a.mode == "shared" and not node.startswith("sk_"): return node
        return "%s_c%d" % (node, k)
    out = [node[0] if isinstance(node[0], str) else ren(node[0], k)]
    if out[0] == "STV": return node
    return out + [ren(x, k) for x in node[1:]]
def copy(s, k):
    n = sp.parse_one(sp.tokenize(s), 0)[0]
    return sp.to_str([n[0], "%s_c%d" % (n[1], k), ren(n[2], k), n[3]])
atoms = list(real); k = 0
while len(atoms) < a.n:
    k += 1; atoms += [copy(s, k) for s in real]
atoms = atoms[:a.n]; n_real = min(len(real), a.n); n_syn = len(atoms) - n_real
h = PeTTaChainer()
if a.no_prune: print("PRUNE-OFF", h.handler.process_metta_string("!(set-bounded-agenda-pruning false)"), flush=True)
stage[0] = "seed"; t = time.time(); nr = load_seeded(h); seed_s = time.time() - t
stage[0] = "atoms"; t = time.time(); fails = 0
for s in atoms:
    try: h.add_atom(s)
    except Exception: fails += 1
for s_ in [copy(x, 99) for x in real[:a.tail]]: h.add_atom(s_)
load_s = time.time() - t; rss_loaded = rss()
def goals_of(strs):
    nodes = [sp.parse_one(sp.tokenize(s), 0)[0][2] for s in strs]
    mem = [c for c in nodes if c[0] == "Member" and len(c) == 3 and isinstance(c[2], str)]
    inh = [c for c in nodes if c[0] == "Inheritance" and len(c) == 3]
    asserted = {sp.to_str(c) for c in nodes}; g = []
    for m in mem:
        for i in inh:
            s = sp.to_str(["Member", m[1], i[2]])
            if m[2] == i[1] and s not in asserted and s not in g: g.append(s)
    return g
gl = [(x, "real") for x in goals_of(real)[:a.real_goals]]
kf = (len(atoms) - n_real) // max(1, len(real))  # last FULLY loaded synthetic copy
if kf: gl += [(x, "syn") for x in goals_of([copy(s, kf) for s in real])[:a.syn_goals]]
res = []
for g, kind in gl:
    stage[0] = "query " + g; t = time.time(); r = q(h, g)
    res.append({"goal": g, "kind": kind, "s": round(time.time() - t, 2), "ok": bool(r), "tv": (str(r).split("STV")[-1][:12] if r else ""), "proof": str(r)[:400] if a.log_proofs else ""})
stage[0] = "neg"; t = time.time(); neg = q(h, a.neg); neg_s = time.time() - t
qs = [r["s"] for r in res]
print("SCALE " + json.dumps({"vendor": a.vendor, "prune": not a.no_prune, "tail": a.tail, "steps": a.steps, "mode": a.mode, "atoms": len(atoms), "real": n_real, "synthetic": n_syn, "copies": k,
    "add_fail": fails, "rules": nr, "seed_s": round(seed_s, 2), "load_s": round(load_s, 2), "ms_per_atom": round(1000 * load_s / max(1, len(atoms)), 1),
    "rss_loaded": rss_loaded, "q_n": len(qs), "q_ok": sum(r["ok"] for r in res), "q_med": round(statistics.median(qs), 2), "q_max": max(qs),
    "q_first": qs[0], "neg": str(neg), "neg_s": round(neg_s, 2), "peak_rss": peak[0], "total_s": round(time.time() - t0, 1), "queries": res}), flush=True)
