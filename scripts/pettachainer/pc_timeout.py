#!/usr/bin/env python3
"""Track F: hard per-query timeout at N atoms, enforced by SIGKILL of the worker process.

Design: a pre-warmed worker subprocess loads seeded rules + mem_inh + the N atoms (same construction as
pc_scale.py) + the Grace canary facts, prints READY, then answers one goal per stdin line.  The parent
starts the clock when it writes the goal; if no RES line arrives within --timeout s it SIGKILLs the worker
(whole process group), records a timeout, and warms a replacement (warm-up time is NOT counted).
Sanity gate (docs/EXPERIMENT_SANITY_GATE.md): canary (Member grace person) and negative control go through
this exact worker/timeout path; every RES payload is structurally checked before it is recorded.
Real data: --atoms / $PC_REPLAY_ATOMS (gitignored .local-data/); the spec file handed to workers is written
under .local-data/ and deleted afterwards.  Prints one JSON line: TIMEOUT {...} (numbers only unless --log-goals)."""
import argparse, json, os, sys, time, signal, select, subprocess, statistics, tempfile
W = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ap = argparse.ArgumentParser()
ap.add_argument("--worker", help=argparse.SUPPRESS)
ap.add_argument("--vendor", default=".vendor36")
ap.add_argument("--atoms", default=os.environ.get("PC_REPLAY_ATOMS", os.path.join(W, ".local-data/replay_atoms.json")))
ap.add_argument("--neg", default=os.environ.get("PC_NEG_GOAL", "(Member grace robot)"))
ap.add_argument("--seeded", default=os.environ.get("SEMPARSE_SEEDED", os.path.join(W, ".semparse-hitl/seeded_rules.metta")))
ap.add_argument("--n", type=int, default=300)
ap.add_argument("--steps", type=int, default=30)
ap.add_argument("--timeout", type=float, default=2.0)
ap.add_argument("--warm-timeout", type=float, default=180.0)
ap.add_argument("--real-goals", type=int, default=8)
ap.add_argument("--syn-goals", type=int, default=4)
ap.add_argument("--repeats", type=int, default=1, help="ask each goal this many times")
ap.add_argument("--log-goals", action="store_true", help="include goal terms (local data; do not commit)")
a = ap.parse_args()
sys.path.insert(0, os.path.join(W, a.vendor)); sys.path.insert(0, W)
MEM_INH = "(: mem_inh (Implication (Premises (Member $x $a) (Inheritance $a $b)) (Conclusions (Member $x $b))) (STV 1.0 0.99))"
CANARY = ["(: cf (Member grace pilot) (STV 1.0 0.99))", "(: cg (Inheritance pilot person) (STV 1.0 0.99))"]

if a.worker:  # ---------------- worker ----------------
    from pettachainer.pettachainer import PeTTaChainer
    from wmtm import semparse_adapter as sp
    spec = json.load(open(a.worker)); h = PeTTaChainer()
    for src, node, err in sp.split_toplevel(open(a.seeded).read() + "\n" + MEM_INH):
        if err or sp.check_statement(node): continue
        for x in sp.normalise(node): h.add_atom(sp.to_str(x))
    fails = 0
    for s in spec["atoms"] + CANARY:
        try: h.add_atom(s)
        except Exception: fails += 1
    print("READY " + json.dumps({"add_fail": fails}), flush=True)
    for line in sys.stdin:
        g = line.strip()
        if not g: continue
        r = h.query("(: $prf %s $tv)" % g, steps=a.steps, timeout_sec=0)
        r = [r] if isinstance(r, str) else list(r or [])
        print("RES " + json.dumps([str(x) for x in r]), flush=True)
    sys.exit(0)

# ---------------- parent ----------------
from wmtm import semparse_adapter as sp
real = []
for k, atoms in json.load(open(a.atoms)).items():
    pre = sp.safe_id(k); txt = "\n".join(x.replace(pre + "__", "").replace("__" + pre, "") for x in atoms)
    real += sp.SemParseAdapter(lambda s, u, t=txt: t, loader=None, reject_log="/tmp/pc_timeout_rejects.jsonl").parse_item(k, "REPLAY").accepted
def isnum(s):
    try: float(s); return True
    except ValueError: return False
def ren(node, k):
    if isinstance(node, str):
        return node if (node.startswith("$") or node.startswith('"') or isnum(node)) else "%s_c%d" % (node, k)
    out = [node[0] if isinstance(node[0], str) else ren(node[0], k)]
    return node if out[0] == "STV" else out + [ren(x, k) for x in node[1:]]
def copy(s, k):
    n = sp.parse_one(sp.tokenize(s), 0)[0]; return sp.to_str([n[0], "%s_c%d" % (n[1], k), ren(n[2], k), n[3]])
atoms = list(real); k = 0
while len(atoms) < a.n:
    k += 1; atoms += [copy(s, k) for s in real]
atoms = atoms[:a.n]; n_real = min(len(real), a.n)
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
kf = (len(atoms) - n_real) // max(1, len(real))
if kf: gl += [(x, "syn") for x in goals_of([copy(s, kf) for s in real])[:a.syn_goals]]

os.makedirs(os.path.join(W, ".local-data"), exist_ok=True)
fd, spec_path = tempfile.mkstemp(prefix="pc_timeout_spec_", suffix=".json", dir=os.path.join(W, ".local-data"))
with os.fdopen(fd, "w") as f: json.dump({"atoms": atoms}, f)

class Worker:
    def __init__(self):
        t = time.time()
        self.p = subprocess.Popen([sys.executable, "-u", os.path.abspath(__file__), "--worker", spec_path, "--vendor", a.vendor,
                                   "--seeded", a.seeded, "--steps", str(a.steps)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, cwd=W, start_new_session=True)
        self.buf = b""; line = self.readline(a.warm_timeout)
        if not line or not line.startswith("READY "): self.kill(); raise SystemExit("WORKER FAILED TO WARM: %r" % line)
        self.add_fail = json.loads(line[6:])["add_fail"]; self.warm_s = time.time() - t
    def readline(self, tmo):
        end = time.time() + tmo; fdn = self.p.stdout.fileno()
        while True:
            while b"\n" in self.buf:
                l, self.buf = self.buf.split(b"\n", 1); l = l.decode(errors="replace")
                if l.startswith(("READY ", "RES ")): return l
            rem = end - time.time()
            if rem <= 0: return None
            r, _, _ = select.select([fdn], [], [], rem)
            if not r: return None
            chunk = os.read(fdn, 65536)
            if not chunk: return None
            self.buf += chunk
    def kill(self):
        try: os.killpg(self.p.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        self.p.wait()

def ask(w, g):
    """-> (worker, record). Structural check: RES must be a JSON list of strings; ok only if a proof mentions the goal head."""
    t = time.time(); w.p.stdin.write((g + "\n").encode()); w.p.stdin.flush()
    line = w.readline(a.timeout); dt = time.time() - t
    if line is None:
        w.kill(); return Worker(), {"s": round(dt, 3), "timeout": True, "ok": False, "n": 0}
    r = json.loads(line[4:])
    if not isinstance(r, list) or not all(isinstance(x, str) for x in r): raise SystemExit("STRUCTURAL CHECK FAILED: %r" % line[:200])
    ok = any(g.split()[0].lstrip("(") in x for x in r)
    if r and not ok: raise SystemExit("STRUCTURAL CHECK FAILED: non-empty result without goal head")
    return w, {"s": round(dt, 3), "timeout": False, "ok": ok, "n": len(r)}

t0 = time.time(); w = Worker(); warm = [w.warm_s]; add_fail = w.add_fail
w, can = ask(w, "(Member grace person)")
w, negc = ask(w, a.neg)
canary_pass = can["ok"] and not can["timeout"]
neg_pass = (not negc["ok"]) and not negc["timeout"]
res = []
for rep in range(a.repeats):
    for g, kind in gl:
        nw, r = ask(w, g)
        if nw is not w: warm.append(nw.warm_s)
        w = nw; r["kind"] = kind
        if a.log_goals: r["goal"] = g
        res.append(r)
w, can2 = ask(w, "(Member grace person)")   # canary again at the end: worker state not corrupted
w.kill(); os.unlink(spec_path)
qs = [r["s"] for r in res]; to = [r for r in res if r["timeout"]]; done = [r["s"] for r in res if not r["timeout"]]
print("TIMEOUT " + json.dumps({"vendor": a.vendor, "atoms": len(atoms), "real": n_real, "synthetic": len(atoms) - n_real, "steps": a.steps,
    "timeout_s": a.timeout, "add_fail": add_fail, "warm_med_s": round(statistics.median(warm), 2), "workers": len(warm),
    "canary": can, "canary_end": can2, "neg": negc, "canary_pass": canary_pass and can2["ok"], "neg_pass": neg_pass,
    "q_n": len(res), "timeouts": len(to), "timeout_rate": round(len(to) / max(1, len(res)), 3),
    "ok_n": sum(r["ok"] for r in res), "q_med_censored": round(statistics.median(qs), 3) if qs else None,
    "q_med_completed": round(statistics.median(done), 3) if done else None, "q_max_completed": max(done) if done else None,
    "by_kind": {kd: {"n": sum(r["kind"] == kd for r in res), "timeouts": sum(r["kind"] == kd and r["timeout"] for r in res)} for kd in ("real", "syn")},
    "total_s": round(time.time() - t0, 1), "queries": res}), flush=True)
sys.exit(0 if (canary_pass and neg_pass and can2["ok"]) else 3)
