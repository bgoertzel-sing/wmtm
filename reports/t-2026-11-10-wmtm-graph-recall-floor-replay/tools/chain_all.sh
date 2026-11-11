#!/bin/bash
# fixed-clock rerun: seeded stage (admit/graph-only/STI table) then unseeded v3-identical stage (count rule, s11)
set -u
N=/tmp/gfr/NOTES.txt; export GFR_FIXED_NOW=1794350000
SEED=/tmp/gfr/seed_journal.metta /tmp/gfr/tools/run_arms.sh full 20 A_p3:nov5_1f1a7a6f:A B_p3:nov5_1f1a7a6f:B A_533:ppv_r1_533c2274:A B_533:ppv_r1_533c2274:B A_f44:nov9_f44d7b74:A B_f44:nov9_f44d7b74:B
/tmp/gfr/tools/run_arms.sh noseed 20 A_p3:nov5_1f1a7a6f:A B_p3:nov5_1f1a7a6f:B A_533:ppv_r1_533c2274:A B_533:ppv_r1_533c2274:B A_f44:nov9_f44d7b74:A B_f44:nov9_f44d7b74:B
echo "$(date -Is) CHAIN_UNSEEDED_DONE" >> $N
