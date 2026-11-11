import json,glob,sys,os
code=sys.argv[1]; sys.path.insert(0,code)
from wmtm import runtime_config as rc
from wmtm.pc_shadow import snapshot_from_raw
G="/tmp/gfr"
for a in sys.argv[2:]:
    cfg=rc.load_worker_config(G+"/loop/%s/state/runtime/pc_shadow/worker_config.json"%a)
    S=[json.loads(l) for l in open(G+"/loop/%s/state/runtime/pc_shadow/shadow.jsonl"%a)]
    os.makedirs(G+"/specs_rebuilt/"+a,exist_ok=True); bad=0; n=0
    for f in glob.glob(G+"/specs/%s/spec_c*.json"%a):
        s=json.load(open(f))
        if "raw_items" not in s: continue
        full=snapshot_from_raw(s,cfg); n+=1
        m=[x for x in S if abs((x.get("spec_ts") or 0)-(s.get("ts") or -1))<1e-6]
        ok=bool(m) and m[-1].get("atoms")==len(full["atoms"]) and m[-1].get("goals_n")==len(full["goals"])
        if not ok: bad+=1; print("MISMATCH",a,os.path.basename(f),m[-1].get("atoms") if m else None,len(full["atoms"]))
        json.dump(full,open(G+"/specs_rebuilt/%s/%s"%(a,os.path.basename(f)),"w"))
    print(a,"rebuilt",n,"mismatch",bad)
