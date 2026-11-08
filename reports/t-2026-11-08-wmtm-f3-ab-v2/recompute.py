# stdlib only: re-derive gate 1 for v3 runs from extract.json + JUDGMENTS_v3.json
import json,os,sys
b=sys.argv[1] if len(sys.argv)>1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
x=json.load(open(os.path.join(b,'recompute','extract.json'))); j=json.load(open(os.path.join(b,'JUDGMENTS_v3.json')))
v={a:{r['goal']:r['verdict'] for r in j[a+'_v3']['rows']} for a in 'AB'}
cnt={}
for k,e in x.items():
    a=k[0]; c={'CORRECT':0,'WRONG':0,'UNCLEAR':0,'UNJUDGED':0}
    for g in e['goals']: c[v[a].get(g,'UNJUDGED')]+=1
    assert c['UNJUDGED']==0,(k,c); cnt[k]=c
A=[c for k,c in cnt.items() if k[0]=='A']; B=[c for k,c in cnt.items() if k[0]=='B']
ok=min(c['CORRECT'] for c in B)>=max(c['CORRECT'] for c in A) and max(c['WRONG'] for c in B)<=min(c['WRONG'] for c in A)
assert all(e['wmtm_rule']==0 for k,e in x.items() if k[0]=='B')
print({k:cnt[k] for k in sorted(cnt)}); print('RECOMPUTE_OK' if ok else 'GATE1_FAIL'); sys.exit(0 if ok else 1)
