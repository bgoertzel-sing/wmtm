# Pre-registration t-2026-11-07-wmtm-f3-ab (written 2026-11-07 15:08 PDT, BEFORE any A/B result)
Source of criterion: andy order projects/wmtm/orders/2026-11-07-wmtm-f3-ab.md (as recorded at acceptance, journal ev-ep-note-20261107T183706Z).
## Arms
- A = live wmtm (unchanged), B = wmtm b62b0f6 (f12 merge) with PeTTaChainer 13c6c9c5, semparse-hitl 477646e1 prompt.
## Sample
- Same 20 notes as P3/P4 (/tmp/p3_out/ab/raw_spec.json; set == NOTE_IDS.txt == P4 rev6 A_shadow items). Ids/hashes only go in the repo.
## Re-parse (pins moved => required)
- Gateway provider via tools/measure_parse.py, cap 20/hour, stop on first 429/usage-limit line.
## Decision criterion (fixed)
1. Count rule: correct(B) >= correct(A) AND wrong(B) <= wrong(A); W1-W4 wrong-conclusion rule exactly as P4.
2. Mesto §11: per-conclusion diff; every conclusion dropped by B listed with a reason.
3. Warm-up <= 120 s.
4. Budget: B <= 2x live weighted usage; median <= 3 min/note; 0 429.
PASS only if 1-4 all hold. Anything else = FAIL, reported as is.
## Sanity gate (docs/EXPERIMENT_SANITY_GATE.md)
- Canary: 1 known note through the exact production parse path; per-note structural check refuses empty/unparseable output; pilot before full run.
