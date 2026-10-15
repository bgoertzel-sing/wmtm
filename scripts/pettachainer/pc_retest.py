"""Retest PeTTaChainer problems found in track C. One case per process (memory isolation).
Usage: python pc_retest.py <vendor_dir> <case>   -> prints RESULT <case> <json>"""
import sys, os, json, time, threading
W = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(W, sys.argv[1]))
LIMIT = int(os.environ.get("PC_RSS_MB", "1200"))
def rss(): return int(open("/proc/self/status").read().split("VmRSS:")[1].split()[0]) // 1024
def wd():
    while True:
        time.sleep(0.1)
        if rss() > LIMIT:
            print("RESULT", sys.argv[2], json.dumps({"abort_rss_mb": rss()}), flush=True); os._exit(5)
threading.Thread(target=wd, daemon=True).start()
from pettachainer.pettachainer import PeTTaChainer
S = "(STV 1.0 0.99)"
def run(atoms, goals, steps=30):
    h = PeTTaChainer(); t = time.time(); out = {"add": []}
    for a in atoms:
        try: out["add"].append(str(h.add_atom(a))[:120])
        except Exception as e: out["add"].append("EXC " + repr(e)[:160])
    out["load_s"] = round(time.time() - t, 2)
    for g in goals:
        t = time.time()
        try: r = h.query("(: $prf %s $tv)" % g, steps=steps, timeout_sec=0)
        except Exception as e: r = "EXC " + repr(e)[:200]
        out[g] = [str(r)[:300], round(time.time() - t, 2)]
    out["rss_mb"] = rss(); return out
C = {
 "and_impl": (["(: r (Implication (And (Inheritance $x $y) (Inheritance $y $z)) (Inheritance $x $z)) %s)" % S,
               "(: f1 (Inheritance pilot person) %s)" % S, "(: f2 (Inheritance person animal) %s)" % S],
              ["(Inheritance pilot animal)"]),
 "premises_impl": (["(: r (Implication (Premises (Inheritance $x $y) (Inheritance $y $z)) (Conclusions (Inheritance $x $z))) %s)" % S,
               "(: f1 (Inheritance pilot person) %s)" % S, "(: f2 (Inheritance person animal) %s)" % S],
              ["(Inheritance pilot animal)"]),
 "multi_concl": (["(: r (Implication (Premises (Member $x pilot)) (Conclusions (Member $x person) (Member $x flyer))) %s)" % S,
               "(: f (Member grace pilot) %s)" % S], ["(Member grace person)", "(Member grace flyer)"]),
 "mem_native": (["(: f (Member grace pilot) %s)" % S, "(: g (Inheritance pilot person) %s)" % S],
                ["(Member grace person)"]),
 "or_in_and": (["(: x (And (Member o offer) (Or (And (Theme o v1) (Member v1 a)) (And (Theme o v2) (Member v2 b))) (Past o)) %s)" % S],
               ["(Member o offer)"]),
 "stv_range": (["(: bad1 (Member a b) (STV 1.0 1.5))", "(: bad2 (Member c d) (STV -0.5 0.9))", "(: bad3 (Member e f) (STV 2.0 0.5))"],
               ["(Member a b)", "(Member c d)", "(Member e f)"]),
 "and_elim": (["(: c (And (Member o offer) (Past o)) %s)" % S], ["(Member o offer)", "(Past o)"]),
 "canary": (["(: mem_inh (Implication (Premises (Member $x $a) (Inheritance $a $b)) (Conclusions (Member $x $b))) %s)" % S,
             "(: f (Member grace pilot) %s)" % S, "(: g (Inheritance pilot person) %s)" % S],
            ["(Member grace person)", "(Member grace robot)"]),
}
a, g = C[sys.argv[2]]
print("RESULT", sys.argv[2], json.dumps(run(a, g)), flush=True)
