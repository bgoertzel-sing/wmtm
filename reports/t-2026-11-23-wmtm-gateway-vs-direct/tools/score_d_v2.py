#!/usr/bin/env python3
"""v2 (review 1): D vs G with G = 4 runs (a1frozen G0 + a1varfull r1-r3 G1-G3).
Agreement (signature=(t,span), Jaccard, empty/empty=1), instance counts with paired bootstrap,
unmapped/issues per sentence, latency per call. Ids/counts only.  Usage: score_d_v2.py EVID CLERKAB_EVID SCRATCH"""
import json,sys,random,itertools,statistics as st
E,C,S=sys.argv[1:4]
def load(p):
    out={}
    for l in open(p):
        if not l.strip(): continue
        o=json.loads(l); r=(o.get('reply') or {}).get('response')
        if isinstance(r,dict) and isinstance(r.get('instances'),list):
            sig=set()
            for i in r['instances']:
                if isinstance(i,dict):
                    sp=i.get('span'); sp=sp if isinstance(sp,str) else json.dumps(sp,sort_keys=True); sig.add((i.get('t'),sp))
            out[o['id']]={'sig':sig,'n_inst':len(r['instances']),'unmapped':len(r.get('unmapped') or []),'issues':len(r.get('issues') or [])}
        else: out[o['id']]=None
    return out
def secs(p): return [json.loads(l)['secs'] for l in open(p) if l.strip()]
P={'D1':E+'/d1/run','D2':E+'/d2/run','G0':C+'/a1frozen','G1':S+'/a1varfull/r1','G2':S+'/a1varfull/r2','G3':S+'/a1varfull/r3'}
R={k:load(v+'/parsed.jsonl') for k,v in P.items()}
ids=[json.loads(l)['id'] for l in open(S+'/a1varfull/sel.jsonl') if l.strip()]
G=['G0','G1','G2','G3']; D=['D1','D2']
jac=lambda a,b:1.0 if not (a|b) else len(a&b)/len(a|b)
def boot(xs,n=5000):
    random.seed(0); b=sorted(st.mean(random.choices(xs,k=len(xs))) for _ in range(n))
    return {'mean':round(st.mean(xs),3),'ci95':[round(b[int(.025*n)],3),round(b[int(.975*n)],3)],'n':len(xs)}
ok=lambda ks:[i for i in ids if all(R[k].get(i) is not None for k in ks)]
full=ok(['D1']+G); both=ok(D+G)
wG=lambda i:st.mean(jac(R[a][i]['sig'],R[b][i]['sig']) for a,b in itertools.combinations(G,2))
cDG=lambda d,i:st.mean(jac(R[d][i]['sig'],R[g][i]['sig']) for g in G)
cnt=lambda k,i:R[k][i]['n_inst']
res={'metric':'signature=(t,span); jaccard; empty/empty=1; bootstrap seed0 5000','coverage':{k:sum(1 for i in ids if i in R[k]) for k in R},
 'struct_bad':{k:sum(1 for i in ids if i in R[k] and R[k][i] is None) for k in R},'n_full':len(full),'n_both':len(both)}
res['agreement']={
 'within_G4@full':round(st.mean(wG(i) for i in full),3),
 'cross_D1_G4@full':round(st.mean(cDG('D1',i) for i in full),3),
 'cross_minus_within@full':boot([cDG('D1',i)-wG(i) for i in full]),
 'pairs@full':{f'{a}-{b}':round(st.mean(jac(R[a][i]['sig'],R[b][i]['sig']) for i in full),3) for a,b in itertools.combinations(['D1']+G,2)}}
if both:
    res['agreement'].update({'within_D@both':round(st.mean(jac(R['D1'][i]['sig'],R['D2'][i]['sig']) for i in both),3),
     'within_G4@both':round(st.mean(wG(i) for i in both),3),
     'cross_D2_G4@both':round(st.mean(cDG('D2',i) for i in both),3),
     'withinD_minus_withinG@both':boot([jac(R['D1'][i]['sig'],R['D2'][i]['sig'])-wG(i) for i in both])})
res['instances_per_sentence']={k:round(st.mean(cnt(k,i) for i in (full if k!='D2' else both)),3) for k in R}
res['instances_per_sentence_basis']='D1,G* over n_full; D2 over n_both'
res['inst_D1_minus_meanG@full']=boot([cnt('D1',i)-st.mean(cnt(g,i) for g in G) for i in full])
res['inst_G_each_minus_meanOtherG@full']={g:boot([cnt(g,i)-st.mean(cnt(h,i) for h in G if h!=g) for i in full]) for g in G}
if both: res['inst_meanD_minus_meanG@both']=boot([st.mean(cnt(d,i) for d in D)-st.mean(cnt(g,i) for g in G) for i in both])
res['unmapped_per_sentence']={k:round(st.mean(R[k][i]['unmapped'] for i in (full if k!='D2' else both)),3) for k in R}
res['issues_per_sentence']={k:round(st.mean(R[k][i]['issues'] for i in (full if k!='D2' else both)),3) for k in R}
res['unmapped_D1_minus_meanG@full']=boot([R['D1'][i]['unmapped']-st.mean(R[g][i]['unmapped'] for g in G) for i in full])
res['issues_D1_minus_meanG@full']=boot([R['D1'][i]['issues']-st.mean(R[g][i]['issues'] for g in G) for i in full])
res['latency_secs']={k:(lambda s:{'calls':len(s),'mean':round(st.mean(s),1),'median':round(st.median(s),1)})(secs(v+'/calls.jsonl')) for k,v in P.items()}
res['per_sentence']={i:{k:(None if R[k].get(i) is None else {'n':R[k][i]['n_inst'],'u':R[k][i]['unmapped'],'iss':R[k][i]['issues']}) for k in R} for i in ids}
json.dump(res,open(E+'/score/d_vs_g4_summary.json','w'),indent=1)
print(json.dumps({k:v for k,v in res.items() if k!='per_sentence'},indent=1))
