#!/usr/bin/env python3
"""Track G shadow worker (launched detached by wmtm/pc_shadow.py; never waited on).

Outer process: spawns an inner PeTTaChainer child (PeTTa v1.0.6 from .vendor-petta106 + PeTTaChainer 36b3fe6
dedup-patched from .vendor36), which loads transitivity rules + mem_inh + snapshot atoms + Grace canary facts
and answers one goal per stdin line.  Each query has a hard --timeout (default 2 s) enforced by SIGKILL of the
child's process group; the whole turn has a --budget (default 20 s).  Sanity gate: canary (Member grace person)
must prove and the negative control (Member grace robot) must not, through this exact path, else the record is
marked canary_fail and no goal results are trusted.  Each RES is structurally checked.  One JSONL line appended
to --out per run; the spec file is deleted afterwards.
"""
import argparse, json, os, sys, time, signal, select, subprocess
W = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ap = argparse.ArgumentParser()
ap.add_argument("--spec", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--inner", action="store_true", help=argparse.SUPPRESS)
ap.add_argument("--petta", default=os.environ.get("WMTM_PC_PETTA", os.path.join(W, ".vendor-petta106")))
ap.add_argument("--vendor", default=os.environ.get("WMTM_PC_VENDOR", os.path.join(W, ".vendor36")))
ap.add_argument("--steps", type=int, default=30)
ap.add_argument("--timeout", type=float, default=2.0)
ap.add_argument("--budget", type=float, default=20.0)
ap.add_argument("--warm-timeout", type=float, default=60.0)
ap.add_argument("--keep-spec", action="store_true")
a = ap.parse_args()
RULES = [
    "(: mem_inh (Implication (Premises (Member $x $a) (Inheritance $a $b)) (Conclusions (Member $x $b))) (STV 1.0 0.99))",
    "(: inh_trans (Implication (Premises (Inheritance $a $b) (Inheritance $b $c)) (Conclusions (Inheritance $a $c))) (STV 1.0 0.99))",
    "(: imp_trans (Implication (Premises (Implies $a $b) (Implies $b $c)) (Conclusions (Implies $a $c))) (STV 1.0 0.99))",
]
CANARY = ["(: cf (Member grace pilot) (STV 1.0 0.99))", "(: cg (Inheritance pilot person) (STV 1.0 0.99))"]
CANARY_GOAL, NEG_GOAL = "(Member grace person)", "(Member grace robot)"

if a.inner:  # ---------------- inner PeTTaChainer child ----------------
    sys.path.insert(0, os.path.join(a.petta, "python")); sys.path.insert(0, a.vendor)
    os.environ["PETTA_PATH"] = a.petta
    import petta
    from pettachainer.pettachainer import PeTTaChainer
    h = PeTTaChainer(); spec = json.load(open(a.spec)); fails = 0
    for s in RULES + spec["atoms"] + CANARY:
        try: h.add_atom(s)
        except Exception: fails += 1
    print("READY " + json.dumps({"add_fail": fails, "petta": petta.__file__}), flush=True)
    for line in sys.stdin:
        g = line.strip()
        if not g: continue
        try:
            r = h.query("(: $prf %s $tv)" % g, steps=a.steps, timeout_sec=0)
            r = [r] if isinstance(r, str) else list(r or [])
        except Exception as e:
            r = None; print("ERR " + json.dumps(type(e).__name__), flush=True); continue
        print("RES " + json.dumps([str(x) for x in r]), flush=True)
    sys.exit(0)

# ---------------- outer ----------------
class Inner:
    def __init__(self):
        t = time.time()
        self.p = subprocess.Popen([sys.executable, "-u", os.path.abspath(__file__), "--inner", "--spec", a.spec, "--out", a.out,
                                   "--petta", a.petta, "--vendor", a.vendor, "--steps", str(a.steps)],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=W, start_new_session=True)
        self.buf = b""; line = self.readline(a.warm_timeout); self.warm_s = round(time.time() - t, 3)
        self.ok = bool(line and line.startswith("READY "))
        self.info = json.loads(line[6:]) if self.ok else {"warm_fail": (line or "")[:200]}
    def readline(self, tmo):
        end = time.time() + tmo; fdn = self.p.stdout.fileno()
        while True:
            while b"\n" in self.buf:
                l, self.buf = self.buf.split(b"\n", 1); l = l.decode(errors="replace")
                if l.startswith(("READY ", "RES ", "ERR ")): return l
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

def parse_stv(proofs):
    import re
    for x in proofs:
        m = re.search(r"STV\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\)*\s*$", x)
        if m: return float(m.group(1)), float(m.group(2))
    return None

def ask(w, g, tmo):
    t = time.time(); w.p.stdin.write((g + "\n").encode()); w.p.stdin.flush()
    line = w.readline(tmo); dt = round(time.time() - t, 3)
    if line is None:
        w.kill(); return None, {"goal": g, "s": dt, "timeout": True, "ok": False}
    if line.startswith("ERR "):
        return w, {"goal": g, "s": dt, "timeout": False, "ok": False, "error": json.loads(line[4:])}
    r = json.loads(line[4:])
    if not isinstance(r, list) or not all(isinstance(x, str) for x in r):
        w.kill(); return None, {"goal": g, "s": dt, "timeout": False, "ok": False, "structural_fail": True}
    head = g.split()[0].lstrip("(")
    ok = any(head in x for x in r)
    rec = {"goal": g, "s": dt, "timeout": False, "ok": ok, "n": len(r)}
    if r and not ok: rec["structural_fail"] = True
    if ok:
        tv = parse_stv(r)
        if tv: rec["stv"] = [round(tv[0], 4), round(tv[1], 4)]
    return w, rec

t0 = time.time(); spec = json.load(open(a.spec))
rec = {"cycle": spec.get("cycle"), "spec_ts": spec.get("ts"), "start_ts": t0, "k": spec.get("k"), "items": spec.get("items"),
       "atoms": len(spec["atoms"]), "goals_n": len(spec["goals"]), "timeout_s": a.timeout, "budget_s": a.budget, "steps": a.steps}
w = Inner(); rec["warm_s"] = w.warm_s; rec.update(w.info); res = []
if not w.ok:
    rec["status"] = "warm_fail"; w.kill()
else:
    w2, can = ask(w, CANARY_GOAL, a.timeout); w = w2 or Inner()
    w2, neg = ask(w, NEG_GOAL, a.timeout); w = w2 or Inner()
    rec["canary"] = can; rec["neg"] = neg
    if not (can["ok"] and not neg["ok"] and not neg["timeout"]):
        rec["status"] = "canary_fail"
    else:
        rec["status"] = "ok"; skipped = 0
        for g in spec["goals"]:
            left = a.budget - (time.time() - t0)
            if left <= 0.05: skipped += 1; continue
            w2, r = ask(w, g, min(a.timeout, left)); res.append(r)
            if w2 is None:
                if a.budget - (time.time() - t0) <= 0.5: w = None; skipped += len(spec["goals"]) - len(res); break
                w = Inner()
                if not w.ok: rec["status"] = "rewarm_fail"; w = None; skipped += len(spec["goals"]) - len(res); break
            else: w = w2
        rec["skipped_budget"] = skipped
    if w: w.kill()
py = {d["goal"]: d for d in spec.get("python_derived", []) if "goal" in d}
diffs = []
for r in res:
    if r["goal"] in py:
        r["python"] = [py[r["goal"]]["s"], py[r["goal"]]["c"]]
        if r.get("stv"):  # PeTTaChainer is the reference: diff = python - pc
            r["diff"] = [round(r["python"][0] - r["stv"][0], 4), round(r["python"][1] - r["stv"][1], 4)]; diffs.append(r["diff"])
if diffs:
    rec["tv_diff_mean"] = [round(sum(d[0] for d in diffs) / len(diffs), 4), round(sum(d[1] for d in diffs) / len(diffs), 4)]
    rec["tv_absdiff_max"] = [round(max(abs(d[0]) for d in diffs), 4), round(max(abs(d[1]) for d in diffs), 4)]
for key in ("semparse_items", "fallback_atoms", "facts"):
    rec[key] = spec.get(key)
rec["queries"] = res
rec["pc_proved"] = sum(r["ok"] for r in res); rec["timeouts"] = sum(r["timeout"] for r in res)
pcg = {r["goal"] for r in res if r["ok"]}; asked = {r["goal"] for r in res}
rec["agree_both"] = len(pcg & set(py)); rec["pc_only"] = len(pcg - set(py)); rec["py_only_asked"] = len((set(py) & asked) - pcg)
rec["py_invalid_chain"] = sum(1 for d in spec.get("python_derived", []) if "invalid_chain" in d); rec["py_derived_n"] = len(py); rec["total_s"] = round(time.time() - t0, 3)
os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
with open(a.out, "a") as f: f.write(json.dumps(rec) + "\n")
if not a.keep_spec:
    try: os.unlink(a.spec)
    except OSError: pass
try:
    pf = os.path.join(os.path.dirname(os.path.abspath(a.out)), "worker.pid")
    if open(pf).read().strip() == str(os.getpid()): os.unlink(pf)
except OSError: pass
sys.exit(0 if rec["status"] == "ok" else 3)
