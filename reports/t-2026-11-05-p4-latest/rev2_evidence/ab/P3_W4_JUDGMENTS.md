# W4 hand judgments (written 2026-11-05T01:39:41-07:00), keyed by the shuffled ids #0-#4 (seed 20261105). Arm labels are not used here.
Caveat: the arm summaries (stv) were already visible before this file was written, so the blinding is partial. This is recorded, not hidden.
#0 (Member hive_t_2026_10_28_goalchainer_v2_status branch): WRONG. The source says the *branch* hive/t-... is a branch; the task id itself is not a branch. Parse conflates task id with branch name.
#1 (Inheritance chat_send valid) from 185132Z+185959Z: WRONG as unconditional fact. Sources say a send is valid ONLY while a request is open; the condition was dropped by the parse.
#2 (Inheritance hive_progress_report report): CORRECT (trivially true).
#3 (Member turn_without_send_entry entry): CORRECT (the LTM entry "Turn w/o send=MY error" is an entry).
#4 (Inheritance chat_send valid) from 185959Z only: WRONG, same reason as #1.
