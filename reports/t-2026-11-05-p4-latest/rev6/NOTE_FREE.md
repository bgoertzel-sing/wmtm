# Note-free history (P4 follow-up, criterion 1)

- hive/t-2026-11-06-p4-followup is a new branch off main 965ea636. P4's commits and the follow-up work are squashed into one commit.
- Scrub: task slugs quoted from notes -> `task_ref_<sha256[:6]>`; parser `(Name sk_... "<literal>")` strings in cache_B/cache.jsonl and the p4_note fixture -> `redacted_<sha256[:8]>`; 2 sk_ ids built from note paths -> `sk_ref_<sha8>_1`; 6 prose fragments reworded; W4 judgment #6 rationale rewritten so it reads without the phrase.
- Proof, run after each commit (phrase list and raw notes kept outside git, mode 600):
  1. `git log -p 965ea636..HEAD | grep -i -F -f <phrases>` -> 0 hits (hashes in PHRASE_HASHES.txt).
  2. 5-gram overlap of every added line in `git log -p 965ea636..HEAD` against the full text of the 20 notes in the A/B parse cache, minus 5-grams already on main -> 0 (run on the final commit).
  3. No path named raw_spec.json in any commit (`git log --name-only`); the name only appears in report prose and check.py.
- The order cites 16 phrases; the local list has 13 (one is the single word "working", excluded from grep because it is a common word and also a parser class name). Check 2 covers all note text, not only the listed phrases.
