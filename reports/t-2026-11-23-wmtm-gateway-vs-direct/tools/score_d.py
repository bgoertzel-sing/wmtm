#!/usr/bin/env python3
"""Score D (direct Anthropic) vs G (gateway: A1 variance runs r1-r3) with the a1varfull metric:
signature=(t,span) (non-str span json-dumped); iu=|cap|/|cup| over runs; pair=mean pairwise Jaccard (empty/empty=1)."""
import json, sys, itertools, statistics as st
def load(p):
    out={}
    for l in open(p):
        if not l.strip(): continue
        o=json.loads(l); r=o.get('reply') or {}; resp=r.get('response')
        sig=None
        if isinstance(resp,dict) and isinstance(resp.get('instances'),list):
            sig=set()
            for i in resp['instances']:
                if not isinstance(i,dict): continue
                sp=i.get('span'); sp=sp if isinstance(sp,str) else json.dumps(sp,sort_keys=True)
                sig.add((i.get('t'),sp))
        out[o['id']]=sig
    return out
def jac(a,b):
    u=a|b; return 1.0 if not u else len(a&b)/len(u)
def iu(sets):
    u=set().union(*sets); return 1.0 if not u else len(set.intersection(*sets))/len(u)
def q(xs):
    xs=sorted(xs); n=len(xs); return [round(xs[int(f*(n-1))],3) for f in (.25,.5,.75)]
E,S=sys.argv[1],sys.argv[2]
runs={'D1':load(f'{E}/d1/run/parsed.jsonl'),'D2':load(f'{E}/d2/run/parsed.jsonl')}
for k in ('r1','r2','r3'): runs['G'+k[1]]=load(f'{S}/a1varfull/{k}/parsed.jsonl')
ids=[json.loads(l)['id'] for l in open(f'{S}/a1varfull/sel.jsonl') if l.strip()]
res={'metric':'signature=(t,span); jaccard; empty/empty=1','n_ids':len(ids),'struct_bad':{k:sum(1 for i in ids if i in v and v[i] is None) for k,v in runs.items()},'coverage':{k:sum(1 for i in ids if i in v) for k,v in runs.items()},'sig_counts':{k:sum(len(v[i]) for i in ids if v.get(i)) for k,v in runs.items()}}
def pairstat(a,b,sub):
    xs=[jac(runs[a][i],runs[b][i]) for i in sub]
    return {'n':len(xs),'mean':round(st.mean(xs),3),'quart':q(xs),'eq1':sum(x==1 for x in xs),'lt05':sum(x<.5 for x in xs)}
ok=lambda ks:[i for i in ids if all(runs[k].get(i) is not None for k in ks)]
full=ok(['D1','G1','G2','G3']); d2=ok(['D1','D2','G1','G2','G3'])
P={}
for a,b in [('G1','G2'),('G1','G3'),('G2','G3'),('D1','G1'),('D1','G2'),('D1','G3')]: P[f'{a}-{b}@full']=pairstat(a,b,full)
for a,b in [('D1','D2'),('G1','G2'),('G1','G3'),('G2','G3'),('D2','G1'),('D2','G2'),('D2','G3'),('D1','G1'),('D1','G2'),('D1','G3')]: P[f'{a}-{b}@d2sub']=pairstat(a,b,d2)
res['pairs']=P
def grp(names,sub): return round(st.mean(P[f'{a}-{b}@{sub}']['mean'] for a,b in names),3)
res['agg']={'within_G@full':grp([('G1','G2'),('G1','G3'),('G2','G3')],'full'),'cross_D1G@full':grp([('D1','G1'),('D1','G2'),('D1','G3')],'full'),
 'within_D@d2sub':P['D1-D2@d2sub']['mean'],'within_G@d2sub':grp([('G1','G2'),('G1','G3'),('G2','G3')],'d2sub'),
 'cross_DG@d2sub':grp([('D1','G1'),('D1','G2'),('D1','G3'),('D2','G1'),('D2','G2'),('D2','G3')],'d2sub'),
 'iu_G3@full':round(st.mean(iu([runs[k][i] for k in('G1','G2','G3')]) for i in full),3),
 'iu_G3@d2sub':round(st.mean(iu([runs[k][i] for k in('G1','G2','G3')]) for i in d2),3),
 'iu_D2_D1_G1@d2sub':round(st.mean(iu([runs[k][i] for k in('D1','D2','G1')]) for i in d2),3)}
res['n_full'],res['n_d2sub']=len(full),len(d2)
# per-sentence (ids only, no text)
res['per_sentence']={i:{'n':{k:(len(runs[k][i]) if runs[k].get(i) is not None else None) for k in runs},
  'D1G_mean':round(st.mean(jac(runs['D1'][i],runs[g][i]) for g in('G1','G2','G3')),3) if i in full else None,
  'D1D2':round(jac(runs['D1'][i],runs['D2'][i]),3) if i in d2 else None} for i in ids}

import random
def boot(xs,seed=0,n=5000):
    random.seed(seed); b=sorted(st.mean(random.choices(xs,k=len(xs))) for _ in range(n))
    return [round(st.mean(xs),3),round(b[int(.025*n)],3),round(b[int(.975*n)],3)]
wG=lambda i:st.mean([jac(runs['G1'][i],runs['G2'][i]),jac(runs['G1'][i],runs['G3'][i]),jac(runs['G2'][i],runs['G3'][i])])
res['boot_seed0_5000']={'cross_D1G_minus_withinG@full':boot([st.mean(jac(runs['D1'][i],runs[g][i]) for g in('G1','G2','G3'))-wG(i) for i in full]),
 'withinD_minus_withinG@d2sub':boot([jac(runs['D1'][i],runs['D2'][i])-wG(i) for i in d2])}
json.dump(res,open(f'{E}/score/d_vs_g_summary.json','w'),indent=1)
print(json.dumps({k:res[k] for k in('n_ids','n_full','n_d2sub','struct_bad','coverage','sig_counts','agg','boot_seed0_5000')},indent=1))
