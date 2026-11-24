#!/bin/bash
# D-arm load via clerk-ab pinned recipe (a1varload/run.sh), same pins.
export CLERK_AB_TMPL=/home/openclaw/scratch/pma/sph-24e37182/templates
export PYTHONPATH=/tmp/yamlonly:/home/openclaw/scratch/p4/r/PeTTaChainer:/home/openclaw/scratch/p4/PeTTa/python
PY=/home/openclaw/research-agent/projects/petta-memory/.venv-pettachainer/bin/python
E=/srv/hive-evidence/t-2026-11-23-wmtm-gateway-vs-direct; C=/srv/hive-evidence/t-2026-11-18-wmtm-clerk-ab
cd $E
for r in "$@"; do
  ATOMS_OUT=$E/dload/atoms-$r.jsonl timeout 3600 $PY $C/pins/load_arm.py $E/$r/run/parsed.jsonl > dload/load-$r.out 2> dload/load-$r.err; echo "EXIT $r $? $(date +%T)" >> dload/status
  python3 $C/pins/goals_arm.py dload/atoms-$r.jsonl $C/pins/seeded_rules.pettachainer-master.metta dload/goals-$r.jsonl > dload/goals-$r.out 2>&1; echo "GOALS $r $? $(date +%T)" >> dload/status
done
