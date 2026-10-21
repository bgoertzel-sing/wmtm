"""Track R: GoalChainer phase 1 (log only).  v0.7: the core (need regulation, deontic legitimacy, ranking) is
GoalChainer v2, run as a separate process (wmtm/goals/v2.py, docs/GOALS_V2.md); goal_engine "native" = the v0.6 core
described below.  See docs/GOALCHAINER_DESIGN.md / design section 7.

Homeostatic needs (OpenPsi style, Mikeda & Goertzel arXiv 2606.05411): uncertainty reduction ("unc") and competence
("comp") are estimated from the WMTM active set (+ cached parser queries, + failed checks); legitimacy is a veto only.
Urge u = w * phi(target - level).  Candidate actions come from 5 templates (ClarifyQuestion, FlagUncertainty, LookUp,
SummarizeStatus, RemindPending); PeTTaChainer proofs from the shadow run (canary-passed only) count as KB support.
score = urge(need) * geometric mean(positive considerations) * product(discouragements); a forbidden action gets 0.

Output goes ONLY to <runtime_dir>/goalchainer/proposals.jsonl (+ runs.jsonl).  Nothing goes into the prompt and no
action is ever taken.  Off unless the flags file sets "goalchainer": true; runs inside the PeTTaChainer shadow worker.
"""
from .engine import propose, run_shadow, goal_canary, check_proposal, settings, SUBDIR  # noqa: F401
from .engine import propose_v2, goal_canary_v2, engine_name  # noqa: F401
