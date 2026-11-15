## Summary

andy asked for a sentence mode in the live parse feed, so that the feed itself writes the parsed.jsonl the master-parser path reads, with speaker linking, a per-note sentence cap, a pin-parameterised fetch script, and a replay check with no live change. **This is done and staged on branch hive/t-2026-11-15-wmtm-sentence-feed (not pushed).** With semparse_mode "sentence", the feed queues notes in <semparse_dir>/sent1. Each note is speaker-linked (with the same substitution spk1 uses), cleaned and split with the sp2 rules, and parsed with one call per sentence, with the earlier sentences as context (parser 24e37182, at most 2 attempts per sentence). Every call is reserved in the live share's ledger before it is sent. A note is written to sent1/parsed.jsonl only when all of its sentences are parsed, all at once, by an atomic file replace. Until then it stays queued, and the master path never sees it.

The replay used the cached master-adopt-v2 replies as the provider, so it made 0 parse calls. It rebuilt parsed.jsonl for the 20 notes through the real feed code: 124 calls, all reserved in a temporary live share, and 124/124 rows byte-identical to the offline driver's rows. The master shadow path then gives the same result as before: **105/105 proved, and 23 admitted = 22 correct / 1 wrong (b68)**, with 82 dropped as trivial (77 symmetry, 5 coref), so the count rule holds. Legacy and catalog feed output is byte-identical to the merge base. The full suite passes (1562 passed; 1575 with the parser templates set). For the switch, andy should note three things. First, besides semparse_mode, the switch needs semparse_prompt_sha256 = 257425b2...; at its default the worker refuses. Second, I left out spk1's "Speaker: X." prefix, because it would be one more paid call per linked note. Third, with the live speaker map, linking changes the text of 3 of the 20 sample notes, so those notes would need fresh parses.

## Question

Can the live feed, switched to a new sentence mode, produce the parsed.jsonl the master path reads (the same rows as the offline driver), with speaker linking, under the live ParseBudget share, while legacy mode stays byte-identical? **Yes**, on the evidence below (offline, 0 real parse calls).

## Base and code

- Fresh worktree projects/omegaclaw/sfd/wmtm-wt, branch hive/t-2026-11-15-wmtm-sentence-feed.
- Base: wmtm main 4417b1e16c4655a3ade8f849777c91d072bfbb91. On top of it, merge fade3d1c1bf3c51e477d466db9f23205f225e86a (feed watch), giving 66f7235, then merge 950d18a4df7d251f8c68c056cac3330c9d445962 (shadow wiring), giving **66c33ae** (the merge base used for every old-vs-new comparison). Both merges were clean. Suite at 66c33ae: 1535 passed, 57 skipped, 5 xfailed (as the plan found).
- New: wmtm/semparse_sentence.py (library):
  - strip and sentences: the sp2 cleanup.py rules, ported unchanged (C1 trailing markup comment, C2 hex ids, C3 backticked shell commands, C4 "(n)" list markers; abbreviation-aware split).
  - prepare: speaker linking (if speaker_link), then strip, split and cap, giving rows {id, dataset, doc, sent, text}. The key order and ids "<item>.sNN" are the offline driver's, and the dataset is "wmtm-sp2" like the offline rows, so the two are interchangeable.
  - gateway_parse_fn: upstream parse_sentence (the function the offline driver calls), with upstream's chat-completions provider class wrapped so that every request first does ParseBudget.acquire (no waiting). A full share raises ShareFull and sends nothing.
  - process_queue_sentence: the drive.py loop. It takes the oldest note first and goes sentence by sentence (tmpl.blocks.walk / context_section), with at most 2 attempts per sentence; error rows are kept as the offline driver keeps them. It writes one parse_log row per call, with the call_ids joined to the ledger, and moves finished notes only, atomically, into parsed.jsonl.
  - promote: rewrites parsed.jsonl by tmp + os.replace; a new version of the same item replaces that item's old rows.
  - require_pin: the hitl checkout must be at 24e37182.
- wmtm/parse_cache.py feed_rows: in semparse_mode "sentence", the queue, budget, worker and launch decisions (fade3d1) live in <semparse_dir>/sent1. Otherwise nothing changes.
- wmtm/workers/semparse_feed.py:
  - In mode "sentence", the existing pin, licence and prompt-sha gates run first, then the 24e37182 pin gate, then a refusal unless the dir is sent1, then upstream stale_prompt.
  - The run is process_queue_sentence on this cache's share (parse_role live gives the live share).
  - worker_runs.jsonl gets status, mode sentence, parsed, notes {ok, failed, empty, partial}, share and share_stop.
- wmtm/parse_budget.py live_root: sent1 counts as a live sub-cache, so without parse_live_dir its share is still the live root's share and never a share of its own. sent1 is deliberately **not** added to SUBCACHES. Its calls are counted through the share ledger (each call reserves a row first, and its log rows carry the call_ids), and adding it would change the logs count in legacy status lines.
- wmtm/runtime_config.py + README:
  - new key semparse_sentence_cap (WMTM_SEMPARSE_SENTENCE_CAP, int, default 0 = none). Only the first N sentences of a longer note are parsed, and the note then counts as complete.
  - semparse_mode documents the "sentence" value.
- scripts/fetch_semparse_hitl.sh:
  - takes [DEST] [PIN] (or env SEMPARSE_PIN), knows f44d7b74 (the default, unchanged) and 24e37182, and refuses any other pin before fetching (exit 2);
  - for 24e37182 it checks PROMPT_CATALOG 257425b2, seeded_rules 2ade9354, semantic-parse.py cb5e15c1, LICENSE 58602369 and seeded_rules.pettachainer-master 9c58f2e0, and adds the last one to VERSION.
- tools/feed_watch.py: reads semparse_mode and watches sent1 in sentence mode; live_root knows sent1.
- tests/test_semparse_sentence.py: 28 tests on synthetic notes. They cover:
  - cleanup categories and split;
  - row shape;
  - the cap;
  - speaker linking equal to spk1's link (no prefix) and a shared name across notes;
  - a full drain under the live share (ledger = log call ids, used == calls);
  - a partial note kept out of parsed.jsonl and resumed without re-parse;
  - a full share stopping with nothing sent;
  - the gate refusing mid-note;
  - 2 attempts then gave up (never fed, never retried);
  - a retry that keeps the error row;
  - a 429 stopping the run;
  - the own hourly cap;
  - new content replacing old rows;
  - an empty note;
  - notes_from_parsed seeing only finished notes (with templates);
  - the gate reserving before sending and refusing when full (fake upstream module);
  - routing to sent1 with a launch decision line;
  - other modes unchanged;
  - the sent1 share root;
  - the config key;
  - the pin gate, and the worker refusing without the pinned checkout;
  - the fetch script refusing an unknown pin, and fetching 24e37182 from the local clone.

## Evidence (/srv/hive-evidence/t-2026-11-15-wmtm-sentence-feed/)

| check | result |
|---|---|
| suite at 66c33ae / at head / at head with WMTM_PC_SHADOW_SPH_TEMPLATES | 1535 / **1562 passed**, 58 skipped, 5 xfailed / **1575 passed**, 45 skipped, 5 xfailed |
| split port vs sp2 sel.jsonl (b76cd0d4) on the 20 notes | 124 sentences, **equal**; equal to the cached rows' selection part |
| replay (tools/replay.py), feed path minus HTTP, 2 arms | 124 requests, 124 served from cache, 0 misses, 0 parse calls; 124 ledger rows, all role live; log call_ids = ledger ids; share used 124 |
| runs of at most 20 calls (the hourly cap) | 7 runs (20x6 + 4). After every run, notes_from_parsed found **0 incomplete notes** in parsed.jsonl |
| rows vs the offline driver's good rows | **124/124 byte-identical** (json.dumps), 0 differing reply fields, row keys [id, dataset, doc, sent, text, reply] |
| arm offline_order (notes queued in the offline order) | spec master_ops 1935 and goals 105 **equal** to shadow-wiring run/spec.json; worker 105/105, add_fail 0, pred_fail 0, timeouts 0; queries, canary and neg equal to run_apply (timing excluded) |
| arm feed_order (queued in one cycle, ranked by STI as the feed does) | same master_ops multiset and goal set, in another order; 105/105; same query set |
| admit, both arms (load_candidates, goal ids from the reference order) | dropped trivial 82 (symmetry 77, coref 5), **admitted 23 = 22C / 1W (b68) / 0U**, vs A_v3 HOLDS |
| live files (sha256 before = after) | flags e6496a47..., live share ledger f8203df4..., host task ledger 29e750fc... |
| legacy / spk1 / catalog feed byte diff (tools/legacy_bytediff.py, 66c33ae vs head) | 16 files, manifests **identical**. worker_config.json is compared after normalising the new key semparse_sentence_cap = 0 and the checkout paths |
| fetch_semparse_hitl.sh default pin (f44d7b74), old vs new script | output tree identical (diff -r), stdout identical |
| worker smoke (tools/worker_smoke.py, subprocess, empty queue, 0 calls) | prompt sha flag at its default: prompt_mismatch, exit 5; hitl at f44d7b74: hitl_pin, exit 5; switch flags: status ok, mode sentence, parsed 0, share role live 20/h |
| recompute (tools/recompute.py, evidence JSON only) | PASS |

Files: replay/counts.json, replay/{offline_order,feed_order}/{shadow.jsonl,admit.json} (the worker's own outputs, as in the shadow-wiring evidence), bytediff/manifest_{old_66c33ae,new}.json, worker_smoke.json, fetch_default_pin_bytediff.txt, suite/*.txt, tools/ (replay.py, legacy_bytediff.py, worker_smoke.py, recompute.py), REPORT.md and SHA256SUMS. Note text stayed in private temp dirs (mkdtemp, removed at exit). The evidence holds counts, statuses and the worker's logic outputs only.

## Differences explained

- The cached file has 129 rows (124 good + 5 error rows from the adopt-v2 run). The replay serves only good replies, so it has no transient failures and rebuilds 124 rows. The retry behaviour (error row kept, at most 2 attempts) is covered by tests.
- Row order: the feed writes a note's rows when the note finishes, so the file order is note by note. The offline file had its retries appended at the end. notes_from_parsed groups by doc in first-seen order, so in offline_order the spec is still exactly equal.
- Load order in the live feed: the feed finishes notes in queue order (oldest first, then STI), and the master path loads notes in parsed.jsonl order. On the 20 notes, that gives the same KB and goal set, the same 105/105 and the same admits; only the goal numbering differs (arm feed_order).

## For the switch (andy's choices and the exact values)

- Flags in addition to the plan's table:
  - semparse_mode "sentence".
  - shadow_master_parsed = the absolute path of <semparse_dir>/sent1/parsed.jsonl. With the live default semparse_dir, that is R/memory/_wmtm_shadow/semparse_cache/sent1/parsed.jsonl.
  - semparse_hitl = the 24e37182 vendor dir (scripts/fetch_semparse_hitl.sh DEST 24e37182).
  - **semparse_prompt_sha256 = 257425b2c1593569789317f0f007f57f21f856df868b382adc0880c1c3414809** (required; the smoke shows prompt_mismatch without it).
  - semparse_sentence_cap: 0 by default; e.g. 8 would bound a note to 8 calls.
- Speaker linking: speaker_link true (live now) applies the spk1 substitutions before the split. **Choice made: no "Speaker: X." prefix sentence.** spk1 prefixes it, and here it would be one more paid call per linked note. If andy wants it, set SPEAKER_PREFIX = True (one line). On the 20 sample notes with the live map: 3 notes' text changes and 0 speakers resolve. The cached replies were made without linking, so the replay ran with linking off, and those 3 notes would get fresh parses live.
- Switching semparse_mode to sentence moves the live feed from spk1 to sent1. spk1 then gets no new parses, and it is used again on rollback (as the plan's Risks 4 option b says).

## Limits

- 0 real parse calls. The real HTTP request through the gated provider was not exercised; the gate is tested with a fake provider and the replay used upstream parse_sentence with a replay provider class. The first real call is the switch's smoke (plan S2e).
- parsed.jsonl is never compacted, and each finished note rewrites it. The adopt-v2 rows average about 4.1 KB, so at about 430 sentences a day it grows by about 1.8 MB a day, and pc_shadow reads the whole file every cycle. A compaction to the active set is a small follow-up, not needed to switch.
- Notes longer than parse_max_chars (1500) are skipped at enqueue, as in every other mode; the plan's 430-sentence estimate used 2000 chars.
- A note that gives up (2 failed attempts on one sentence) is not retried for that content, the same rule as legacy llm_error. Its rows are kept in sent1/gave_up/ and never fed.
- Unmerged parent branches of 950d18a are as listed in the plan (not re-checked; gh is not authenticated).
