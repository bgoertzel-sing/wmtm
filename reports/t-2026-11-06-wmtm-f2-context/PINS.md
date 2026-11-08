# Pins (t-2026-11-06-wmtm-f2-context)

Upstream HEADs at task start (git ls-remote, 2026-11-06 17:50 UTC). Recorded; not edited, not vendored.

| Repository | Ref | Commit |
|---|---|---|
| rTreutlein/PeTTaChainer | master | 2a6dbb9d614b16b60693a1c09dbe767a23c89a7d |
| leungmanhin/semantic-parsing-hitl | main | 48ab896274c604698cbff51fd65e1c0e7164d94e |

The code pins stay as on the base (P4: PeTTaChainer bdae8d7e, semantic-parsing-hitl f44d7b74, PeTTa 3681b9b); F2 changes
no engine-facing code, so the gates run on the P4 engine env. GoalChainer v2 runtime for the real tie test:
MesTTo/OmegaClaw-GoalChainer 5c6ecda (goalchainer-v2-pymetta-native.2). GoalChainer v1 contract read (not edited):
MesTTo/OmegaClaw-GoalChainer 10627ce, src/goal_chainer/heuristic_beliefs.py parse_memory_evidence. STOPGAP markers added: 0.
