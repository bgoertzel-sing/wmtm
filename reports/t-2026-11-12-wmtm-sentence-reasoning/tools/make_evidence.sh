#!/bin/bash
# Assemble the evidence folder (pop-os only; holds note-derived stores, specs and runs) and write SHA256SUMS.
# Usage: make_evidence.sh [EVIDENCE_DIR]   (reads ~/scratch/snr, /tmp/npl/store, ~/scratch/sp2/runs/calls.jsonl)
set -eu
EV=${1:-/var/tmp/hive-evidence-t-2026-11-12-wmtm-sentence-reasoning}; W=${SNR_WORK:-/home/openclaw/scratch/snr}
mkdir -p $EV/stores $EV/runs $EV/inputs
for s in s1 s2 s3; do mkdir -p $EV/stores/$s; cp -p $W/store/$s/frozen.jsonl $EV/stores/$s/; cp -p $W/caches/$s/cache.jsonl $W/caches/$s/rejects.jsonl $EV/stores/$s/; cp -p $W/rec_$s/recovered.jsonl $W/rec_$s/counts.json $W/rec_$s/rerejects.jsonl $EV/stores/$s/ 2>/dev/null || true; done
for r in r1 r2 r3; do mkdir -p $EV/stores/${r}_after; cp -p /tmp/npl/store/${r}_after/frozen.jsonl $EV/stores/${r}_after/; cp -p $W/canary/rec_$r/counts.json $EV/stores/${r}_after/rebuild_counts.json; done
cp -p $W/caches/rebuild.json $W/ids_M17.txt $W/ids_P5.txt $W/ids_P4.txt $W/NOTES.txt $EV/inputs/
cp -p $W/judge/hand_verdicts.json $EV/
for d in $W/runs/*; do n=$(basename $d); mkdir -p $EV/runs/$n; cp -p $d/admit.json $d/shadow.jsonl $d/spec.json $d/worker_config.json $d/stderr.txt $d/stdout.txt $EV/runs/$n/; [ -d $d/no_live_cache ] && cp -rp $d/no_live_cache $EV/runs/$n/ || true; done
L=/home/openclaw/scratch/sp2/runs/calls.jsonl
python3 - "$W/calls_before.txt" "$L" "$EV/parse_calls.json" "$W" <<'PY'
import json,sys,hashlib,glob
b=open(sys.argv[1]).read().split(); L=sys.argv[2]
hits=sum(open(f,errors="replace").read().count("parse call refused")+open(f,errors="replace").read().count("FrozenParseError") for f in glob.glob(sys.argv[4]+"/runs/*/stderr.txt"))
json.dump({"log":L,"before":{"lines":int(b[0]),"sha256":b[1]},"after":{"lines":sum(1 for _ in open(L)),"sha256":hashlib.sha256(open(L,"rb").read()).hexdigest()},"stub_hits":hits},open(sys.argv[3],"w"),indent=1)
PY
cd $EV && find . -type f ! -name SHA256SUMS | sort | xargs sha256sum > SHA256SUMS && wc -l SHA256SUMS
