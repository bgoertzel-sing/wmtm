#!/bin/bash
# All matched-note runs: B = sentence stores s1/s2/s3, A = whole-note stores r1/r2/r3_after, same spec per set.
set -u; H=$(cd "$(dirname "$0")" && pwd); W=${SNR_WORK:-/home/openclaw/scratch/snr}
P=533c2274beac05439b08fa4dccd6b391fa38139e; S=1585e873fc3151b8
for ind in False True; do
 for set in M17:s1 P5:s3 P4:s2; do
  ids=$W/ids_${set%%:*}.txt; b=${set##*:}
  $H/run_b.sh ${set%%:*}_${b}_$ind $W/store/$b $P $S $ids $ind
  for r in r1 r2 r3; do $H/run_b.sh ${set%%:*}_${r}_$ind /tmp/npl/store/${r}_after $P $S $ids $ind; done
 done
done
echo ALLDONE >> $W/NOTES.txt
