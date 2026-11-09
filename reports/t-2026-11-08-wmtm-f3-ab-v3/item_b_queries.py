import os,sys,json,time
P="/home/openclaw/research-agent/projects/omegaclaw/p1-engine/petta-3681b9b"
sys.path.insert(0,P+"/python"); sys.path.insert(0,"/tmp/f3/pc"); os.environ["PETTA_PATH"]=P
from pettachainer.pettachainer import PeTTaChainer as PC
run=sys.argv[1]
d=json.load(open(f"/tmp/f3/ab/{run}/full_B_spec.json"))
h=PC(); bad=0
for a in d["atoms"]:
    try: h.add_atom(a if isinstance(a,str) else str(a))
    except Exception as e: bad+=1
Q=[("chat_send valid","(Inheritance chat_send valid)"),("chat_send valid","(Member chat_send valid)"),("chat_send valid","(Inheritance chat_send $c)"),("chat_send valid","(Member chat_send $c)"),("chat_send valid","(Member $x valid)"),
("goalchainer_v2 branch","(Member hive_t_2026_10_28_goalchainer_v2_status branch)"),("goalchainer_v2 branch","(Member hive_t_2026_10_28_goalchainer_v2_status $c)"),
("progress_report report","(Inheritance hive_progress_report report)"),("progress_report report","(Member hive_progress_report report)"),("progress_report report","(Inheritance hive_progress_report $c)"),("progress_report report","(Member hive_progress_report $c)"),
("turn_without_send entry","(Member turn_without_send_entry entry)"),("turn_without_send entry","(Member turn_without_send_entry $c)"),("turn_without_send entry","(Member $x entry)"),("turn_without_send entry","(Inheritance ltm_entry entry)")]
out={"run":run,"atoms":len(d["atoms"]),"add_fail":bad,"q":[]}
for tag,g in Q:
    t=time.time()
    try: r=[str(x) for x in h.query(f"(: $prf {g} $tv)",steps=30,timeout_sec=0)]
    except Exception as e: r=["ERR "+repr(e)[:120]]
    out["q"].append({"for":tag,"goal":g,"n":len(r),"s":round(time.time()-t,3),"res":r[:4]})
print(json.dumps(out,indent=1))
