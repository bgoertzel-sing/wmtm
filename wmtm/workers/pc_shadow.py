"""Track G shadow worker: ``python -m wmtm.workers.pc_shadow --spec S --out O [--config C]``.

Launched detached by wmtm/pc_shadow.py; never waited on.  Outer process: builds the snapshot from the raw spec
(off the cycle path), then spawns an inner PeTTaChainer child (PeTTa v1.0.6 + PeTTaChainer 36b3fe6 dedup-patched,
paths from the runtime config), which loads transitivity rules + mem_inh + snapshot atoms + Grace canary facts and
answers one goal per stdin line.  Each query has a hard timeout (default 2 s) enforced by SIGKILL of the child's
process group; the queries share a budget (default 20 s).  Address space is capped (worker_mem_mb, inherited by the
child).  Sanity gate: canary (Member grace person) must prove and the negative control (Member grace robot) must
not, through this exact path, else the record is marked canary_fail and no goal results are trusted.  Each RES is
structurally checked.  One JSONL line appended to --out per run (size-capped, rotated to .1); the spec file is
deleted afterwards.
"""
import argparse, json, os, sys, time, signal, select, subprocess

from wmtm import runtime_config as rc

ap = argparse.ArgumentParser()
ap.add_argument("--spec", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--config", default=None, help="worker_config.json written by the launcher (default: env/defaults)")
ap.add_argument("--inner", action="store_true", help=argparse.SUPPRESS)
ap.add_argument("--petta", default=None)
ap.add_argument("--vendor", default=None, help="PeTTaChainer dir (contains pettachainer/)")
ap.add_argument("--steps", type=int, default=None)
ap.add_argument("--timeout", type=float, default=None)
ap.add_argument("--budget", type=float, default=None)
ap.add_argument("--warm-timeout", type=float, default=60.0)
ap.add_argument("--keep-spec", action="store_true")
a = ap.parse_args()
CFG = rc.load_worker_config(a.config) if a.config else rc.resolve()
a.petta = a.petta or CFG["petta_dir"]
a.vendor = a.vendor or CFG["pettachainer_dir"]
a.steps = a.steps if a.steps is not None else int(CFG["shadow_steps"])
a.timeout = a.timeout if a.timeout is not None else float(CFG["shadow_timeout_s"])
a.budget = a.budget if a.budget is not None else float(CFG["shadow_budget_s"])
MEM_CAP = rc.apply_mem_cap(CFG.get("worker_mem_mb")) if not a.inner else None
PRIO = rc.lower_priority(CFG) if not a.inner else None     # inherited by the PeTTa child
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
        args = ["--inner", "--spec", a.spec, "--out", a.out, "--petta", a.petta, "--vendor", a.vendor, "--steps", str(a.steps)]
        if a.config:
            args += ["--config", a.config]
        self.p = subprocess.Popen([sys.executable, "-u", "-m", "wmtm.workers.pc_shadow"] + args,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  cwd=rc.DIST_ROOT, env=rc.worker_env(CFG), start_new_session=True)
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
if "raw_items" in spec:  # built here, off the cycle path
    try:
        from wmtm.pc_shadow import snapshot_from_raw
        spec = snapshot_from_raw(spec, CFG)
    except Exception as e:
        spec.update(atoms=[], goals=[], build_error=type(e).__name__ + ": " + str(e)[:160])
    with open(a.spec + ".tmp", "w") as f: json.dump(spec, f)
    os.replace(a.spec + ".tmp", a.spec)
rec = {"mem_cap_mb": (MEM_CAP or 0) // (1 << 20), "prio": PRIO, "cycle": spec.get("cycle"), "spec_ts": spec.get("ts"), "start_ts": t0, "k": spec.get("k"), "items": spec.get("items"),
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
        t0q = time.time(); rec["prequery_s"] = round(t0q - t0, 3)  # budget covers queries only (build+warm ate it under load)
        for g in spec["goals"]:
            left = a.budget - (time.time() - t0q)
            if left <= 0.05: skipped += 1; continue
            w2, r = ask(w, g, min(a.timeout, left)); res.append(r)
            if w2 is None:
                if a.budget - (time.time() - t0q) <= 0.5: w = None; skipped += len(spec["goals"]) - len(res); break
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
for key in ("semparse_items", "fallback_atoms", "facts", "build_s", "build_error", "skolem_goals", "py_skolem_goals_dropped"):
    rec[key] = spec.get(key)
rec["queries"] = res
rec["pc_proved"] = sum(r["ok"] for r in res); rec["timeouts"] = sum(r["timeout"] for r in res)
pcg = {r["goal"] for r in res if r["ok"]}; asked = {r["goal"] for r in res}
rec["agree_both"] = len(pcg & set(py)); rec["pc_only"] = len(pcg - set(py)); rec["py_only_asked"] = len((set(py) & asked) - pcg)
rec["py_invalid_chain"] = sum(1 for d in spec.get("python_derived", []) if "invalid_chain" in d); rec["py_derived_n"] = len(py); rec["total_s"] = round(time.time() - t0, 3)
os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
rc.append_jsonl(a.out, rec, CFG.get("jsonl_max_bytes"))
if not a.keep_spec:
    try: os.unlink(a.spec)
    except OSError: pass
try:
    pf = os.path.join(os.path.dirname(os.path.abspath(a.out)), "worker.pid")
    if open(pf).read().strip() == str(os.getpid()): os.unlink(pf)
except OSError: pass
sys.exit(0 if rec["status"] == "ok" else 3)
