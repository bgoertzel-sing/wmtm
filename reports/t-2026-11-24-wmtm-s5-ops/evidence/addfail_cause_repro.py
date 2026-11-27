import sys,json,os,tempfile,shutil,atexit,re
R="/home/openclaw/research-agent/projects/omegaclaw/protocosmo2/iter-port/repos"
C=json.load(open(R+"/memory/_wmtm_shadow/pc_shadow/worker_config.json"))
sys.path.insert(0,R+"/vendor/wmtm-d506783")
sys.path.insert(0,os.path.join(C["petta_dir"],"python")); sys.path.insert(0,C["pettachainer_dir"]); os.environ["PETTA_PATH"]=C["petta_dir"]
from wmtm import master_loader as ML
from pettachainer.pettachainer import PeTTaChainer
cfg=json.load(open(R+"/memory/_wmtm_flags.json"))
tdir=os.path.expanduser(cfg["shadow_sph_templates"]); src=os.path.expanduser(cfg["shadow_master_parsed"])
T=tempfile.mkdtemp(prefix="s5af_"); os.chmod(T,0o700); atexit.register(lambda: shutil.rmtree(T,ignore_errors=True))
p=T+"/parsed.jsonl"; shutil.copy(src,p)
ids=[]
for l in open(p):
    if not l.strip(): continue
    d=json.loads(l).get("doc")
    if d and d not in ids and not d.startswith("derived-"): ids.append(d)
print("notes",len(ids),flush=True)
notes,info=ML.notes_from_parsed(tdir,p,ids); ops,meta=ML.plan(tdir,notes)
print("ops",len(ops),flush=True)
h=PeTTaChainer(); n=0
for i,(k,x) in enumerate(ops):
    try: h.set_positive_only_predicate(x) if k=="pred" else h.add_atom(x)
    except Exception as e:
        n+=1; print("FAIL",i,k,type(e).__name__,repr(str(e)[:300]),flush=True); print("ATOM",x,flush=True)
        # retry alone in fresh chainer
        try: PeTTaChainer().add_atom(x); print("ALONE ok",flush=True)
        except Exception as e2: print("ALONE fail",type(e2).__name__,flush=True)
print("fails",n,"DONE",flush=True)
