# SCRATCH arm driver (t-2026-11-18-wmtm-clerk-ab): pilot2 path + shared ParseBudget ledger row per note attempt
# (extra rows booked post-hoc when glance reports calls>1), one retry per note on dependency_failed/job_failed/timeout,
# per-attempt rows to <home>/calls.jsonl. argv: demo home settings keyf model base_url n [offset]
import json, os, re, subprocess, sys, threading, time, urllib.request
from http.client import HTTPConnection
from pathlib import Path
demo, home, settings, keyf, model, bu, n = sys.argv[1:8]; n=int(n); off=int(sys.argv[8]) if len(sys.argv)>8 else 0
sys.path.insert(0,os.environ.get('CLERK_AB_WT',os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from wmtm.parse_budget import ParseBudget
PRE=7  # cos answer-3: book 7 rows before each Clerk note, extras after
BUD=ParseBudget('task',cfg={'parse_budget_dir':'~/.wmtm/parse_budget','parse_share_tasks_per_hour':20,'parse_live_dir':''})

def table_calls(home,gref):
    # host_id (post-...) is not the table arrival id; map via the glance job_ref -> its reading job
    want={gref, gref[len('glance-'):] if gref and gref.startswith('glance-') else gref}
    # true provider calls for one arrival: journal_turns carrying cost_microusd: (reading) or reasoning.call (glance)
    jobs=set(); evs=[]
    for l in open(home/'tables'/'operator-v4.jsonl',errors='ignore'):
        try: d=json.loads(l)
        except Exception: continue
        for e in d.get('events',[]):
            p=e.get('payload',{})
            if e['kind']=='job_opened' and p.get('job_ref') in want: jobs.add(p.get('job_ref'))
            evs.append(e)
    n=0
    for e in evs:
        p=e.get('payload',{})
        if e['kind']=='journal_turn' and p.get('job_ref') in jobs:
            fl=[str(x) for x in p.get('flags') or ()]
            if 'reasoning.call' in fl or any(x.startswith('cost_microusd:') for x in fl): n+=1
    return n, sorted(jobs)
home=Path(home); home.mkdir(parents=True, exist_ok=True, mode=0o700)
d=json.load(open('/tmp/p3_out/ab/raw_spec.json')); m={x['id']:x for x in d['raw_items']}
ids=[l.strip() for l in open(os.path.expanduser('~/scratch/ppv/wmtm/reports/t-2026-11-07-wmtm-f3-ab/NOTE_IDS.txt')) if l.strip()][off:off+n]
cmd=[sys.executable,'-B','-I',demo,'start','--provider','compatible','--home',str(home),'--settings',settings,
     '--key-file',keyf,'--port','0','--model',model,'--base-url',bu]
events=[]; changed=threading.Condition(); out={'ids':ids,'notes':[]}
log=open(home/'pilot-start.log','wb'); child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
try:
    t0=time.monotonic(); rec=None
    while time.monotonic()-t0<120 and child.poll() is None:
        try:
            rec=json.loads((home/'state'/'demo-service.json').read_text())
            if rec.get('phase')=='serving' and rec.get('port'): break
        except (OSError,ValueError): pass
        time.sleep(.1)
    out['warmup_s']=round(time.monotonic()-t0,1)
    assert rec and rec.get('phase')=='serving', 'start_failed'
    base='http://127.0.0.1:'+str(rec['port'])
    c=HTTPConnection('127.0.0.1',rec['port'],timeout=600); c.request('GET','/events'); r=c.getresponse()
    def recv():
        blk={}
        while True:
            raw=r.fp.readline(2_000_001)
            if not raw: return
            line=raw.decode().rstrip('\r\n')
            if not line:
                if blk.get('data'):
                    with changed: events.append({'name':blk.get('event'),'data':json.loads(blk['data'])}); changed.notify_all()
                blk={}
            elif not line.startswith(':'):
                k,_,v=line.partition(':'); blk[k]=v.lstrip()
    threading.Thread(target=recv,daemon=True).start()
    op=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def attempt(i,k):
        pre=[BUD.acquire({'task':'t-2026-11-18-wmtm-clerk-ab','note':i,'attempt':k,'prebook':j},wait=True,max_wait_s=3700) for j in range(PRE)]
        page=op.open(base+'/messages',timeout=10).read().decode()
        tok=re.search(r'name="token" value="([0-9a-f]+)"',page).group(1)
        req=urllib.request.Request(base+'/messages',data=json.dumps({'text':m[i]['content'],'token':tok}).encode(),
            headers={'Content-Type':'application/json','Accept':'application/json','Origin':base},method='POST')
        hid=json.loads(op.open(req,timeout=10).read())['arrival_id']; ts=time.monotonic()
        while time.monotonic()-ts<400:
            with changed:
                mine=[e for e in events if e['data'].get('arrival_id')==hid]
                if any(e['name'] in ('glance','dependency_failed','job_failed') for e in mine): break
                changed.wait(.5)
        mine=[e for e in events if e['data'].get('arrival_id')==hid]
        g=next((e['data'] for e in mine if e['name']=='glance'),None)
        time.sleep(2); calls,jobs=table_calls(home,(g or {}).get('job_ref')); calls=max(calls,1)
        extra=[BUD.acquire({'task':'t-2026-11-18-wmtm-clerk-ab','note':i,'attempt':k,'posthoc':True},wait=True,max_wait_s=3700) for _ in range(max(0,int(calls)-PRE))]
        row={'id':i,'attempt':k,'host_id':hid,'secs':round(time.monotonic()-ts,1),'ledger_ids':pre+extra,'prebooked':PRE,'unused_prebooked':max(0,PRE-int(calls)),
            'glance_status':(g or {}).get('status'),'calls':calls,'glance_calls':(g or {}).get('calls'),'jobs':jobs,'cost':(g or {}).get('cost'),
            'landings':[e['data'].get('canonical') for e in mine if e['name']=='landing'],
            'failures':[e['data'] for e in mine if e['name'] in ('dependency_failed','job_failed')],
            'event_names':[e['name'] for e in mine]}
        with open(home/'calls.jsonl','a') as fh: fh.write(json.dumps(row)+'\n')
        return row
    for i in ids:
        row=attempt(i,1)
        if row['failures'] or row['glance_status'] is None:
            row=attempt(i,2)
        out['notes'].append(row)
except Exception as e:
    out['error']=type(e).__name__+': '+str(e)[:200]
finally:
    if child.poll() is None:
        child.terminate()
        try: child.wait(20)
        except subprocess.TimeoutExpired: child.kill()
    json.dump(out,open(home/'PILOT-RESULT.json','w'),indent=1); print('done')
