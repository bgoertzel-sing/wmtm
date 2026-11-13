#!/bin/sh
# t-2026-11-13-wmtm-spread-seed-default: the spread-seed sweep's replay (tools/run5.sh of t-2026-11-13-wmtm-spread-seed-sweep)
# on this branch, where the default is now arm P10 (recall_spread_seeds=turn + recall_spread_add_pct=10).
# Because the defaults changed, every sweep arm sets all three seed-rule variables explicitly here; arm D sets none
# (= the new default).  Same tools (byte-identical copies, SHA256SUMS.txt), capacity 60, recall_budget 10 (default),
# floor 0.1, reasoner off, fixed clock, no parse calls (probe_turns.py refuses them), nothing on pop-os.
#   A    = worktree probe-A (265062e), keyword only: the reference for "hubs lost" (as in the probe and the sweep)
#   E    = turn, add 0, fallback 0                   F50 = turn, fallback 50, add 0      F25 = turn, fallback 25, add 0
#   P10  = turn, add 10, fallback 0 (explicit)        P25 = turn, add 25, fallback 0
#   D    = no seed-rule variable set: the new code default (only run with --default)
# $1 = folder holding the worktree probe-A; $2 = this branch's worktree; $3 = journal seed; $4 = output tag
# (data-<tag>, results-<tag>); $5 = arms to run (default "A E F50 F25 P10 P25").
set -e
. /hive/protocosmo/workspace/projects/wmtm/env-gapcheck/env.sh      # python 3.10.22 venv (env-gapcheck), toolchain git
R=$(cd "$(dirname "$0")/.." && pwd); cd "$R"
SEED=$3; TAG=$4; ARMS=${5:-A E F50 F25 P10 P25}
mkdir -p data-$TAG results-$TAG
python3 tools/gen_journal.py --out data-$TAG --seed $SEED > results-$TAG/gen_journal_stdout.txt
unset WMTM_RECALL_SPREAD_SEEDS WMTM_RECALL_SPREAD_FALLBACK_PCT WMTM_RECALL_SPREAD_ADD_PCT
rm -f results-$TAG/arms.txt.new
for X in $ARMS; do
  CODE="$2"; S=turn; FB=0; AD=0
  case $X in A) CODE="$1/probe-A"; S=; FB=; AD=;; E) ;; F50) FB=50;; F25) FB=25;; P10) AD=10;; P25) AD=25;;
             D) S=; FB=; AD=;; *) echo "unknown arm $X"; exit 2;; esac
  rm -rf /tmp/sd-st-$TAG-$X results-$TAG/$X
  env ${S:+WMTM_RECALL_SPREAD_SEEDS=$S} ${FB:+WMTM_RECALL_SPREAD_FALLBACK_PCT=$FB} ${AD:+WMTM_RECALL_SPREAD_ADD_PCT=$AD} \
    python tools/probe_turns.py --code "$CODE" --state /tmp/sd-st-$TAG-$X --data data-$TAG --out results-$TAG/$X > /tmp/sd-$TAG-$X.stdout 2>&1
  mv /tmp/sd-$TAG-$X.stdout results-$TAG/$X/stdout.txt
  echo "$X: WMTM_RECALL_SPREAD_SEEDS=${S:-unset} WMTM_RECALL_SPREAD_FALLBACK_PCT=${FB:-unset} WMTM_RECALL_SPREAD_ADD_PCT=${AD:-unset} code=$CODE" >> results-$TAG/arms.txt.new
done
mv results-$TAG/arms.txt.new results-$TAG/arms.txt
