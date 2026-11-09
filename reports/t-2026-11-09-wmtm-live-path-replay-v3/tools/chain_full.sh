#!/bin/bash
# after the pilot stage: full 20-note loop on A, B533, Bp3; then Bf44 once its cache fill finishes
set -u
N=/tmp/lpr/ab/runs/NOTES.txt
while ! grep -q "LOOP_STAGE_DONE pilot" $N; do sleep 20; done
/tmp/lpr/loop/run_arms.sh full 20 A:/tmp/lpr/ab/A/cache:A B533:/tmp/lpr/ab/B/cache:B Bp3:/tmp/lpr/ab/Bp3/cache:B
for i in $(seq 1 180); do grep -q "BF44_DONE" $N && break; sleep 30; done
if grep -q "BF44_DONE" $N; then /tmp/lpr/loop/run_arms.sh fullf44 20 Bf44:/tmp/lpr/ab/Bf44/cache:B
else echo "$(date -Is) LOOP Bf44 SKIPPED (fill not done in 90 min)" >> $N; fi
echo "$(date -Is) CHAIN_FULL_DONE" >> $N
