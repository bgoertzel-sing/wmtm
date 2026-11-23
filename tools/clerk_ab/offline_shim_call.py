import sys, os, json, tempfile, hashlib
sys.path.insert(0, 'parser-clerk'); sys.path.insert(0, 'parser-clerk/tests/host_live')
import fakes
key = 'sk-test-planted'
fakes.install(hashlib.sha256(key.encode()).hexdigest())
from parser_clerk import preview
state = tempfile.mkdtemp(prefix='clerk-shim-')
env = dict(os.environ, PARSER_CLERK_HYPERNOIA_SRC=os.path.abspath('shim/hypernoia-src/src'))
call = preview.compatible_call(state, env, 'compatible:test', 'remote-model', 'http://127.0.0.1:9/v1', key, sys.stderr)
packet = {'system': 'MANUAL', 'idempotency_key': 'k1', 'messages': [], 'remaining': {'call_ceiling_microusd': 100000},
  'request': {'context': {'arrival_text': 'hello world'}, 'arrival': {'event_id': 'ev1'}},
  'submission': {'job_ref': 'j', 'operation_id': 'o', 'arrival_ref': 'a', 'snapshot_ref': 's'}}
r = call(packet)
print('reply kind ok:', '"submit_parse"' in r.content, 'cost', r.cost_microusd, 'finish', r.finish_reason)
print('usage', call.last_usage)
print('calls', [{k: c[k] for k in ('model','max_tokens','main_thread','keys')} for c in fakes.RECORD['calls']])
print('meter', open(preview.spend_meter(state)).read())
