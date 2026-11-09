#!/bin/bash
# usage: run_b.sh <name> <normalise true|false> <pin> <prompt sha>   offline B through the pc_shadow worker, frozen store only
set -u
name=$1; norm=$2; pin=$3; psha=$4
R=/home/openclaw/research-agent/projects/omegaclaw/wmtm-module
F=/home/openclaw/research-agent/projects/omegaclaw/frozen_parses
d=/tmp/nrm/runs/$name; rm -rf $d; mkdir -p $d
python3 - "$d" "$norm" <<'PY'
import json,sys
d,norm=sys.argv[1],sys.argv[2]=="true"
f=json.load(open("/home/openclaw/research-agent/projects/omegaclaw/protocosmo2/iter-port/repos/memory/_wmtm_flags.json"))
f.update({"runtime_dir":d+"/runtime","shadow_dir":d+"/runtime/pc_shadow","semparse_dir":d+"/no_live_cache",
 "semparse_feed":False,"goalchainer":False,"shadow_normalise":norm,
 "petta_dir":"/home/openclaw/research-agent/projects/omegaclaw/p1-engine/petta-3681b9b",
 "pettachainer_dir":"/home/openclaw/scratch/ppv/pc","_sandbox":"nrm"})
import wmtm.runtime_config as rc
cfg=dict(rc.resolve()); cfg.update(f)
json.dump(cfg,open(d+"/worker_config.json","w"),indent=1,default=str)
json.dump(json.load(open("/home/openclaw/research-agent/projects/omegaclaw/frozen_parses/inputs/raw_spec_20notes.json")),open(d+"/spec.json","w"))
PY
cd $R
echo "$(date -Is) RUN start $name norm=$norm pin=$pin psha=$psha" >> $F/notes/NOTES.txt
WMTM_EVAL_FROZEN_STORE="$F/store|$pin|$psha" timeout 1800 python3 -m wmtm.workers.pc_shadow --spec $d/spec.json --out $d/shadow.jsonl --config $d/worker_config.json --keep-spec > $d/stdout.txt 2> $d/stderr.txt
echo "$(date -Is) RUN end $name rc=$?" >> $F/notes/NOTES.txt
