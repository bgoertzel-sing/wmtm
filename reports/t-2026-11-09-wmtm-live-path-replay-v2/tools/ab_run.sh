#!/bin/bash
# live-path-replay-v2 A/B replay. Same script, same code (wmtm-module branch hive/t-2026-11-09-wmtm-live-path-replay-v2), per-arm config + private spec copy.
# v1 fix: v0 ran A on the branch code (no wmtm-side rules) with live PeTTaChainer 36b3fe6 -> canary_fail; A must run live code.
# Usage: ab_run.sh <stage> <n>   stage in canary|pilot|full
set -u
W=/home/openclaw/research-agent/projects/omegaclaw/wmtm-module
V=/home/openclaw/research-agent/projects/omegaclaw/protocosmo2/iter-port/repos/vendor/wmtm-v0.7.0-rc2   # A = live code (_wmtm_pin.py WMTM_VENDOR)
R=/tmp/p3_out/ab/raw_spec.json
O=/tmp/lpr/ab/runs; st=$1; n=$2; mkdir -p $O
sha256sum $R >> $O/RAW_SHA.txt
for arm in A B; do
  d=$O/${st}_$arm; mkdir -p $d
  python3 -c "import json,sys;s=json.load(open('$R'));s['raw_items']=s['raw_items'][:$n];s['k']=$n;json.dump(s,open('$d/spec.json','w'))"
  echo "$(date -Is) start $st $arm" >> $O/run.log
  src=$V; [ $arm = B ] && src=$W
  (cd $src && timeout 900 python3 -m wmtm.workers.pc_shadow --spec $d/spec.json --out $d/shadow.jsonl --config /tmp/lpr/ab/$arm/worker_config.json --keep-spec > $d/stdout.txt 2> $d/stderr.txt)
  echo "$(date -Is) end $st $arm rc=$?" >> $O/run.log
done
sha256sum $R >> $O/RAW_SHA.txt
