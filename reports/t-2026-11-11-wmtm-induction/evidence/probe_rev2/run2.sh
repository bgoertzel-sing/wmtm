#!/bin/bash
export PATH=/home/openclaw/research-agent/projects/petta-memory/toolchains/local/swi-prolog-9.3.36/lib/swipl/bin/x86_64-linux:$PATH
cd /home/openclaw/scratch/ppv/pc/examples/indprobe
for f in d_frozen_cleanup_done e_frozen_result_alias; do PETTA_STACK_LIMIT=4g PETTA_TABLE_LIMIT=2g timeout 300 /home/openclaw/research-agent/projects/omegaclaw/p1-engine/petta-3681b9b/run.sh $f.metta > $f.out 2>&1; echo "$f rc=$?" >> DONE2.txt; done
echo ALLDONE >> DONE2.txt
