#!/bin/bash
# t-2026-11-17-wmtm-variable-implication-test: lower + goals + PeTTaChainer for the invented notes, two arms:
#   pr43   = PR 43 (a70dc86) defaults (shadow_extra_rules off) + note_impl_goals (1dd5f47 logic) + asks
#   pr43xr = shadow_extra_rules on, minus the four rules andy dropped (as nig-v2 'both')
#   diag   = pr43 + the run_cases.py DIAG atoms (thing / narrowed-class membership) -- diagnostic only, not the master path
# Usage: run_all.sh PARSED OUTDIR
set -u
H=$(cd "$(dirname "$0")" && pwd); R=$(cd "$H/../../.." && pwd)
P=$1; E=$2
T=$HOME/scratch/pma/sph-24e37182/templates
PETTA=/home/openclaw/research-agent/projects/omegaclaw/p1-engine/petta-3681b9b
VENDOR=/home/openclaw/research-agent/projects/omegaclaw/p1-engine/pettachainer-bdae8d7e
D=xr_directive_inherit,xr_close_closes,xr_hour_order,xr_minute_order
mkdir -p $E; md5sum $P > $E/parsed.md5
git -C $R rev-parse HEAD > $E/repo_head.txt; git -C $(dirname $T) rev-parse HEAD > $E/sph_head.txt
for a in pr43:0:-:0 pr43xr:1:$D:0 diag:0:-:1; do
  IFS=: read n x d g <<<"$a"
  mkdir -p $E/$n
  python3 $H/run_cases.py $H/../notes.json $P $T $R $E/$n $x $d $g > $E/$n/build.out 2> $E/$n/build.err
  echo "== $n build rc=$?"
  (cd $R && WMTM_PC_SHADOW_STEPS=30 timeout 900 python3 -m wmtm.workers.pc_shadow --spec $E/$n/spec.json --out $E/$n/shadow.jsonl \
      --petta $PETTA --vendor $VENDOR --budget 600 --keep-spec > $E/$n/run.out 2>&1); echo "== $n shadow rc=$?"
  python3 $H/summarize.py $E/$n > $E/$n/summary.md; echo "== $n summary rc=$?"
done
