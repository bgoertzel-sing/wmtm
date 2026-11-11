#!/bin/bash
F=/home/openclaw/research-agent/projects/omegaclaw/frozen_parses/store
P1=1f1a7a6fc42ffb8911afb7d2e95259fdfe8a0aef; S1=e4c4a76c7666d70f
P5=533c2274beac05439b08fa4dccd6b391fa38139e; S5=1585e873fc3151b8
for ind in False True; do
 ./run_b_ind.sh nov5_$ind $F $P1 $S1 $ind
 for r in r1 r2 r3; do ./run_b_ind.sh ${r}_$ind /tmp/npl/store/${r}_after $P5 $S5 $ind; done
done
echo ALLDONE >> /home/openclaw/scratch/ind/NOTES.txt
