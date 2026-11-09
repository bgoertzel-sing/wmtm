## Summary

The question was whether the class-level statements in note 181709Z (progress report is a report) and note 185959Z (turn_without_send entry / ltm entry) reach the B knowledge base, and if not, where they get lost. They never come out of the parser. Our wmtm KB build does not drop them. The order says to stop and report in that case, so I stopped at step 0 and made no wmtm code change. I did not run the step-1 fallback that my earlier checkpoint mentioned.

One caveat: F3 v3's exact B parser cache (/tmp/f3/ab/B/cache) was deleted after that task closed. The conclusion therefore rests on F3 v3's saved B KB, a direct probe of the reader, and the two parser caches that still exist. It does not rest on the original raw parse. Humans need to decide: (a) whether the parser should emit flat Inheritance (this question has been open since p3-join-ab on Nov 5), or (b) whether to authorize a wmtm-side fallback that derives Inheritance from the sk_<cls>_* witness shape, which this order does not cover. Optionally, someone can re-parse the same 20 notes with the same pins if a check against the exact raw input is needed.

## Task

t-2026-11-09-wmtm-flat-inheritance-v2: step 0, parser coverage.

Supersedes: t-2026-11-09-wmtm-flat-inheritance

## Evidence

1. reports/t-2026-11-08-wmtm-f3-ab-v3/KB_B_atoms.json has 398 atoms: 251 Member, 147 Implication and 0 Inheritance. The symbols progress_report, turn_without_send, ltm_entry and chat_send each appear 0 times.
2. Reader probe: wmtm.pc_shadow.semparse_facts was given `(: i_x__r1 (Inheritance hive_progress_report progress_report) (STV 1.0 0.99))` and kept it as a fact. A flat Inheritance that the parser emits is therefore not dropped by the KB build.
3. Surviving parser caches: /tmp/p3_out/ab/B2/cache/cache.jsonl (prompt e4c4a76c, 20 items) and reports/t-2026-11-05-p4-latest/rev2_evidence/ab/cache_B/cache.jsonl (645bff3f).
   - In both caches, for 181709Z and 185959Z: 0 Inheritance atoms and 0 target symbols.
   - In B2, 181709Z has 42 atoms. "report" appears only as a Member witness inside a Directive. The parser dropped 10 sentences: 9 catalog_unmapped and 1 issues.
   - In B2, 185959Z has 48 atoms and none of them are about entry, turn_without_send or ltm. The parser dropped 27 sentences: 20 catalog_unmapped, 3 dangling-referent, 3 emission-failed and 1 issues.
   - Neither cache matches F3 v3's KB exactly. Of the 361 normalized KB atoms, 11 match B2 and 23 match p4 cache_B. Neither cache is F3 v3's own input.
4. Arm A's genus links (hive_progress_report→progress_report→report, turn_without_send_entry∈ltm_entry→entry) come from a different parser prompt (the spk1 cache, 2fcbcc54).

## State

Branch hive/t-2026-11-09-wmtm-flat-inheritance-v2 is based on 35dd978. The only change is this report; there are no code changes. The branch is not pushed because there are no GitHub credentials on pop-os. The order file projects/wmtm/orders/2026-11-09-wmtm-flat-inheritance-v2.md is not on this host, so I worked from the accepted task text.
