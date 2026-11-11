#!/bin/sh
# t-2026-11-11-wmtm-graph-only-probe: exact commands (vm2 proto-hive container, user space).
# A = 265062e (base of the floor-replay branch, keyword-only recall), B = 26e7769 (floor-replay code: graph recall,
# floor 0.1, direct PromotesFrom 0.5).  Worktrees: git worktree add --detach <dir> <commit>.
set -e
. /hive/protocosmo/workspace/projects/wmtm/env-gapcheck/env.sh      # python 3.10.22 venv (env-gapcheck), toolchain git
R=$(cd "$(dirname "$0")/.." && pwd); cd "$R"
python3 tools/gen_journal.py --out data                            # seed 20261111 (default); deterministic
for X in A B; do
  rm -rf /tmp/probe-st-$X results/$X
  python tools/probe_turns.py --code "$1/probe-$X" --state /tmp/probe-st-$X --data data --out results/$X > /tmp/probe-$X.stdout 2>&1
  mv /tmp/probe-$X.stdout results/$X/stdout.txt
done
python3 tools/analyse.py --data data --a results/A/turns.jsonl --b results/B/turns.jsonl --out results
python3 tools/leak_check.py > results/leak_check.txt
