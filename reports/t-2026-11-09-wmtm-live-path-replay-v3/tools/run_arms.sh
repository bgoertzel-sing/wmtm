#!/bin/bash
# usage: run_arms.sh <stage> <n> <arm:cache:code> ...   sequential, one arm at a time (no shared CPU contention)
set -u
st=$1; n=$2; shift 2
VA=/home/openclaw/research-agent/projects/omegaclaw/protocosmo2/iter-port/repos/vendor/wmtm-v0.7.0-rc2
VB=/home/openclaw/research-agent/projects/omegaclaw/wmtm-module
for spec in "$@"; do
  arm=${spec%%:*}; rest=${spec#*:}; cache=${rest%%:*}; code=${rest#*:}
  [ "$code" = A ] && code=$VA || code=$VB
  name=${st}_$arm
  python3 /tmp/lpr/loop/mkarm.py $name $cache >/dev/null; mkdir -p /tmp/lpr/loop/$name/state/_journal
  echo "$(date -Is) LOOP start $name n=$n cache=$cache code=$code" >> /tmp/lpr/ab/runs/NOTES.txt
  timeout 3000 python3 /tmp/lpr/loop/turn_loop.py --code $code --state /tmp/lpr/loop/$name/state --notes /tmp/p3_out/ab/raw_spec.json --out /tmp/lpr/loop/$name/out --n $n > /tmp/lpr/loop/$name/stdout.txt 2> /tmp/lpr/loop/$name/stderr.txt
  echo "$(date -Is) LOOP end $name rc=$?" >> /tmp/lpr/ab/runs/NOTES.txt
done
echo "$(date -Is) LOOP_STAGE_DONE $st" >> /tmp/lpr/ab/runs/NOTES.txt
