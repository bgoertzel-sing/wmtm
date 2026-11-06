import json,os,subprocess,sys
ref=json.load(open(os.path.expanduser("~/.openclaw/openclaw.json")))["gateway"]["auth"]["token"]
tok=ref
if isinstance(ref,dict):
    sec=json.load(open(os.path.expanduser("~/.openclaw/secrets.json")))
    for part in ref["id"].strip("/").split("/"): sec=sec[part]
    tok=sec
assert isinstance(tok,str) and tok, "token not resolved"
env=dict(os.environ); env["OPENCLAW_GATEWAY_TOKEN"]=tok
env["WMTM_SEMPARSE_HITL"]="/home/openclaw/scratch/p4/sph"
env["WMTM_SEMPARSE_DIR"]="/tmp/p4_rev2/r2/cache_snapshot"
env["WMTM_SEMPARSE_PROMPT_SHA256"]="645bff3f5c3a0670d98a463d60d18e178d899c08c58f17ea4b3ff5a53b1d25b6"
B="/home/openclaw/research-agent/projects/omegaclaw/wmtm-module"
out,hf=sys.argv[1],sys.argv[2]
sys.exit(subprocess.call([sys.executable,B+"/tools/measure_parse.py","--state-dir","/tmp/p4_rev2/r2/state","--hashes","@"+hf,"--out",out,"--provider","openclaw","--base-url","http://127.0.0.1:18789/v1","--model","openclaw/protocosmo2","--per-hour","20"],env=env))
