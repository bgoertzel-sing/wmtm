"""Counts-only recompute for t-2026-11-18-wmtm-clerk-ab evidence (no note text printed).
Usage: python3 recompute_counts.py <evidence_dir>/a1frozen <driver_pid> [ledger.snapshot.jsonl]
(calls.jsonl carries no pid field, so the driver pid is passed explicitly.)"""
import json, ast, sys, os, statistics as st
d = sys.argv[1]
def L(p): return [json.loads(l) for l in open(p) if l.strip()]
def V(x): return x if isinstance(x, (dict, list)) else ast.literal_eval(x)
calls = L(os.path.join(d, 'calls.jsonl')); parsed = L(os.path.join(d, 'parsed.jsonl'))
pid = int(sys.argv[2])
led = L(sys.argv[3] if len(sys.argv) > 3 else os.path.join(d, 'ledger.snapshot.jsonl'))
inst = []; bad = 0
for x in parsed:
    r = (V(x['reply']).get('response') or {})
    if not isinstance(r.get('instances'), list) or V(x['reply']).get('error'): bad += 1
    inst.append(len(r.get('instances') or []))
us = [V(c['usage']) for c in calls]
http429 = sum(1 for c in calls if '429' in str(c.get('error') or ''))
rows = [r for r in led if r.get('task') == 't-2026-11-18-wmtm-clerk-ab' and r.get('pid') == pid]
out = {'sentences': len(parsed), 'unique_ids': len({V(x['reply']).get('response', {}).get('id') for x in parsed}),
       'docs': len({x['doc'] for x in parsed}), 'bad': bad, 'http429': http429, 'calls': len(calls),
       'call_ids_per_call': sorted({len(V(c['call_ids'])) for c in calls}),
       'secs_median': st.median(float(c['secs']) for c in calls),
       'prompt_tokens': sum(int(u.get('prompt_tokens') or 0) for u in us),
       'cached': sum(int(u.get('cached') or 0) for u in us), 'output': sum(int(u.get('output') or 0) for u in us),
       'instances': sum(inst), 'zero_instance_sentences': sum(1 for n in inst if n == 0),
       'ledger_rows_task_pid': len(rows), 'ledger_rows_task_other_pids': sum(1 for r in led if r.get('task') == 't-2026-11-18-wmtm-clerk-ab' and r.get('pid') != pid),
       'ledger_rows_total': len(led)}
print(json.dumps(out, indent=1))
