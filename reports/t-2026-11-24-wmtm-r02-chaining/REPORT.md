# t-2026-11-24-wmtm-r02-chaining: multi-step goal chaining that reads class links (R-02), shadow on 5 frozen runs over the S1 bundle

## Summary
The order asked whether wmtm goal generation that chains several steps and uses class links lets PeTTaChainer draw more correct non-trivial conclusions without new wrong ones. **The answer is no.** Plain chaining (k=2 and k=3) adds 56–82 conclusions per run, mostly correct, but it also adds 4–11 new **wrong** ones per run, so **the count rule fails**. Every wrong one comes from a coref rule carrying a wrong parser coreference (for example "it" or "this" bound to the wrong antecedent) into a second step. With a gate that stops chained steps from reading Coref (`shadow_chain_no_coref`, my choice under the order's no-new-W criterion), the count rule holds (0 new W on all 5 runs), but only +2 correct conclusions per run remain (0 on A1). Those are 2-step supersedes/contradicts conclusions, and +2 is inside the run-to-run noise.

Class links add nothing: the Member/Inheritance class-link rules fire 0 times on every run, with class_links off or on, because the stated Member and Inheritance facts already contain their closure. The strict reader pass is 7–8 of 75 in every arm, the same as the baseline, so the gain is 0. Cost: chaining takes at most 0.45 s against a 10 s budget, and at most 19 chained goals in one note against a cap of 30. k=3 without the gate goes past the 20 s shadow budget on 3 of 5 runs (r1, r2, r3: 1 timeout each, 4–13 goals skipped), and k2cl had 1 timeout on r1. **Recommendation: do not switch chaining on.** The real limit is coreference quality in the parse (P-08), not missing chaining steps. Everything stays off by default.

## Ranges across the 5 runs (A0, A1, r1, r2, r3)
Baseline = S1 bundle (xr, ni and lr on, note_impl_premise off). Arms s1 = class_links off and s1cl = class_links on. k2/k3 compare against s1, k2cl/k3cl against s1cl, and k2g/k3g (gated) against s1.

| arm | new vs base | new C | **new W** | admitted W | reader strict /75 | goals/note | shadow s/note | timeouts | skipped (budget) |
|---|---|---|---|---|---|---|---|---|---|
| s1 | 0–0 | 0–0 | 0–0 | 1–2 | 7–8 | 6.5–7.05 | 0.672–0.929 | 0–0 | 0–0 |
| s1cl | 0–0 | 0–0 | 0–0 | 1–2 | 7–8 | 6.5–7.05 | 0.675–0.928 | 0–0 | 0–0 |
| k2 | 56–71 | 50–64 | 4–7 | 3–9 | 7–8 | 9.45–10.5 | 0.992–1.303 | 0–0 | 0–0 |
| k3 | 68–82 | 56–73 | 4–11 | 5–9 | 7–8 | 10.05–11.35 | 1.18–1.386 | 0–1 | 0–9 |
| k2cl | 56–71 | 50–64 | 4–7 | 3–9 | 7–8 | 9.45–10.5 | 0.938–1.446 | 0–1 | 0–0 |
| k3cl | 68–82 | 56–69 | 4–11 | 5–9 | 7–8 | 10.05–11.35 | 1.219–1.442 | 0–1 | 0–13 |
| k2g | 0–2 | 0–2 | 0–0 | 1–2 | 7–8 | 6.6–7.15 | 0.881–1.401 | 0–0 | 0–0 |
| k3g | 0–2 | 0–2 | 0–0 | 1–2 | 7–8 | 6.6–7.15 | 0.854–1.042 | 0–0 | 0–0 |

- The baseline s1 has admitted W 1–2. Admitted counts are scored with the cap lifted to 1000.
- Reader strict follows the S1 method: a (note, rule) row of the 75-row clerk-ab review3 reader_expect.tsv appears among the proved goals. The figure in brackets in the table below is score_r02's older count of admitted rows against the armB reader_expect (6–7). Both are identical between baseline and chained arms on every run, so neither moves.

## Per-run, per-arm table
Columns: goals/proved/timeouts/skipped · admitted C/W/U/unjudged · narrow (non-restatement) · wide (all proved) · new vs base (n: C/W/U/?) · reader strict /75 (older admitted count) · non-restatement proved · goals per note · shadow seconds per note.

| run | arm | g/p/to/sk | admitted | narrow | wide | new | reader | nonrest | goals/note | s/note |
|---|---|---|---|---|---|---|---|---|---|---|
| A0 | s1 | 130/130/0/0 | 46/1/1/0 | 46/1/1/0 | 121/4/5/0 | 0: 0/0/0/0 | 8 (7) | 48 | 6.5 | 0.757 |
| A0 | s1cl | 130/130/0/0 | 46/1/1/0 | 46/1/1/0 | 121/4/5/0 | 0: 0/0/0/0 | 8 (7) | 48 | 6.5 | 0.675 |
| A0 | k2 | 193/193/0/0 | 93/7/3/0 | 101/7/3/0 | 176/10/7/0 | 63: 55/6/2/0 | 8 (7) | 111 | 9.65 | 0.992 |
| A0 | k3 | 212/212/0/0 | 105/7/3/0 | 114/12/4/0 | 189/15/8/0 | 82: 68/11/3/0 | 8 (7) | 130 | 10.6 | 1.206 |
| A0 | k2cl | 193/193/0/0 | 93/7/3/0 | 101/7/3/0 | 176/10/7/0 | 63: 55/6/2/0 | 8 (7) | 111 | 9.65 | 0.986 |
| A0 | k3cl | 212/212/0/0 | 105/7/3/0 | 114/12/4/0 | 189/15/8/0 | 82: 68/11/3/0 | 8 (7) | 130 | 10.6 | 1.219 |
| A0 | k2g | 132/132/0/0 | 48/1/1/0 | 48/1/1/0 | 123/4/5/0 | 2: 2/0/0/0 | 8 (7) | 50 | 6.6 | 1.401 |
| A0 | k3g | 132/132/0/0 | 48/1/1/0 | 48/1/1/0 | 123/4/5/0 | 2: 2/0/0/0 | 8 (7) | 50 | 6.6 | 0.944 |
| A1 | s1 | 133/133/0/0 | 41/1/1/11 | 42/1/1/11 | 106/2/3/22 | 0: 0/0/0/0 | 7 (6) | 55 | 6.65 | 0.71 |
| A1 | s1cl | 133/133/0/0 | 41/1/1/11 | 42/1/1/11 | 106/2/3/22 | 0: 0/0/0/0 | 7 (6) | 55 | 6.65 | 0.804 |
| A1 | k2 | 189/189/0/0 | 87/3/3/11 | 92/5/3/11 | 156/6/5/22 | 56: 50/4/2/0 | 7 (6) | 111 | 9.45 | 1.003 |
| A1 | k3 | 201/201/0/0 | 93/5/3/11 | 98/10/4/11 | 162/11/6/22 | 68: 56/9/3/0 | 7 (6) | 123 | 10.05 | 1.18 |
| A1 | k2cl | 189/189/0/0 | 87/3/3/11 | 92/5/3/11 | 156/6/5/22 | 56: 50/4/2/0 | 7 (6) | 111 | 9.45 | 0.938 |
| A1 | k3cl | 201/201/0/0 | 93/5/3/11 | 98/10/4/11 | 162/11/6/22 | 68: 56/9/3/0 | 7 (6) | 123 | 10.05 | 1.271 |
| A1 | k2g | 133/133/0/0 | 41/1/1/11 | 42/1/1/11 | 106/2/3/22 | 0: 0/0/0/0 | 7 (6) | 55 | 6.65 | 0.881 |
| A1 | k3g | 133/133/0/0 | 41/1/1/11 | 42/1/1/11 | 106/2/3/22 | 0: 0/0/0/0 | 7 (6) | 55 | 6.65 | 0.854 |
| r1 | s1 | 140/140/0/0 | 46/1/1/6 | 51/1/1/6 | 121/1/4/14 | 0: 0/0/0/0 | 8 (7) | 59 | 7.0 | 0.672 |
| r1 | s1cl | 140/140/0/0 | 46/1/1/6 | 51/1/1/6 | 121/1/4/14 | 0: 0/0/0/0 | 8 (7) | 59 | 7.0 | 0.73 |
| r1 | k2 | 209/209/0/0 | 100/5/2/6 | 115/5/2/6 | 185/5/5/14 | 69: 64/4/1/0 | 8 (7) | 128 | 10.45 | 1.29 |
| r1 | k3 | 226/221/1/4 | 109/5/2/6 | 124/7/3/6 | 194/7/6/14 | 81: 73/6/2/0 | 8 (7) | 140 | 11.3 | 1.383 |
| r1 | k2cl | 209/208/1/0 | 99/5/2/6 | 114/5/2/6 | 184/5/5/14 | 68: 63/4/1/0 | 8 (7) | 127 | 10.45 | 1.401 |
| r1 | k3cl | 226/217/1/8 | 105/5/2/6 | 120/7/3/6 | 190/7/6/14 | 77: 69/6/2/0 | 8 (7) | 136 | 11.3 | 1.41 |
| r1 | k2g | 142/142/0/0 | 48/1/1/6 | 53/1/1/6 | 123/1/4/14 | 2: 2/0/0/0 | 8 (7) | 61 | 7.1 | 1.04 |
| r1 | k3g | 142/142/0/0 | 48/1/1/6 | 53/1/1/6 | 123/1/4/14 | 2: 2/0/0/0 | 8 (7) | 61 | 7.1 | 0.992 |
| r2 | s1 | 138/138/0/0 | 45/2/2/6 | 45/2/2/6 | 115/4/6/13 | 0: 0/0/0/0 | 8 (7) | 55 | 6.9 | 0.864 |
| r2 | s1cl | 138/138/0/0 | 45/2/2/6 | 45/2/2/6 | 115/4/6/13 | 0: 0/0/0/0 | 8 (7) | 55 | 6.9 | 0.928 |
| r2 | k2 | 209/209/0/0 | 101/6/5/6 | 108/6/5/6 | 179/8/9/13 | 71: 64/4/3/0 | 8 (7) | 125 | 10.45 | 1.303 |
| r2 | k3 | 219/209/1/9 | 101/6/5/6 | 108/6/5/6 | 179/8/9/13 | 71: 64/4/3/0 | 8 (7) | 125 | 10.95 | 1.386 |
| r2 | k2cl | 209/209/0/0 | 101/6/5/6 | 108/6/5/6 | 179/8/9/13 | 71: 64/4/3/0 | 8 (7) | 125 | 10.45 | 1.446 |
| r2 | k3cl | 219/211/1/7 | 103/6/5/6 | 110/6/5/6 | 181/8/9/13 | 73: 66/4/3/0 | 8 (7) | 127 | 10.95 | 1.43 |
| r2 | k2g | 140/140/0/0 | 47/2/2/6 | 47/2/2/6 | 117/4/6/13 | 2: 2/0/0/0 | 8 (7) | 57 | 7.0 | 1.044 |
| r2 | k3g | 140/140/0/0 | 47/2/2/6 | 47/2/2/6 | 117/4/6/13 | 2: 2/0/0/0 | 8 (7) | 57 | 7.0 | 0.965 |
| r3 | s1 | 141/141/0/0 | 50/2/1/0 | 54/2/1/0 | 128/4/5/4 | 0: 0/0/0/0 | 7 (6) | 57 | 7.05 | 0.929 |
| r3 | s1cl | 141/141/0/0 | 50/2/1/0 | 54/2/1/0 | 128/4/5/4 | 0: 0/0/0/0 | 7 (6) | 57 | 7.05 | 0.862 |
| r3 | k2 | 210/210/0/0 | 102/9/2/0 | 115/9/2/0 | 189/11/6/4 | 69: 61/7/1/0 | 7 (6) | 126 | 10.5 | 1.087 |
| r3 | k3 | 227/219/1/7 | 108/9/2/0 | 121/12/2/0 | 195/14/6/4 | 78: 67/10/1/0 | 7 (6) | 135 | 11.35 | 1.385 |
| r3 | k2cl | 210/210/0/0 | 102/9/2/0 | 115/9/2/0 | 189/11/6/4 | 69: 61/7/1/0 | 7 (6) | 126 | 10.5 | 1.335 |
| r3 | k3cl | 227/213/1/13 | 102/9/2/0 | 115/12/2/0 | 189/14/6/4 | 72: 61/10/1/0 | 7 (6) | 129 | 11.35 | 1.442 |
| r3 | k2g | 143/143/0/0 | 52/2/1/0 | 56/2/1/0 | 130/4/5/4 | 2: 2/0/0/0 | 7 (6) | 59 | 7.15 | 0.973 |
| r3 | k3g | 143/143/0/0 | 52/2/1/0 | 56/2/1/0 | 130/4/5/4 | 2: 2/0/0/0 | 7 (6) | 59 | 7.15 | 1.042 |

- The unjudged entries in admitted, narrow and wide (A1, r1, r2, r3) are baseline coref goals that have no earlier verdict, carried over unchanged from S1. They are the same in every arm. **Every new conclusion is judged: 0 unjudged.**
- The 128 distinct chained conclusions are judged in `verdicts_r02.tsv` (r001–r128): 100 C, 23 W, 5 U. Each was judged from the note's own sentence plus the premises the chain used. That file holds the goal atoms (goalkey column), which are note-derived, so it is kept **only in the evidence directory** (/srv/hive-evidence/t-2026-11-24-wmtm-r02-chaining/verdicts_r02.tsv, where score_r02.py reads it) and is not in git. The sentence and premise text used for judging stayed in a private 0700 temp dir that was deleted after judging. Git carries only ids, rule ids and counts (failing_WU.tsv, score.json, reader.json).

## Failing conclusions (count rule): failing_WU.tsv
Ids only; the rule is `chain<depth>:<rule id>`. W by rule: coref_member 10, coref_patient 6, coref_theme 4, coref_agent 2, coref_goal 1. Every W is a coreference error from the parser carried one or two steps further. None of them occurs in the gated arms.

```
id	rule	verdict	n_runarms	runs_arms
r006	chain3:coref_member	W	4	A0/k3,A0/k3cl,A1/k3,A1/k3cl
r007	chain3:coref_member	W	6	A0/k3,A0/k3cl,A1/k3,A1/k3cl,r1/k3,r1/k3cl
r008	chain3:coref_member	U	6	A0/k3,A0/k3cl,A1/k3,A1/k3cl,r1/k3,r1/k3cl
r034	chain2:coref_member	U	8	A1/k2,A1/k3,A1/k2cl,A1/k3cl,r2/k2,r2/k3,r2/k2cl,r2/k3cl
r035	chain2:coref_member	U	8	A1/k2,A1/k3,A1/k2cl,A1/k3cl,r2/k2,r2/k3,r2/k2cl,r2/k3cl
r079	chain2:coref_member	W	8	r1/k2,r1/k3,r1/k2cl,r1/k3cl,r3/k2,r3/k3,r3/k2cl,r3/k3cl
r086	chain2:coref_patient	W	4	r1/k2,r1/k3,r1/k2cl,r1/k3cl
r088	chain2:coref_theme	W	4	r3/k2,r3/k3,r3/k2cl,r3/k3cl
r090	chain3:coref_member	W	2	A1/k3,A1/k3cl
r091	chain3:coref_patient	W	2	A1/k3,A1/k3cl
r092	chain2:coref_agent	W	4	r3/k2,r3/k3,r3/k2cl,r3/k3cl
r102	chain2:coref_member	W	20	A0/k2,A0/k3,A0/k2cl,A0/k3cl,A1/k2,A1/k3,A1/k2cl,A1/k3cl,r1/k2,r1/k3,r1/k2cl,r1/k3cl,r2/k2,r2/k3,r2/k2cl,r2/k3cl,r3/k2,r3/k3,r3/k2cl,r3/k3cl
r103	chain2:coref_member	W	20	A0/k2,A0/k3,A0/k2cl,A0/k3cl,A1/k2,A1/k3,A1/k2cl,A1/k3cl,r1/k2,r1/k3,r1/k2cl,r1/k3cl,r2/k2,r2/k3,r2/k2cl,r2/k3cl,r3/k2,r3/k3,r3/k2cl,r3/k3cl
r104	chain2:coref_patient	U	8	A0/k2,A0/k3,A0/k2cl,A0/k3cl,r1/k2,r1/k3,r1/k2cl,r1/k3cl
r107	chain3:coref_agent	W	2	r3/k3,r3/k3cl
r108	chain3:coref_member	W	2	r3/k3,r3/k3cl
r109	chain3:coref_member	W	2	r3/k3,r3/k3cl
r110	chain3:coref_patient	W	4	A0/k3,A0/k3cl,r1/k3,r1/k3cl
r115	chain2:coref_member	W	8	A0/k2,A0/k3,A0/k2cl,A0/k3cl,A1/k2,A1/k3,A1/k2cl,A1/k3cl
r116	chain2:coref_member	W	12	A0/k2,A0/k3,A0/k2cl,A0/k3cl,r2/k2,r2/k3,r2/k2cl,r2/k3cl,r3/k2,r3/k3,r3/k2cl,r3/k3cl
r118	chain2:coref_patient	W	4	A1/k2,A1/k3,A1/k2cl,A1/k3cl
r119	chain2:coref_patient	W	8	r2/k2,r2/k3,r2/k2cl,r2/k3cl,r3/k2,r3/k3,r3/k2cl,r3/k3cl
r120	chain2:coref_possession	U	12	A0/k2,A0/k3,A0/k2cl,A0/k3cl,r2/k2,r2/k3,r2/k2cl,r2/k3cl,r3/k2,r3/k3,r3/k2cl,r3/k3cl
r123	chain2:coref_theme	W	4	A0/k2,A0/k3,A0/k2cl,A0/k3cl
r124	chain2:coref_theme	W	4	A0/k2,A0/k3,A0/k2cl,A0/k3cl
r125	chain3:coref_goal	W	2	A0/k3,A0/k3cl
r126	chain3:coref_patient	W	2	A1/k3,A1/k3cl
r127	chain3:coref_theme	W	2	A0/k3,A0/k3cl
```

## Design (Do 1)
- `master_loader.chain_goals`, flag `shadow_chain_k` (int, default 0; 0 or 1 = off). Step 1 is the existing `rule_goals`, unchanged.
- Steps 2..k use every ground conclusion of the step before as a premise for the same rules (seeded plus extra). Two class-link rules are added: (Member x A) with (Inheritance A B) gives (Member x B), and (Inheritance A B) with (Inheritance B C) gives (Inheritance A C).
- The search is semi-naive: each new goal must use a conclusion from the step just before, so a cycle stops once nothing new appears (test `test_cycle_terminates` uses k=10).
- **Cross-note check.** Each fact has a home note:
  - the note suffix in its symbols, if it has one;
  - otherwise the note that states it (plan()'s label to note id);
  - a fact stated in several notes is shared by those notes;
  - a fact stated in no note and with no suffix (definitions, kind__ links) is free.
  A combination's home is the intersection over all premises used. If that intersection is empty, the combination is refused and counted (`cross_note_refused`: 5–13 per run). A derived fact keeps that home. Extra rules also keep the existing one-note binding check.
- A first version looked only at symbol suffixes, which treated 188–206 note-stated facts per run as shared. It was replaced before scoring; its specs are kept under `superseded_v1/` and none of them are scored.
- **Caps:** `shadow_chain_max_per_note` 30 new chained goals per note, `shadow_chain_budget_s` 10 s of wall time for steps 2..k, and the existing max_envs of 200 per premise. Anything that hits a cap is counted. Two limits on these caps: (a) `budget_s` is checked only before each step starts, so it is not a hard bound inside one step (a single step could overrun it; measured maximum 0.45 s, so it did not matter here); (b) the 200-env cap per premise did trim candidates in every chained arm (`envs_cut` per run: k2/k2cl/k2g 410–492, k3/k3cl 686–824, k3g 492–738), so the chained goal sets are a truncated, order-dependent sample, not the full closure. The ungated W count is therefore a lower bound; the gated null is a result on that sample. Measured: per-note max 19, chaining time at most 0.45 s, budget_hit 0 and capped 0 on all runs.
- Gate: `shadow_chain_no_coref` (default false). It makes chained steps (depth 2 or more) skip any rule with a Coref premise.
- Synthetic tests in `tests/test_chain_goals.py` (7):
  - flag off by default;
  - a chain fires (rule→rule, Inheritance transitivity, Member through a class link);
  - a cycle terminates;
  - cross-note facts do not chain unless a premise is shared (once by suffix, once by source label);
  - the cap is counted;
  - the no-coref gate works.
  The new flags are in the README flags table.

## Acceptance
1. **Flag off: byte-identical** to the S1 bundle on all 5 runs. The s1 spec built at this branch equals the s1 spec built at 7fa69af, s1cl equals s1cl, and s1cl equals the archived S1 `all` arm (basecheck.out, 15/15).
2. **Count rule:** it fails for plain chaining (new W 4–11 per run). The failing conclusions are shown above. It holds with the coref gate (0 new W on all 5 runs).
3. **Gain vs noise, stated plainly:** the strict reader pass gain is 0 in every arm. Correct conclusions: ungated +50 to +73 C per run, but with new W. Gated +0 to +2 C per run, which is within the run-to-run range of baseline admitted C (41–50), so it is **not an improvement**. class_links: 0 effect.
4. **Cost within the caps:** see the ranges table. Chaining caps were never hit. The shadow budget (20 s) is kept by k2, k2g and k3g (0 timeouts and 0 skipped). k2cl has 1 timeout on r1 (0 skipped). k3/k3cl break it on 3 of 5 runs (r1, r2, r3).

## Details
- Base: wmtm fd48815, via the S1 branch 7fa69af (unmerged; the baseline the order names). Branch hive/t-2026-11-24-wmtm-r02-chaining in worktree projects/omegaclaw/r02/wmtm-wt. Not pushed.
- Pins: templates sph-24e37182 (rules 9c58f2e0), PeTTa mh-rules-on-roman, vendor PeTTaChainer ~/scratch/ppv/pc. 0 parse calls (spy). Parse files unchanged (md5 before = after).
- Full suite: 1638 passed, 70 skipped, 5 xfailed in 33.25s.
- 40 shadow runs in total (5 runs × 8 arms), all rc 0, status ok and canary ok. run_all.sh ends with a completion-count assertion (30/30 and 10/10).
- Evidence: /srv/hive-evidence/t-2026-11-24-wmtm-r02-chaining/ (tools/, runs/, base_runs/, superseded_v1/, score.json, reader.json, verdicts_r02.tsv, failing_WU.tsv, basecheck.out, recompute.sh, recompute.out, suite.out, SHA256SUMS). recompute.sh is counts-only, runs in a mktemp dir and reproduces score.json byte for byte.

## Review 1 fixes
| finding | fix |
|---|---|
| Blocking: verdicts_r02.tsv with note-derived goalkey atoms committed to git | Branch rewritten (never pushed) so no commit contains the file; verdicts stay in the evidence dir only, as in S1. Checked: `git log -p 7fa69af..HEAD` has 0 note-derived atoms. |
| Minor: time budget not a hard bound | Stated in Design/Caps above. |
| Minor: envs_cut trimming not reported | Figures per arm added in Design/Caps; W count framed as lower bound. |
| Minor: report said goal text not in evidence | Corrected: goal atoms are in the evidence copy of verdicts_r02.tsv, not in git. |
