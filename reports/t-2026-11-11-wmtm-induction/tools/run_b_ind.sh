#!/bin/bash
# usage: run_b.sh <name> <store dir> <pin> <prompt sha>  offline B through the pc_shadow worker, sandbox frozen store, guard on
set -u
name=$1; store=$2; pin=$3; psha=$4; ind=${5:-False}
R=/home/openclaw/research-agent/projects/omegaclaw/ind/wmtm-wt; export PYTHONPATH=$R
d=/home/openclaw/scratch/ind/runs/$name; rm -rf $d; mkdir -p $d
python3 - "$d" "$ind" <<'PY'
import json,sys
d=sys.argv[1]; IND=(sys.argv[2]=="True")
f=json.load(open("/home/openclaw/research-agent/projects/omegaclaw/protocosmo2/iter-port/repos/memory/_wmtm_flags.json"))
f.update({"runtime_dir":d+"/runtime","shadow_dir":d+"/runtime/pc_shadow","semparse_dir":d+"/no_live_cache",
 "semparse_feed":False,"goalchainer":False,"shadow_normalise":False,
 "petta_dir":"/home/openclaw/research-agent/projects/omegaclaw/p1-engine/petta-3681b9b",
 "pettachainer_dir":"/home/openclaw/scratch/ppv/pc","_sandbox":"ind","shadow_induction":IND,"shadow_induction_min":3})
import wmtm.runtime_config as rc
cfg=dict(rc.resolve()); cfg.update(f)
json.dump(cfg,open(d+"/worker_config.json","w"),indent=1,default=str)
json.dump(json.load(open("/home/openclaw/research-agent/projects/omegaclaw/frozen_parses/inputs/raw_spec_20notes.json")),open(d+"/spec.json","w"))
PY
cd $R
echo "$(date -Is) RUN start $name pin=$pin psha=$psha" >> /home/openclaw/scratch/ind/NOTES.txt
WMTM_EVAL_FROZEN_STORE="$store|$pin|$psha" timeout 1800 python3 -m wmtm.workers.pc_shadow --spec $d/spec.json --out $d/shadow.jsonl --config $d/worker_config.json --keep-spec > $d/stdout.txt 2> $d/stderr.txt
echo "$(date -Is) RUN end $name rc=$?" >> /home/openclaw/scratch/ind/NOTES.txt
