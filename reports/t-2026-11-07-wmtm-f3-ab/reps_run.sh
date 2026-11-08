#!/bin/bash
# B (and A) repeat runs: per-run private spec copy, sequential; measures timeout-driven variance of the proved set
set -u
V=/home/openclaw/research-agent/projects/omegaclaw/protocosmo2/iter-port/repos/vendor/wmtm-v0.7.0-rc2
for i in 1 2 3 4 5; do for arm in A B; do
  d=/tmp/f3/ab/reps/${arm}_$i; mkdir -p $d
  python3 -c "import json;json.dump(json.load(open('/tmp/p3_out/ab/raw_spec.json')),open('$d/spec.json','w'))"
  src=$V; [ $arm = B ] && src=/tmp/f3/wmtmB
  (cd $src && timeout 600 python3 -m wmtm.workers.pc_shadow --spec $d/spec.json --out $d/shadow.jsonl --config /tmp/f3/ab/$arm/worker_config.json --keep-spec > $d/stdout.txt 2>&1)
  echo "$(date -Is) $arm $i rc=$?" >> /tmp/f3/ab/reps/run.log
done; done
echo DONE >> /tmp/f3/ab/reps/run.log
