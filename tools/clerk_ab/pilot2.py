# SCRATCH (t-2026-11-18-wmtm-clerk-ab step1 pilot): same start+HTTP path as kit smoke_main, but posts N real notes.
import json, os, re, subprocess, sys, threading, time, urllib.request
from http.client import HTTPConnection
from pathlib import Path
demo, home, settings, keyf, model, bu, n = sys.argv[1:8]; n=int(n)
home=Path(home); home.mkdir(parents=True, exist_ok=True, mode=0o700)
d=json.load(open('/tmp/p3_out/ab/raw_spec.json')); m={x['id']:x for x in d['raw_items']}
ids=[l.strip() for l in open(os.path.expanduser('~/scratch/ppv/wmtm/reports/t-2026-11-07-wmtm-f3-ab/NOTE_IDS.txt')) if l.strip()][:n]
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
    for i in ids:
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
        out['notes'].append({'id':i,'host_id':hid,'secs':round(time.monotonic()-ts,1),
            'glance_status':(g or {}).get('status'),'calls':(g or {}).get('calls'),'cost':(g or {}).get('cost'),
            'landings':[e['data'].get('canonical') for e in mine if e['name']=='landing'],
            'failures':[e['data'] for e in mine if e['name'] in ('dependency_failed','job_failed')],
            'event_names':[e['name'] for e in mine]})
except Exception as e:
    out['error']=type(e).__name__+': '+str(e)[:200]
finally:
    if child.poll() is None:
        child.terminate()
        try: child.wait(20)
        except subprocess.TimeoutExpired: child.kill()
    json.dump(out,open(home/'PILOT-RESULT.json','w'),indent=1); print('done')
