#!/bin/sh
# t-2026-11-11-wmtm-spread-seeds-probe: the graph-only probe in four arms (vm2 proto-hive container, user space).
# A = 265062e (keyword-only recall, reference); C, D, E = this branch (graph recall, floor 0.1, recall_budget 10) with
# recall_spread_seeds unset (C = all residents, the default), focus (D) and turn (E).  The journal generator, turn
# script, labels and harness are the probe's, byte for byte (see SHA256SUMS.txt).
# $1 = the folder holding the worktree probe-A (265062e); $2 = this branch's worktree.
set -e
. /hive/protocosmo/workspace/projects/wmtm/env-gapcheck/env.sh      # python 3.10.22 venv (env-gapcheck), toolchain git
R=$(cd "$(dirname "$0")/.." && pwd); cd "$R"
python3 tools/gen_journal.py --out data                            # seed 20261111 (default); deterministic
for X in A C D E; do
  case $X in A) CODE="$1/probe-A"; S=;; C) CODE="$2"; S=;; D) CODE="$2"; S=focus;; E) CODE="$2"; S=turn;; esac
  rm -rf /tmp/ss-st-$X results/$X
  if [ -n "$S" ]; then export WMTM_RECALL_SPREAD_SEEDS=$S; else unset WMTM_RECALL_SPREAD_SEEDS; fi
  python tools/probe_turns.py --code "$CODE" --state /tmp/ss-st-$X --data data --out results/$X > /tmp/ss-$X.stdout 2>&1
  mv /tmp/ss-$X.stdout results/$X/stdout.txt
done
unset WMTM_RECALL_SPREAD_SEEDS
python3 tools/analyse3.py --data data --arm A=results/A/turns.jsonl --arm C=results/C/turns.jsonl --arm D=results/D/turns.jsonl --arm E=results/E/turns.jsonl --out results > results/analyse_stdout.txt
