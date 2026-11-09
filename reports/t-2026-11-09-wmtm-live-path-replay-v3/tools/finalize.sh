#!/bin/bash
# wait for CHAIN_FULL_DONE, then per-arm loop counts (ids/counts only) into the report dir
set -u
N=/tmp/lpr/ab/runs/NOTES.txt
R=/home/openclaw/research-agent/projects/omegaclaw/wmtm-module/reports/t-2026-11-09-wmtm-live-path-replay-v3
while ! grep -q CHAIN_FULL_DONE $N; do sleep 20; done
mkdir -p $R/runs_loop
dirs=""; for d in full_A full_B533 full_Bp3 fullf44_Bf44; do [ -f /tmp/lpr/loop/$d/out/turns.jsonl ] && dirs="$dirs /tmp/lpr/loop/$d"; done
python3 /tmp/lpr/loop/analyze_loop.py $dirs > $R/runs_loop/LOOP_RESULTS.json 2> $R/runs_loop/analyze.err
for d in $dirs; do b=$(basename $d); mkdir -p $R/runs_loop/$b
  cp $d/out/turns.jsonl $R/runs_loop/$b/
  python3 - "$d" "$R/runs_loop/$b" <<'PY'
import json,sys,os
d,o=sys.argv[1],sys.argv[2]
s=json.load(open(d+'/state/_wmtm_state.json'))
json.dump([{k:r.get(k) for k in ('item_id','content_hash','source_type','evicted_at_tick','final_utility','final_sti')} for r in s.get('forgetting_log',{}).get('records',[])],open(o+'/evictions.json','w'),indent=1)
G=[json.loads(l) for l in open(d+'/state/runtime/goalchainer/runs.jsonl')]
json.dump([{'source':g.get('source'),'status':g.get('status'),'canary_ok':(g.get('canary') or {}).get('ok'),'decisions':g.get('v2',{}).get('decisions'),'choices':g.get('v2',{}).get('choices'),'logged':g.get('logged')} for g in G],open(o+'/gc_runs.json','w'),indent=1)
S=[json.loads(l) for l in open(d+'/state/runtime/pc_shadow/shadow.jsonl')]
json.dump([{'status':x.get('status'),'items':x.get('items'),'atoms':x.get('atoms'),'goals_n':x.get('goals_n'),'proved':sum(1 for q in x.get('queries',[]) if q.get('ok')),'goals':[q['goal'] for q in x.get('queries',[])]} for x in S],open(o+'/shadow_summary.json','w'),indent=1)
PY
done
echo "$(date -Is) FINALIZE_DONE" >> $N
