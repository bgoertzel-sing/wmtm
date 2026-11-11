import json,sys,os
SKIP={"ts","spec_ts","s","elapsed","elapsed_s","wall","wall_s","dur","dur_s","warm_s","total_s"}
def strip(o):
    if isinstance(o,dict): return {k:strip(v) for k,v in o.items() if k not in SKIP and not k.endswith("_s")}
    if isinstance(o,list): return [strip(x) for x in o]
    return o
def load(p):
    t=open(p).read()
    try: return strip(json.loads(t))
    except Exception: return [strip(json.loads(l)) for l in t.splitlines() if l.strip()]
for n in sorted(os.listdir("runs")):
    for f in ["shadow.jsonl","admit.json"]:
        a,b=load("runs/%s/%s"%(n,f)),load("runs_v2_pre/%s/%s"%(n,f))
        print(n,f,"same-modulo-timing" if a==b else "DIFF")
