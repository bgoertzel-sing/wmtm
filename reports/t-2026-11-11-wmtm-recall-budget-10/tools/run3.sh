#!/bin/sh
# t-2026-11-11-wmtm-recall-budget-10: the graph-only probe rerun in three arms (vm2 proto-hive container, user space).
# A = 265062e (keyword-only recall), B = 26e7769 (graph recall, floor 0.1, top 15), C = this branch (graph recall,
# floor 0.1, recall_budget 10).  The journal generator, turn script, labels and harness are the probe's, byte for byte
# (tools/gen_journal.py, tools/probe_turns.py, data/turns.json, data/labels.json; see SHA256SUMS.txt vs the probe's).
# $1 = the folder holding the worktrees probe-A (265062e) and probe-B (26e7769); $2 = C's worktree (this branch).
set -e
. /hive/protocosmo/workspace/projects/wmtm/env-gapcheck/env.sh      # python 3.10.22 venv (env-gapcheck), toolchain git
R=$(cd "$(dirname "$0")/.." && pwd); cd "$R"
python3 tools/gen_journal.py --out data                            # seed 20261111 (default); deterministic
for X in A B C; do
  if [ $X = C ]; then CODE="$2"; else CODE="$1/probe-$X"; fi
  rm -rf /tmp/rb10-st-$X results/$X
  python tools/probe_turns.py --code "$CODE" --state /tmp/rb10-st-$X --data data --out results/$X > /tmp/rb10-$X.stdout 2>&1
  mv /tmp/rb10-$X.stdout results/$X/stdout.txt
done
python3 tools/analyse3.py --data data --arm A=results/A/turns.jsonl --arm B=results/B/turns.jsonl --arm C=results/C/turns.jsonl --out results > results/analyse_stdout.txt
