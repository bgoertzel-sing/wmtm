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
if any((r.get("pred_fail") or 0)>0 for r in rows): trig.append("pred_fail")
EXC={20473}  # answer-3 load-stall exception
if any((r.get("timeouts") or 0)>0 and r.get("cycle") not in EXC for r in rows): trig.append("timeouts")
if any(r.get("build_error") for r in rows): trig.append("build_error")
if any(not (r.get("canary") or {}).get("ok") for r in rows): trig.append("canary")
print(time.strftime("%FT%TZ",time.gmtime()),"rows",len(rows),"add_fail>0",sum(1 for a in af if a>0),"max",max(af) if af else None,
 "pq_median",round(st.median(pq),2) if pq else None,"pq_max",pq[-1] if pq else None,"ge12",sum(1 for x in pq if x>=12),"TRIGGERS",trig or "none","load1",open("/proc/loadavg").read().split()[0],"last_cycle",rows[-1].get("cycle") if rows else None,"last_warm_s",rows[-1].get("warm_s") if rows else None,"last_to",rows[-1].get("timeouts") if rows else None,"exc",sorted(EXC),flush=True)
