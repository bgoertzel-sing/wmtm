#!/bin/bash
# t-2026-11-17-wmtm-impl-premise-proving: run the shadow worker on each prebuilt spec (no parser calls), sequentially.
set -u
E=/srv/hive-evidence/t-2026-11-17-wmtm-impl-premise-proving
W=/home/openclaw/research-agent/projects/omegaclaw/ipp/wmtm-wt
PETTA=/home/openclaw/scratch/mh-rules-on-roman/PeTTa
VENDOR=/home/openclaw/scratch/ppv/pc
cd $E
for n in ${ARMS:-base off ip sg ipsg}; do
  (cd $W && PYTHONPATH=$W PETTA_PATH=$PETTA timeout 1800 python3 -m wmtm.workers.pc_shadow --spec $E/$n/spec.json --out $E/$n/shadow.jsonl --petta $PETTA --vendor $VENDOR --keep-spec > $E/$n/run.out 2>&1; echo "rc=$?" > $E/$n/run.log)
  echo "run $n $(cat $n/run.log) $(date +%T)"
done
echo DONE
