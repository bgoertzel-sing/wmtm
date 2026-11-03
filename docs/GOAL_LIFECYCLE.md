# Goal lifecycle (log only, offline)

Module: `wmtm/goals/lifecycle.py`. Command: `scripts/goal_lifecycle_replay.py`. Tests: `tests/test_goal_lifecycle.py`.
The live worker, the flags and goal_prompt never call any of this. It only reads copies of `proposals.jsonl` and the journal, plus optional git logs.

## Goal ID and dedup
- Goal body: the proposal text with its wrapper ("Self-task (log only, no message):", "Remind X about:") and any leading open markers (Still open:, PENDING:, waiting on) removed.
- Terms: `needs.norm(needs.keys(body))`, plus short acronyms (LTM, CoS) and hive task ids, minus the marker words.
- Value and direction anchors (review 2): every standalone number becomes an anchor `#30` (so "30 days" != "90 days"), and every directed pair becomes `@dir:a>b` ("from A to B", "A -> B", "rename/move/copy/migrate/switch A to B"), so a reversed move never merges with the original.
- Two proposals are the **same goal** only if all of these hold:
  - same `who`;
  - same action;
  - **identical anchor sets** (entities, paths, track letters, commit hashes, task ids);
  - Jaccard(terms) >= `MERGE_JACCARD` = 0.8.
- An anchor that appears on one side only means a different object, so the two never merge. This guards against losing real requests.
- Goal ID: `sha1(who|action|sorted terms)[:12]` of the first proposal in the cluster. It is stable across runs and term order.
- Why 0.8: the existing `cluster_match` (overlap / min) merges short texts with almost anything. On the Oct 19–29 log, "no later note says I joined" matched 9 of 13 other goals. Jaccard >= 0.8 plus equal anchors merged no pair of distinct texts in that log.

## Newest source
When a proposal merges into an existing goal, its source notes are added to the goal and `src_ts` moves forward to the newest one. A goal re-raised by a newer "still open" note is therefore not satisfied by an older closure.

## States (precedence: superseded > satisfied > stale > open)
States are computed **as of the proposal time**: only notes and goals before it count, so there is no look-ahead.
- **satisfied**: a source newer than the goal's newest source note has a *closing sentence* that matches the goal.
  - Sources read: journal EventNotes and, with `--git-repo`, commit subjects. Hive "done" results reach the journal as CLOSED notes, which is how readme-flags is matched.
  - A closing sentence has a non-negated resolution word (`needs.res_hit`) or CLOSED / DONE / is done / deleted / trimmed / removed / merged / fixed, and no earlier open marker.
  - These never count as closing: LINK / SUPPORTS / CORRECTION / LESSON / NOTE / ROOT CAUSE sentences, and WMTM enrichment clusters (`MemoryCluster`, `wmtm-enrich-`), because they restate older notes.
  - Anchor conflict (review 2): a closing sentence is skipped when, for some anchor kind (entity/path `@`, number `#`, direction `@dir:`), both the goal and the sentence have anchors of that kind and share none. "cache logs for src/gadget rotated" never closes "rotate cache logs for src/widget"; "retention 90 days, done" never closes "retention to 30 days".
  - The closing sentence matches the goal in any of these ways:
    - (a) it names one of the goal's task ids that is not a precondition. In "once t-x closes, do Y", closing t-x is not evidence for Y: Y must match on its own terms, and the condition words (once, clos, ...) are ignored;
    - (b) it shares >= 2 distinctive terms including an anchor, and the whole note shares >= `SAT_MIN`-1 = 3;
    - (c) it alone shares >= 3 terms and >= `SAT_FRAC` = 0.5 of the goal's distinctive terms;
    - (d) it shares >= 2 terms, and the note shares >= 3 and >= 0.5 of them.
  - "Distinctive" excludes the journal's common closure terms (`needs.common_terms`, e.g. wmtm, telegram, tests).
  - **A multi-item goal** ("a; b; c", or "a, and X hasn't ...") is satisfied only when every item matches a closure on its own.
- **superseded**: one of these holds:
  - only a later goal with the same person AND the same action counts;
  - it restates it (covers >= `COVER` = 0.8 of its terms) with identical anchors;
  - it was split into later smaller goals (each covered >= 0.8 by it) whose union covers >= `SPLIT_COVER` = 0.95. Each part's anchors must be a subset of the original's. One split-off item alone never retires the rest, and a goal about a different object (other anchor) never retires it.
- **stale**: the newest source note is more than `STALE_DAYS` = 7 days old, with no later note on the topic (>= 3 and >= 0.5 shared terms).
- **open**: none of the above. Within open, a repeat of a goal's first proposal is dropped as "duplicate", and a merged different engine id is dropped as "near-duplicate".

## Rating export
Final states (goals.json, rating sheet) are computed as of `--until` (the window end), not as of the last proposal.
`goal_lifecycle_replay.py --out DIR` writes the following. Keep DIR out of git, because the rows hold chat-derived text.
- `report.{json,md}`: counts before and after, split pre/post rc2 (`--cutoff`, default 2026-10-23T17:13Z = 10:13 PDT) and people (RemindPending) vs self.
- `dropped.csv`: every dropped proposal with its reason.
- `kept.csv` and `goals.json`.
- `rating_sheet.{csv,md}`: one row per goal still open, with the goal id, the source note and a rating column (approve / reject / already done / wrong).
