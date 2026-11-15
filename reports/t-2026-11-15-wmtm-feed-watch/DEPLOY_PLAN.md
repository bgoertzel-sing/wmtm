# Deploy plan: parse-feed decision record + stall watch (t-2026-11-15-wmtm-feed-watch, L-03)

**Not done in this task.** Nothing below has been run on the live bot. Every step needs andy's go-ahead.
R = /home/openclaw/research-agent/projects/omegaclaw/protocosmo2/iter-port/repos (the live bot, ProtoCosmo2),
M = R/memory, D = M/_wmtm_shadow/semparse_cache (the live share root; the active cache is D/spk1, speaker_link on).
C = the commit of branch hive/t-2026-11-15-wmtm-feed-watch after review and merge (base: main ddd2096).

There are two independent parts. Part A (the watch) changes nothing the bot runs and can go first. Part B (the
decision record) is a pin switch like the 11-14 switch to ddd2096.

## Part A: the watch timer (no change to the bot)

Files that change on pop-os (all new, none of them under R):

| File | What |
|---|---|
| ~/.local/share/parse-feed-watch/feed_watch.py | git show C:tools/feed_watch.py (stdlib only; it imports nothing from wmtm) |
| ~/.local/share/parse-feed-watch/SHA256SUMS | its sha256 |
| ~/.config/systemd/user/parse-feed-watch.service | below |
| ~/.config/systemd/user/parse-feed-watch.timer | below |
| ~/.local/state/parse-feed-watch/{last.json,history.jsonl} | written by each run (history rotated at 512 KiB) |

crontab -l is permission-denied for openclaw on pop-os, so this uses a systemd user timer, like
gateway-patch-guard (t-2026-11-11).

    # parse-feed-watch.service
    [Unit]
    Description=Read-only parse-feed stall check for ProtoCosmo2 (t-2026-11-15-wmtm-feed-watch, L-03)
    [Service]
    Type=oneshot
    Environment=PATH=/usr/local/bin:/usr/bin:/bin
    ExecStart=/usr/bin/python3 -I %h/.local/share/parse-feed-watch/feed_watch.py --state-dir /home/openclaw/research-agent/projects/omegaclaw/protocosmo2/iter-port/repos/memory --alert
    SuccessExitStatus=1 3
    TimeoutStartSec=900
    Nice=10

    # parse-feed-watch.timer
    [Unit]
    Description=Parse-feed stall check every 30 min (t-2026-11-15-wmtm-feed-watch)
    [Timer]
    OnCalendar=*:07,37
    Persistent=true
    [Install]
    WantedBy=timers.target

(The cron equivalent, if a crontab is ever allowed: 7,37 * * * * /usr/bin/python3 -I ~/.local/share/parse-feed-watch/feed_watch.py --state-dir <M> --alert.)
SuccessExitStatus keeps ALERT (1) and ERROR (3) from marking the unit failed. The alert itself goes through
hive-task propose, and journalctl --user -u parse-feed-watch keeps the printed verdicts.

Install:
1. mkdir -p ~/.local/share/parse-feed-watch && git -C <wmtm-module> show C:tools/feed_watch.py > ~/.local/share/parse-feed-watch/feed_watch.py && (cd ~/.local/share/parse-feed-watch && sha256sum feed_watch.py > SHA256SUMS)
2. Dry run: /usr/bin/python3 -I ~/.local/share/parse-feed-watch/feed_watch.py --state-dir M. Expect OK (idle, or recent_run).
3. Prove the real alert path once, as the patch guard did: run it against a scratch copy of the live state with one synthetic queued item and --now 3 h ahead, with --alert --test-label "feed-watch install test" --status-dir /tmp/pfw-test. One proposal titled "TEST (...) ... ALERT pop-os: parse feed stalled (...)" should reach the record, for cos to decline. The canary below already shows the verdict on such a copy.
4. Write the two units, then: export XDG_RUNTIME_DIR=/run/user/1001; systemctl --user daemon-reload && systemctl --user enable --now parse-feed-watch.timer
5. Check: systemctl --user list-timers parse-feed-watch.timer, and after the first run ~/.local/state/parse-feed-watch/last.json.

Rollback for A: export XDG_RUNTIME_DIR=/run/user/1001; systemctl --user disable --now parse-feed-watch.timer && rm ~/.config/systemd/user/parse-feed-watch.{timer,service} && systemctl --user daemon-reload. Optionally remove ~/.local/share/parse-feed-watch and ~/.local/state/parse-feed-watch. Nothing of the bot's is touched either way.

## Part B: the decision record (pin switch to C)

Files that change on pop-os:

| File | Change |
|---|---|
| R/vendor/wmtm-<C7>/ | new, beside wmtm-ddd2096: git archive C wmtm upstream pyproject.toml README.md PETTA_PIN.md docs/RUNTIME.md docs/GOALS_V2.md (ddd2096's file set), VERSION (version=0.7.0rc2, commit=C, tree=...), MANIFEST.sha256, then chmod -R a-w |
| R/_wmtm_pin.py | 2 lines: WMTM_VENDOR = "wmtm-<C7>", EXPECTED_COMMIT = "<C>" (EXPECTED_VERSION stays 0.7.0rc2) |
| D/spk1/launch_decisions.jsonl (+ .1) | new, written by the bot after the switch; at most ~2 x 256 KiB |

Unchanged: the flags file, the runtime vendor dirs (petta, pettachainer, semparse-hitl), the share, the gateway and
every process. As on 11-14, nothing is restarted: each iter.py --invoke re-reads the pin.

What C changes against ddd2096 in wmtm/: only wmtm/parse_cache.py (launch_worker, feed_rows, maybe_feed and
the new record_launch). Each decision appends one line. Return values and the order of the checks are the same:
busy is checked first, then the budget, then pending. tests/test_launch_decisions.py::test_return_values_match_the_old_launcher
pins this over 24 input combinations. The record never raises and never creates a dir.

Steps:
1. Backup: cp -a R/_wmtm_pin.py to backups/wmtm-feedwatch-<ts>/, and record sha256 of M/_wmtm_flags.json.
2. Build the vendor dir. Check that sha256sum -c MANIFEST.sha256 passes and that git diff ddd2096 C -- wmtm/ touches only parse_cache.py.
3. Smoke, before the pin changes: PYTHONPATH=R/vendor/wmtm-<C7> /usr/bin/python3.10 -c "import wmtm.parse_cache as p; print(p.LAUNCH_LOG)". Also run feed_rows on a /tmp copy of the state with semparse_feed true and spawn stubbed, and check for one line in the copy's launch_decisions.jsonl.
4. Edit the 2 pin lines.
5. Verify within 20 min (one automated turn is about 15 min):
   - M/_wmtm_pkg.json shows commit C.
   - D/spk1/launch_decisions.jsonl exists, with nothing_pending lines while the bot is idle.
   - worker_runs.jsonl keeps its cadence: the next user turn gives a launched line and then a worker_runs row.
   - feed_watch.py shows decisions.present true and an OK verdict.

Rollback for B: cp the backed-up _wmtm_pin.py back, or restore the two lines to wmtm-ddd2096 / ddd209611e6b31dc973b4669c39800f76f907d39. The next --invoke loads ddd2096 again (check _wmtm_pkg.json). launch_decisions.jsonl is then simply no longer written. ddd2096 never reads it, so it can stay or be deleted. The new vendor dir can stay; nothing loads it.

## Dry run on live (read-only, 2026-11-15T18:12:08Z, this task)

    /usr/bin/python3 tools/feed_watch.py --state-dir M --status-dir /tmp/fw/status --json   -> exit 0

Verdict **OK [idle]**: "idle: nothing queued (last run 17 min ago)".
- pending 0 in D/spk1.
- Live share: 5/20 used in the last hour, so 15 remaining. The own cap is 5/20 used, so budget_left is 15.
- Last worker run ended 2026-11-15T17:55:00Z. No worker.pid; no launch_decisions.jsonl yet (expected before B).
- The flags resolve to role live, share dir = D, active cache D/spk1. Full JSON: dryrun-live.json.
- sha256 of D/share_ledger.jsonl, D/spk1/queue.json, D/spk1/worker_runs.jsonl and M/_wmtm_flags.json were the same before and after the run. The check wrote only under /tmp/fw/status.

Independent cross-check, at the same instant, through the live vendor copy's own counters (read-only calls):
ParseBudget("live").used = 5, ParseCache(spk1).used_last_hour = 5, pending() = 0, budget() = 15. These are the same
numbers the watch got from reading the files itself. rc.resolve(M) reported no unknown or invalid keys.

Known-answer canary through the same script, on a /tmp copy of the live file shapes: the live ledger, parse logs,
worker_runs, and cache hashes only. The flags were copied with parse_live_dir pointed at the copy, and one synthetic
queued item was added (its content is the literal "synthetic canary"; no note text was copied):
+0 h OK recent_run (exit 0); +1 h OK recent_run (exit 0); +3 h **ALERT stalled** (exit 1): "1 queued (oldest
waiting 3.0 h), budget free (20 left ...), no worker run for 3.3 h (last 2026-11-15T17:55:00Z)". With the queue
drained at +3 h it is OK idle (exit 0). Transcript: canary.txt.

## Limits and notes
- The watch reads only the flags file. WMTM_* environment overrides in the bot's own process are invisible to it. Today the live bot's settings all come from the flags file, and rc.resolve agrees with the file. If they ever diverge, the share-dir and role checks report ERROR rather than OK only when the flags themselves are wrong.
- Detection latency is at most about 2.5 h: the 2 h window plus the 30 min timer. A persistent finding is re-filed at most once per 24 h. Going back to OK re-arms it.
- The hook_errors rule (ALERT on 3 trailing error decisions within 2 h, even with an empty queue) only works after Part B. Before that, an exception in feed_rows before enqueue still looks idle. This is exactly L-03, and Part B is what closes it.
- Not alerted on: a bot that runs no turns at all. Its queue is empty, so it looks idle. After B, "no decision line for well over 15 min" would show it, but that also fires whenever the bot is stopped on purpose. I left it out and offer it as a possible follow-up.
