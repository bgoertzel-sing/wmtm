#!/bin/bash
# v2: per-arm private spec copies (v1 void: both arms shared one spec file, the worker rewrites it in place)
set -u
exec 9>/tmp/f3/ab/v3.lock; flock -n 9 || { echo 'v3 already running' >&2; exit 1; }
V=/home/openclaw/research-agent/projects/omegaclaw/protocosmo2/iter-port/repos/vendor/wmtm-v0.7.0-rc2
B=/tmp/f3/wmtmB2
R=/tmp/p3_out/ab/raw_spec.json
O=/tmp/f3/ab/v3r1
python3 - <<'PY'
import json
s=json.load(open('/tmp/p3_out/ab/raw_spec.json'))
for name,n in (('canary',1),('pilot',4),('full',20)):
    for arm in 'AB':
        c=dict(s); c['raw_items']=s['raw_items'][:n]; c['k']=n
        json.dump(c,open(f'/tmp/f3/ab/v3r1/{name}_{arm}_spec.json','w'))
PY
sha256sum $R > $O/RAW_SHA_before.txt
for stage in canary pilot full; do
  for arm in A B; do
    d=$O/${stage}_$arm; mkdir -p $d
    [ -f $O/${stage}_${arm}_spec.json ] || { echo "$(date -Is) MISSING spec $stage $arm" >> $O/run.log; exit 2; }
    cp $O/${stage}_${arm}_spec.json $d/input_spec.json
    src=$V; [ $arm = B ] && src=$B
    echo "$(date -Is) start $stage $arm" >> $O/run.log
    (cd $src && timeout 900 python3 -m wmtm.workers.pc_shadow --keep-spec --spec $O/${stage}_${arm}_spec.json --out $d/shadow.jsonl --config /tmp/f3/ab/$arm/worker_config.json > $d/stdout.txt 2> $d/stderr.txt)
    echo "$(date -Is) end $stage $arm rc=$?" >> $O/run.log
  done
done
sha256sum $R > $O/RAW_SHA_after.txt
echo DONE >> $O/run.log
