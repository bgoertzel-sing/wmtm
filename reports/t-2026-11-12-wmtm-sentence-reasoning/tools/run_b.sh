#!/bin/bash
# usage: run_b.sh <name> <store dir> <pin> <prompt sha> <note-id file> [induction False|True] [min_shared]
# Offline B through the pc_shadow worker on a sandbox frozen store (guard on: any parse attempt raises), spec
# restricted to the note ids in <note-id file>.  Same flags as the trivial-filter and induction runs
# (t-2026-11-11-wmtm-induction tools/run_b_ind.sh), plus the matched-note spec.  Runs land outside the repo.
set -u
name=$1; store=$2; pin=$3; psha=$4; ids=$5; ind=${6:-False}; imin=${7:-3}
R=${WMTM_REPO:-$(cd "$(dirname "$0")/../../.." && pwd)}; export PYTHONPATH=$R
W=${SNR_WORK:-/home/openclaw/scratch/snr}; d=$W/runs/$name; rm -rf $d; mkdir -p $d
python3 - "$d" "$ind" "$imin" "$ids" <<'PY'
import json,sys
d=sys.argv[1]; IND=(sys.argv[2]=="True"); keep=[l.strip() for l in open(sys.argv[4]) if l.strip()]
f=json.load(open("/home/openclaw/research-agent/projects/omegaclaw/protocosmo2/iter-port/repos/memory/_wmtm_flags.json"))
f.update({"runtime_dir":d+"/runtime","shadow_dir":d+"/runtime/pc_shadow","semparse_dir":d+"/no_live_cache",
 "semparse_feed":False,"goalchainer":False,"shadow_normalise":False,
 "petta_dir":"/home/openclaw/research-agent/projects/omegaclaw/p1-engine/petta-3681b9b",
 "pettachainer_dir":"/home/openclaw/scratch/ppv/pc","_sandbox":"snr","shadow_induction":IND,"shadow_induction_min":int(sys.argv[3])})
import wmtm.runtime_config as rc
cfg=dict(rc.resolve()); cfg.update(f)
json.dump(cfg,open(d+"/worker_config.json","w"),indent=1,default=str)
spec=json.load(open("/home/openclaw/research-agent/projects/omegaclaw/frozen_parses/inputs/raw_spec_20notes.json"))
spec["raw_items"]=[it for it in spec["raw_items"] if it["id"] in keep]
assert len(spec["raw_items"])==len(keep), "note ids not all in spec"
spec["k"]=len(keep)
json.dump(spec,open(d+"/spec.json","w"))
PY
cd $R
echo "$(date -Is) RUN start $name store=$store pin=$pin psha=$psha ids=$(basename $ids) ind=$ind min=$imin" >> $W/NOTES.txt
WMTM_EVAL_FROZEN_STORE="$store|$pin|$psha" timeout 1800 python3 -m wmtm.workers.pc_shadow --spec $d/spec.json --out $d/shadow.jsonl --config $d/worker_config.json --keep-spec > $d/stdout.txt 2> $d/stderr.txt
echo "$(date -Is) RUN end $name rc=$?" >> $W/NOTES.txt
