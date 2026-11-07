#!/usr/bin/env python3
"""P4 rev2 recompute (stdlib only). Recomputes budget, shares, A/B counts and checks gates/pins/stop-lines."""
import os,re,json,statistics as S,sys
D=os.path.dirname(os.path.abspath(__file__)); ok=True
def P(*a): return os.path.join(D,*a)
def chk(n,c,info=""):
    global ok; ok&=bool(c); print(("PASS " if c else "FAIL ")+n+(("  ["+info+"]") if info else ""))
W={"uncached_input":1.0,"cache_write":1.25,"cache_read":0.1,"output":5.0}
rows=[json.loads(l) for f in ("canary_per_note_raw.jsonl","rest_per_note_raw.jsonl") for l in open(P("budget",f))]
for r in rows: r["_w"]=sum(W[k]*(r[k] or 0) for k in W)
chk("budget: 20 notes measured, usage complete",len(rows)==20 and all(r[k] is not None for r in rows for k in W),str(len(rows)))
chk("budget: weighted recomputed == logged",all(abs(r["_w"]-r["weighted"])<0.5 for r in rows))
mb=S.median(r["_w"] for r in rows); ml=S.median(r["live_weighted_lo"] for r in rows); ratio=mb/ml
mx=max(r["_w"]/r["live_weighted_lo"] for r in rows)
chk("budget: weighted usage/note <= 2x live (ratio of medians)",ratio<=2.0,"%.3f, max per-note %.3f"%(ratio,mx))
lat=S.median(r["latency_s"] for r in rows)
chk("budget: median latency <= 180 s",lat<=180,"%.1f s (live %.1f s)"%(lat,S.median(r["live_secs"] for r in rows)))
chk("budget: no parse errors",all(not r["error_kind"] for r in rows))
for f in ("canary_summary.json","rest_summary.json"):
    s=json.load(open(P("budget",f))); chk("budget: 0 429/usage-limit errors in "+f,s["limit_errors_429_or_usage"]==0 and s["errors"]==0)
g=open(P("budget","gateway_extract.json")).read()
chk("budget: gateway extract has no 429/usage-limit",not re.search(r'(?<![.\d:])429(?!\d)|usage.limit|rate.limit|too many requests',g,re.I),"timestamp millis like :58.429 excluded" )
u=[json.loads(l) for l in open(P("budget","agent_usage_extract.jsonl"))]
MAP=[("input","uncached_input"),("cacheWrite","cache_write"),("cacheRead","cache_read"),("output","output")]
tot={}
for x in u:
    w=sum(W[b]*(x[a] or 0) for a,b in MAP); tot.setdefault(x["win"],{}); tot[x["win"]][x["agent"]]=tot[x["win"]].get(x["agent"],0)+w
pw={"canary":sum(r["_w"] for r in rows[:1]),"rest":sum(r["_w"] for r in rows[1:])}
pc=sum(pw.values()); p2=sum(t.get("protocosmo2",0) for t in tot.values()); al=sum(sum(t.values()) for t in tot.values())
print("INFO parse feed share (both windows): of protocosmo2 %.3f, of all agents/gateway %.3f; agents seen %s"%(pc/p2,pc/al,sorted({x['agent'] for x in u})))
chk("budget: parse share <= 1",pc<=p2<=al)
d=json.load(open(P("ab","AB_DIFF.json"))); b=json.load(open(P("ab","B_W1234.json")))
A=d["A"]; B=d["B_P4"]
wrongA=json.load(open(P("ab","A_W1234.json")))["wrong"] if os.path.exists(P("ab","A_W1234.json")) else None
cB=B["goals"]-sum(b[k] for k in ("W1","W2","W3","W4") if isinstance(b[k],int) and False)
print("INFO A: goals %d proved %d; B: atoms %d facts %d rules %d goals %d proved %d"%(A["goals"],A["proved"],B["atoms"],B["facts"],B["rules"],B["goals"],B["proved"]))
corrB=len(b["conclusions"]); corrA=A["proved"]-(wrongA or 0)
chk("A/B: andy criterion correct(B)>=correct(A) AND wrong(B)<=wrong(A) (expected FAIL -> Not Ready)",corrB>=corrA,"correct B=%d A=%d"%(corrB,corrA))
chk("A/B: every A conclusion listed in diff_rows",len(d["diff_rows"])==A["goals"])
gs=open(P("gates","SUMMARY.txt")).read()+open(P("gates","pytest.log")).read()
chk("gate: GoalChainer 186 passed at 38b1473",("186 passed" in gs) and "38b147345a3d195637377a9d0f6017e2f50aa105" in gs)
chk("gate: engine-loading trace: all opens under external/PeTTaChainer, 0 bdae8d7 paths","bdae8d7 paths: 0" in gs)
gl=open(P("gates","goals242.log")).read()
chk("gate: wmtm goal tests 242 passed",re.search(r"\b242 passed",gl) and not re.search(r"\d+ failed",gl))
chk("unit: P4 reader tests passed",re.search(r"\b9 passed",open(P("narrow","pytest_p4.txt")).read()))
df=open(P("narrow","f963032_pc_shadow.diff")).read()
print("INFO rev2 stopgap check retired in rev3 (F7 is the design, Track P 8cf5006); see check.py rev3 checks")
pins=open(P("pins","PINS.txt")).read()
for s in ("bdae8d7ee0bc38ef93528ea3e9d3dcc47c5b8c95","f44d7b740aed240c834165672b6a862998ee4a12","3681b9baa28d005dfbad21ad9b5d46b243b1e323","38b147345a3d195637377a9d0f6017e2f50aa105","selection rationale"):
    chk("pins: "+s[:20],s in pins)
allf=[os.path.join(r,f) for r,_,fs in os.walk(D) for f in fs]
chk("stop-line: no bundle file",not any(f.endswith(".bundle") for f in allf))
m=[json.loads(l) for l in open(P("manhin","BAD_PARSES_FOR_MANHIN.jsonl"))]
chk("manhin: per-note summaries, no text field",len(m)>0 and all("text" not in r for r in m),"%d notes"%len(m))
print("RESULT","FAIL (expected: A/B criterion -> Not Ready)" if not ok else "ALL PASS")
