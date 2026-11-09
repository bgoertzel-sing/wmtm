# Criterion-5 extras (goal escalations, evictions, recent-focus use): A vs B
Status: NOT EXERCISED by this A/B. Measured counts would be 0/0 for both arms by construction, so no difference is claimed.
Evidence:
- Both worker configs set "goalchainer": false (/tmp/f3/ab/A/worker_config.json, /tmp/f3/ab/B/worker_config.json), so pc_shadow's Track R hook (wmtm/workers/pc_shadow.py, `if CFG.get("goalchainer")`) never calls goals.run_shadow -> no escalate dispositions (goals/v2.py:318) in either arm.
- The offline shadow path runs pc_shadow only; context.cleanup (evictions, context.py:111ff) and context.recent_focus (context.py:980, F12 decision 3) are not called by pc_shadow. Runtime dirs /tmp/f3/ab/{A,B}/run are empty after all 12 runs.
- Code presence: B (3288bf2) has recent_focus + escalated-tie handling (F12 decisions 3/4); A (vendor wmtm-v0.7.0-rc2) has v2 escalate mapping but no recent_focus.
To measure them, a live/replay run with goalchainer on and the context/cleanup path driven per turn is needed; proposed as a follow-up, not run here.
