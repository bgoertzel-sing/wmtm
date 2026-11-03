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

## Polarity, order and object kinds (review 3)
- Polarity is scoped (review 4): every negation word (not, never, no longer, don't, do not, doesn't, shouldn't, must not, avoid, without; since review 6 the reversal verbs are operations, see below) adds an anchor `@neg:<term>` for the first content term after it (within 4 words). "increase X without downtime" -> `@neg:downtim`; "do not increase X without downtime" -> `@neg:increas`, `@neg:downtim`. One negation therefore never masks another. Only a STATIVE negation followed by "yet" in the same clause ("Ben hasn't answered yet", "src/context is not merged yet": "not"/"n't" after has/have/is/are/was/were/been/still) is a pending state and adds nothing. A prohibition or decision keeps its anchor even with "yet" (review 5): "do not X yet", "don't X yet", "we will not / won't X yet", "never X yet", "must not X yet", and an order opening with "Not yet: X".
- Closure polarity is checked in both directions (review 4): a closing sentence is skipped when it shares a term with the goal that one side negates and the other does not. "We will not increase X; done" never closes "increase X", and "X increased, done" never closes "do not increase X".
- Polar operations (review 6): verbs such as increase/decrease, raise/lower, enable/disable, add/remove, extend/shorten, start/stop, allow/deny/block, include/exclude, upgrade/downgrade, install/uninstall, lock/unlock, promote/demote, attach/detach, cancel, revert, undo, drop add an anchor `@op:<stem>`. Anchors must be identical to merge, and `@op:` is its own kind in anchor_conflict(), so "increase X" and "decrease X" never merge and "X was decreased, done" never closes "increase X". `@op:` anchors identify a goal; they are not closure evidence.
- Negated closure words (review 6): a closing sentence is rejected when a true negation (not, never, no longer, n't) stands in the same clause within 6 words before the closure word: "Widget cache changes are not yet merged into production", "were never merged", "aren't merged yet". A clause break or "but/now" resets it ("were not tested before, but now they are merged" closes).
- Negated closure words also cover quantifier, failure and partial forms (review 7): no, nothing, none, neither, nor, failed to, unable to, yet to, almost, nearly, partially, half. A comma also ends the clause.
- Operations bound to objects (review 7): each operation verb adds `@opobj:<op>><object>`, binding it to the first content word of its object in the same clause (active: the words after the verb; passive "X was increased": the words before). So "increase widget and decrease gadget" and "decrease widget and increase gadget" never merge. A closing sentence that applies another operation to one of the goal's objects never closes it (opobj_conflict). Direction anchors `@dir:<source phrase>><dest>` now use the stemmed multi-word source phrase and cover passive forms ("records were copied into archive"), so "copy production records into archive" != "copy archive records into production". In closure, two direction anchors with the same destination are compatible when one source phrase contains the other's words.
- Plans, conditions and questions never close (review 7, _irrealis_close): a closure word is rejected when a modal or condition (will, 'll, would, should, shall, must, can, could, may, might, if, unless, once, until, whether, when without a past auxiliary, need to, has to, going to, plan to, scheduled to, expected to, to be) stands in its clause within 8 words before it; when a future time word (tomorrow, later, soon, next week...) follows it in its clause; when the sentence is a question; or when the sentence opens with a condition (if, unless, assuming, provided, in case, once). Every closure word in a sentence is checked, and the sentence closes if any one is a clean completion ("had to be merged, and they were merged" closes).
- The adversarial probe set (31 merge pairs, 27 closure cases) is a test fixture in tests/test_goal_lifecycle.py (test_adversarial_merge_probes, test_adversarial_closure_probes), so every later rule change is checked against all earlier failure cases.
- Order: "before" and "after" become `@rel:before` / `@rel:after`; "merge/rebase/cherry-pick A into B" is a direction `@dir:a>b`.
- `@neg` and `@rel:*` identify a goal but are not closure evidence: they are removed from the terms that a closing sentence must share.
- Anchor conflict is checked per kind: entity `@x`, path `@a/b`, task id `@t-...`, number `#N`, direction `@dir:`, order `@rel:`. A shared entity (`@ltm`) therefore does not hide conflicting paths (src/widget vs src/gadget).
- Known limit: symmetric phrasings ("swap A and B" vs "swap B and A") merge on purpose because they mean the same thing; other paraphrases of direction are not modelled.

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

## Future work (design notes, not implemented)
- Speaker provenance ranking: rank goals by who raised them (a human request in chat > a human remark > a self-task derived from my own notes), and keep the speaker and message id on each goal so the rating sheet can show and sort by it.
- New-evidence-only scheduling: re-evaluate a goal only when a new note touches its terms or anchors (or the stale timer fires), instead of re-scanning the whole journal on every cycle; a goal with no new evidence is never re-proposed.
- Approved goals become CoS hive proposals: once a human rates a goal "do it" on the rating sheet, emit a hive `propose` (title, what is wanted, acceptance criteria, source citation telegram:<chat>/<msg>) for the chief of staff to approve and assign; the goal moves to a `proposed` state and is closed by the hive task's outcome.
