# Default-timeout run (shadow_timeout_s=2.0, shadow_budget_s=20.0, runtime_config defaults), PeTTaChainer bdae8d7e
Run 2026-11-05 18:02 PDT, real worker wmtm.workers.pc_shadow, same spec as bdae8d7e/ (13 goals).
Result: status ok (NOT canary_fail), canary (Member grace person) 1.0/0.99 proved, negative (Member grace robot) prior only.
12/13 proved, 1 timeout (sk_config_1__i_ep_note_20261028T185959Z effective, 2.009 s), same goals and STVs as the 10 s run.
Rev2's "default 2 s run hit canary_fail" was on 202b9379 under load (warm 20 s there vs 2.5 s here); on bdae8d7e the defaults work.
