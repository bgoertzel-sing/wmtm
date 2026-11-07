# Build a B-only parse cache (parser 1f1a7a6f, catalog mode) from the recovered replies; no LLM calls.
import json,os,sys,hashlib,time
B="/home/openclaw/research-agent/projects/omegaclaw/wmtm-module"; sys.path.insert(0,B)
from wmtm import semparse_adapter as sp
from wmtm.parse_cache import ParseCache, content_hash
out="/tmp/p4_rev2/r2/ab/cache"; os.makedirs(out,exist_ok=True)
assert not os.path.exists(os.path.join(out,"cache.jsonl")), "cache exists; refuse to append"
raw=json.load(open("/tmp/p3_out/ab/raw_spec.json"))["raw_items"]
rep={json.loads(l)["hash"]:json.loads(l)["reply"] for l in open("/tmp/p4_rev2/r2/recover/mock_replies.jsonl")}
cur={}
llm=lambda s,u: rep.get(cur["h"],""); llm.last_usage=None
ad=sp.SemParseAdapter(llm, mode="catalog", reject_log=os.path.join(out,"rejects.local.jsonl"), max_chars=10**6)
pc=ParseCache(out, per_hour=1000, max_chars=10**6, max_attempts=1)
counts={}
for it in raw:
    h=content_hash(it["content"]); assert h in rep, h
    cur["h"]=h
    r=ad.parse_item(it["id"],{"text":it["content"]})
    assert not r.truncated_chars
    st="ok" if r.accepted else "empty"
    if r.error: st="failed"
    pc.record(h,{"item_id":it["id"],"content":it["content"]},st,list(r.accepted) if st in("ok","empty") else [],
              {"ts":time.time(),"prompt_sha":(getattr(ad,"prompt_sha256","") or "")[:16]})
    counts[h]=(st,len(r.accepted),len(r.rejected))
print(len(counts),sum(v[1] for v in counts.values()),sum(v[2] for v in counts.values()))
pn={}
for f in ("/tmp/p4_rev2/r2/rest","/tmp/p4_rev2/r2/canary"):
    for l in open(f"{f}/per_note.jsonl"):
        d=json.loads(l); pn[d["hash"]]=(d["accepted"],d["rejected"])
print("diffs",[(h[:8],counts[h][1:],pn.get(h)) for h in counts if counts[h][1:]!=pn.get(h)])
