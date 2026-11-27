# S5 live switch plan: live WMTM flags file -> config/live-flags.json (for andy)

Task t-2026-11-24-wmtm-s5-ops. Nothing here has been applied; every step needs andy's go.

## Where things stand
- The live bot (protocosmo2, iter-port) reads its flags from `<state_dir>/_wmtm_flags.json`
  (vendor wmtm-d506783, `wmtm/runtime_config.py`: `FLAGS_FILENAME`, `read_flags_file`, `resolve`).
  It is re-read on every cycle, so a change takes effect on the next turn with no restart.
  A missing or non-JSON file counts as absent and every feature goes OFF.
- Live path on pop-os: `.../protocosmo2/iter-port/repos/memory/_wmtm_flags.json` (1735 bytes, mode 640+ACL).
- `config/live-flags.json` in this repo is byte-identical to it today (sha f9e59f74..., 28 keys).
- No cron or timer runs the drift check yet (`crontab -l` is empty for openclaw).

## The switch (repo file becomes the source, live file becomes a deployed copy)
The bot code does not change: it keeps reading `<state_dir>/_wmtm_flags.json`. What changes is who writes it.

1. Freeze: from now on, flag changes are made as commits to `config/live-flags.json` on a branch, reviewed and
   merged like code. Hand edits of the live file stop.
2. Deploy step (`scripts/deploy_live_flags.sh`, to be written once andy agrees; about 15 lines):
   a. `check_live_flags_drift.py` must exit 0 (no unreviewed hand edit on live) or the deploy stops;
   b. back up the live file to `memory/_wmtm_flags.json.bak.<utc>`;
   c. write the merged repo file to `memory/_wmtm_flags.json.tmp`, `python3 -m json.tool` it, then `mv` it
      over the live file (atomic rename, so the bot never reads half a file);
   d. re-run the drift check: it must print "same".
   Rollback: `mv` the backup back. The next turn picks it up.
3. Not chosen: a symlink from the live path into the repo checkout. It would make any checkout or branch
   switch in the worktree a live flag change, which is exactly what the drift check is there to catch.

## Running the drift check routinely
- Proposed: hourly user crontab line (needs andy's OK, because it is a scheduler edit on pop-os):
  `17 * * * * cd <wmtm checkout on main> && git pull -q --ff-only && nice -n19 python3 scripts/check_live_flags_drift.py --json >> ~/.openclaw/wmtm-flags-drift.log 2>&1 || echo "WMTM flags drift $(date -u +%FT%TZ)" >> ~/.openclaw/wmtm-flags-drift.alert`
- Exit 1 (drift) or 2 (file missing or not JSON) adds an alert line. The script prints key names and hashes
  only, never values, so the log is safe to share.
- Who reads the alert: the bot that owns the deploy (protocosmo2) checks the alert file at its first turn of
  the day and reports any new line to andy in the WMTM chat.
- `check_live_triggers.py --hours 24` can run on the same schedule once a day for T1-T7 (see the report
  for the T6 caveat and fix).

## Decisions for andy
1. Make the repo file the source of truth, with the deploy step above? Recommended: yes.
2. Install the hourly drift-check cron line? Recommended: yes. It is read-only on live.
3. The repo file includes the speaker map (2 numeric Telegram user ids, 2 handles), because the order required
   exact live bytes. Keep it there, or move the speaker map into a pop-os-only side file? Recommended: move it
   at the first deploy.
