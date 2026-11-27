import json,time,statistics as st
R="/home/openclaw/research-agent/projects/omegaclaw/protocosmo2/iter-port/repos"; T=1795714585
rows=[]
for l in open(R+"/memory/_wmtm_shadow/pc_shadow/shadow.jsonl"):
    try: r=json.loads(l)
    except: continue
    if float(r.get("start_ts") or 0)>=T: rows.append(r)
af=[r.get("add_fail") or 0 for r in rows]; pq=sorted(float(r.get("prequery_s") or 0) for r in rows)
trig=[]
if any(a>=3 for a in af): trig.append("T3 row add_fail>=3")
if sum(1 for a in af if a>0)>3: trig.append("T3 count>3")
for k in ("pred_fail","timeouts"):
    if any((r.get(k) or 0)>0 for r in rows): trig.append(k)
if any(r.get("build_error") for r in rows): trig.append("build_error")
if any(not (r.get("canary") or {}).get("ok") for r in rows): trig.append("canary")
print(time.strftime("%FT%TZ",time.gmtime()),"rows",len(rows),"add_fail>0",sum(1 for a in af if a>0),"max",max(af) if af else None,
 "pq_median",round(st.median(pq),2) if pq else None,"pq_max",pq[-1] if pq else None,"ge12",sum(1 for x in pq if x>=12),"TRIGGERS",trig or "none",flush=True)
