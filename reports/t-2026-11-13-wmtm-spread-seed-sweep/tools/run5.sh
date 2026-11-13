#!/bin/sh
# t-2026-11-13-wmtm-spread-seed-sweep: the spread-seeds probe's replay in five seed-rule arms + the keyword-only
# reference A (vm2 proto-hive container, user space).  Inputs are the probe's, byte for byte (SHA256SUMS.txt):
# journal seed 20261111, data/turns.json, data/labels.json, capacity 60, recall_budget 10 (default), floor 0.1,
# reasoner off, fixed clock.  The arms differ only in the three seed-rule variables below.
#   A    = worktree probe-A (265062e), keyword-only recall: the reference for "hubs lost" (as in the probe)
#   E    = recall_spread_seeds=turn                                      (arm 1, must equal the probe's E)
#   F50  = turn + recall_spread_fallback_pct=50  (top 50% STI, only on turns with no keyword match; the plan)  (arm 2)
#   F25  = turn + recall_spread_fallback_pct=25                                                          (arm 3)
#   P10  = turn + recall_spread_add_pct=10       (top 10% STI added on every turn; Ben's reading)        (arm 4)
#   P25  = turn + recall_spread_add_pct=25                                                               (arm 5)
# $1 = the folder holding the worktree probe-A (265062e); $2 = this branch's worktree.
set -e
. /hive/protocosmo/workspace/projects/wmtm/env-gapcheck/env.sh      # python 3.10.22 venv (env-gapcheck), toolchain git
R=$(cd "$(dirname "$0")/.." && pwd); cd "$R"
python3 tools/gen_journal.py --out data                            # seed 20261111 (default); deterministic
unset WMTM_RECALL_SPREAD_SEEDS WMTM_RECALL_SPREAD_FALLBACK_PCT WMTM_RECALL_SPREAD_ADD_PCT
rm -f results/arms.txt.new
for X in A E F50 F25 P10 P25; do
  CODE="$2"; S=turn; FB=; AD=
  case $X in A) CODE="$1/probe-A"; S=;; E) ;; F50) FB=50;; F25) FB=25;; P10) AD=10;; P25) AD=25;; esac
  rm -rf /tmp/sw-st-$X results/$X; mkdir -p results
  env ${S:+WMTM_RECALL_SPREAD_SEEDS=$S} ${FB:+WMTM_RECALL_SPREAD_FALLBACK_PCT=$FB} ${AD:+WMTM_RECALL_SPREAD_ADD_PCT=$AD} \
    python tools/probe_turns.py --code "$CODE" --state /tmp/sw-st-$X --data data --out results/$X > /tmp/sw-$X.stdout 2>&1
  mv /tmp/sw-$X.stdout results/$X/stdout.txt
  echo "$X: WMTM_RECALL_SPREAD_SEEDS=${S:-unset} WMTM_RECALL_SPREAD_FALLBACK_PCT=${FB:-unset} WMTM_RECALL_SPREAD_ADD_PCT=${AD:-unset} code=$CODE" >> results/arms.txt.new
done
mv results/arms.txt.new results/arms.txt
P=../t-2026-11-11-wmtm-spread-seeds-probe/results
{ echo "A vs probe A:   $(python3 tools/check_rerun.py $P/A/turns.jsonl results/A/turns.jsonl || true)"
  echo "E vs probe E:   $(python3 tools/check_rerun.py $P/E/turns.jsonl results/E/turns.jsonl || true)"; } > results/rerun_check.txt
python3 tools/analyse3.py --data data --arm A=results/A/turns.jsonl --arm E=results/E/turns.jsonl --arm F50=results/F50/turns.jsonl \
  --arm F25=results/F25/turns.jsonl --arm P10=results/P10/turns.jsonl --arm P25=results/P25/turns.jsonl --out results > results/analyse_stdout.txt
python3 tools/table5.py --code "$2" --data data --results results > results/table5_stdout.txt
