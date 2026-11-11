#!/bin/bash
# after CHAIN_UNSEEDED_DONE: admit table (all arms), per-arm judge on the last kept spec + its matching shadow record
set -u
G=/tmp/gfr; N=$G/NOTES.txt
V3=/home/openclaw/research-agent/projects/omegaclaw/wmtm-module/reports/t-2026-11-09-wmtm-live-path-replay-v3
while ! grep -q CHAIN_UNSEEDED_DONE $N; do sleep 30; done
sleep 5
mkdir -p $G/res
python3 $G/tools/admit_table.py $G/loop/full_* $G/loop/noseed_* > $G/res/admit_table.json 2> $G/res/admit_table.err
python3 $V3/tools/analyze_loop.py $G/loop/full_* $G/loop/noseed_* > $G/res/loop_results.json 2> $G/res/analyze.err
python3 - <<'PY' > $G/res/pairs.txt 2> $G/res/pairs.err
import json, glob, os
G = "/tmp/gfr"; args = []
for d in sorted(glob.glob(G + "/loop/full_*") + glob.glob(G + "/loop/noseed_*")):
    arm = os.path.basename(d); specs = glob.glob(G + "/specs/%s/spec_c*.json" % arm)
    S = [json.loads(l) for l in open(d + "/state/runtime/pc_shadow/shadow.jsonl")]
    best = None
    for f in specs:
        sp = json.load(open(f))
        m = [x for x in S if abs((x.get("spec_ts") or 0) - (sp.get("ts") or -1)) < 1e-6]
        if m and (best is None or sp["ts"] > best[0]): best = (sp["ts"], f, m[-1])
    if not best: print("NOPAIR", arm); continue
    o = G + "/judge/" + arm; os.makedirs(o, exist_ok=True)
    os.system("cp %s %s/spec.json" % (best[1], o)); open(o + "/shadow.jsonl", "w").write(json.dumps(best[2]) + "\n")
    print("PAIR", arm, os.path.basename(best[1]), best[2].get("cycle"), best[2].get("goals_n"))
PY
keys=""; for d in $G/judge/*; do keys="$keys $(basename $d)=$d"; done
python3 $V3/tools/build_extract.py $G/res/extract.json $keys > $G/res/extract.out 2>&1
python3 - <<'PY' > $G/res/judge.out 2>&1
import json, subprocess
ext = json.load(open("/tmp/gfr/res/extract.json"))
V3 = "/home/openclaw/research-agent/projects/omegaclaw/wmtm-module/reports/t-2026-11-09-wmtm-live-path-replay-v3"
for stage in ("full", "noseed"):
    for p in ("p3", "533", "f44"):
        sub = {("A" if "_A_" in k else "B") + "_" + k: v for k, v in ext.items() if k.startswith(stage + "_") and k.endswith("_" + p)}
        fn = "/tmp/gfr/res/ext_%s_%s.json" % (stage, p); json.dump(sub, open(fn, "w"))
        print("=== %s %s" % (stage, p), flush=True)
        print(subprocess.run(["python3", V3 + "/tools/judge.py", fn, V3 + "/runs_offline/W4_f3v3.json"], capture_output=True, text=True).stdout, flush=True)
PY
echo "$(date -Is) FINALIZE_GFR_DONE" >> $N
