"""Compare rev2 re-runs with the pre-rev2 runs, ignoring timing fields. Usage: cmpruns.py [new_dir] [old_dir]."""
import json, sys, os
H = os.path.join(os.path.dirname(__file__), "..", "evidence")
new = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, "runs_rev2")
old = sys.argv[2] if len(sys.argv) > 2 else os.path.join(H, "runs_v2_pre")
SKIP = {"ts", "spec_ts", "s", "start_ts", "elapsed", "wall", "dur"}
def strip(o):
    if isinstance(o, dict): return {k: strip(v) for k, v in o.items() if k not in SKIP and not k.endswith("_s")}
    if isinstance(o, list): return [strip(x) for x in o]
    return o
def load(p):
    t = open(p).read()
    try: return strip(json.loads(t))
    except ValueError: return [strip(json.loads(l)) for l in t.splitlines() if l.strip()]
for n in sorted(os.listdir(old)):
    for f in ["shadow.jsonl", "admit.json"]:
        a, b = load(os.path.join(new, n, f)), load(os.path.join(old, n, f))
        print(n, f, "same-modulo-timing" if a == b else "DIFF")
