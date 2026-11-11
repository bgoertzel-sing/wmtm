#!/bin/bash
# usage: run_arms.sh <stage> <n> <arm:cachename:A|B> ...  sequential; A=/tmp/gfr/A (265062e), B=/tmp/gfr/B (26e7769)
set -u
st=$1; n=$2; shift 2
N=/tmp/gfr/NOTES.txt
for spec in "$@"; do
  arm=${spec%%:*}; rest=${spec#*:}; cache=/tmp/gfr/caches/${rest%%:*}; code=/tmp/gfr/${rest#*:}
  name=${st}_$arm
  python3 /tmp/gfr/tools/mkarm.py $name $cache >/dev/null; mkdir -p /tmp/gfr/loop/$name/state/_journal
  if [ -n "${SEED:-}" ]; then cp "$SEED" /tmp/gfr/loop/$name/state/_journal/journal.metta; echo "$(date -Is) SEED $name $(sha256sum $SEED|cut -c1-16)" >> /tmp/gfr/NOTES.txt; fi
  echo "$(date -Is) LOOP start $name n=$n cache=$cache code=$code $(git -C $code rev-parse --short HEAD) cache_sha=$(sha256sum $cache/cache.jsonl|cut -c1-16)" >> $N
  timeout 3000 python3 /tmp/gfr/tools/turn_loop.py --code $code --state /tmp/gfr/loop/$name/state --notes /home/openclaw/research-agent/projects/omegaclaw/frozen_parses/inputs/raw_spec_20notes.json --out /tmp/gfr/loop/$name/out --n $n > /tmp/gfr/loop/$name/stdout.txt 2> /tmp/gfr/loop/$name/stderr.txt
  echo "$(date -Is) LOOP end $name rc=$?" >> $N
done
echo "$(date -Is) LOOP_STAGE_DONE $st" >> $N
