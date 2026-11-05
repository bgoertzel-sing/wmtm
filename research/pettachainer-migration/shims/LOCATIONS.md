# Per-shim locations (generated from shims/rt49ca-vs-shimmed.diff)

Line numbers are in the SHIMMED tree (the `+++` side of the diff); paths are relative to external/PeTTaChainer/.
Generated mechanically from the tags each edited line carries. 583 hunks in 67 files; 14 hunks carry no tag and are listed at the end with their first changed line.

Early shims (1-13) predate tagging. Their locations are in their own unified diffs: `bootstrap.shim4b.diff` (shim2/3/4/4b), `natives.shim4c.diff` (shim4c), `runtime_helpers.shim9.diff` (shim9-12), `evidence_chainer.py.diff` (shim8, GoalChainer :85), `goalchainer_pettachainer.metta.diff` (GoalChainer :44-45). shim1/5/7 arrow rewrites were later overwritten by the tagged shim15/17/18 edits at the same declaration lines, so they appear under those tags.

## shim3 (1 hunks, 1 files)
- `pettachainer/metta/prolog/runtime_helpers.pl`: lines 6-11

## shim13 (1 hunks, 1 files)
- `pettachainer/metta/prolog/ingestion.pl`: lines 326-354

## shim14 (1 hunks, 1 files)
- `pettachainer/metta/lib/natives.pl`: lines 81-85

## shim15 (146 hunks, 36 files)
- `pettachainer/metta/compiler/rules.metta`: lines 611-611
- `pettachainer/metta/compiler/runtime_encoding.metta`: lines 67-67
- `pettachainer/metta/compiler/source_lowering.metta`: lines 44-44, 174-174, 349-349, 362-362
- `pettachainer/metta/runtime/backward/execution.metta`: lines 3-3, 119-119, 146-146, 157-164, 177-181, 216-216
- `pettachainer/metta/runtime/backward/forgetting.metta`: lines 53-53, 64-71, 142-142
- `pettachainer/metta/runtime/backward/skeleton.metta`: lines 73-95, 112-119, 148-148, 173-173, 181-187, 297-297, 355-362, 506-506, 528-528, 569-569, 608-608, 637-641, 741-745, 773-785, 824-824, 900-900, 916-916, 933-933, 1045-1059, 1075-1075, 1085-1085, 1120-1120, 1145-1145, 1162-1167, 1192-1197, 1213-1214, 1247-1248, 1269-1269, 1290-1295, 1371-1371, 1388-1398, 1424-1429
- `pettachainer/metta/runtime/backward/upward.metta`: lines 23-23, 31-31, 75-82, 115-115, 247-247
- `pettachainer/metta/runtime/evaluator/core.metta`: lines 163-167
- `pettachainer/metta/runtime/evaluator/evaluation.metta`: lines 33-33, 54-54, 88-88, 101-131
- `pettachainer/metta/runtime/evaluator/folds.metta`: lines 193-193, 205-205, 216-216, 363-363
- `pettachainer/metta/runtime/evaluator/sampling.metta`: lines 69-69
- `pettachainer/metta/runtime/evaluator/values.metta`: lines 487-495
- `pettachainer/metta/runtime/evaluator/versions.metta`: lines 92-96, 192-210, 340-344, 516-537, 545-549, 1159-1179, 1202-1206, 1215-1215, 1232-1232, 1242-1242
- `pettachainer/metta/runtime/evaluator/work.metta`: lines 13-23, 172-172, 288-288, 373-373, 402-402, 518-522, 621-621, 806-806, 814-821, 845-845
- `pettachainer/metta/runtime/fact_reads/selection.metta`: lines 59-59
- `pettachainer/metta/runtime/hypothesis_mining.metta`: lines 16-16, 54-54, 66-66
- `pettachainer/metta/runtime/hypothesis_review.metta`: lines 60-60, 85-85, 100-100, 132-132, 161-161
- `pettachainer/metta/runtime/installation.metta`: lines 30-30
- `pettachainer/metta/runtime/kb_publication.metta`: lines 44-61, 85-91, 101-101, 114-114, 132-132, 145-145, 156-156
- `pettachainer/metta/runtime/kb_publication.metta.orig62`: lines 1-166
- `pettachainer/metta/runtime/kb_publication.metta.orig68`: lines 1-170
- `pettachainer/metta/runtime/presentation.metta`: lines 80-80
- `pettachainer/metta/runtime/proofs.metta`: lines 304-319
- `pettachainer/metta/runtime/skeleton_journal.metta`: lines 2-2, 19-22, 31-36
- `pettachainer/metta/runtime/statistics/aggregates.metta`: lines 59-87, 142-142
- `pettachainer/metta/runtime/statistics/base_rates.metta`: lines 16-16
- `pettachainer/metta/runtime/statistics/ledger.metta`: lines 52-52, 119-128, 162-171, 182-182, 217-222, 251-262, 277-277, 285-285
- `pettachainer/metta/runtime/statistics/plans.metta`: lines 11-18
- `pettachainer/metta/runtime/store/allowances.metta`: lines 38-38, 46-46
- `pettachainer/metta/runtime/store/contracts.metta`: lines 1-1
- `pettachainer/metta/runtime/store/journal.metta`: lines 9-9, 25-25
- `pettachainer/metta/runtime/store/rows.metta`: lines 1-1
- `pettachainer/metta/runtime/store/rule_identity.metta`: lines 77-84
- `pettachainer/metta/runtime/store/search_index.metta`: lines 5-11, 27-27, 43-52, 63-63, 86-86, 123-123, 176-176, 184-191, 203-213, 221-221, 231-231
- `pettachainer/metta/runtime/store/value_store.metta`: lines 88-92, 139-139, 164-171, 208-208, 241-241, 250-250
- `pettachainer/metta/runtime/values.metta`: lines 3-3, 82-82, 97-112

## shim15b (18 hunks, 8 files)
- `pettachainer/metta/compiler/runtime_encoding.metta`: lines 11-11
- `pettachainer/metta/compiler/source_lowering.metta`: lines 128-128, 144-144
- `pettachainer/metta/runtime/backward/eval_cache.metta`: lines 5-5
- `pettachainer/metta/runtime/backward/skeleton.metta`: lines 73-95, 773-785, 1162-1167, 1388-1398
- `pettachainer/metta/runtime/evaluator/work.metta`: lines 13-23, 590-597, 638-638, 685-685, 698-698, 870-870
- `pettachainer/metta/runtime/statistics/ledger.metta`: lines 217-222, 238-238
- `pettachainer/metta/runtime/store/allowances.metta`: lines 89-95
- `pettachainer/metta/runtime/store/value_store.metta`: lines 264-264

## shim17 (3 hunks, 2 files)
- `pettachainer/metta/compiler/source_lowering.metta`: lines 108-108, 293-293
- `pettachainer/metta/lib/collections.metta`: lines 2-36

## shim18 (290 hunks, 50 files)
- `pettachainer/metta/compiler/query_lowering.metta`: lines 142-142, 157-157, 412-412
- `pettachainer/metta/compiler/rules.metta`: lines 60-60, 71-78, 92-92, 171-171, 383-383, 493-493, 642-642, 671-671, 725-725, 762-762
- `pettachainer/metta/compiler/runtime_encoding.metta`: lines 67-67
- `pettachainer/metta/compiler/source_lowering.metta`: lines 224-224, 256-256, 267-267, 349-349, 601-601, 632-632, 644-644, 660-660, 678-678
- `pettachainer/metta/core/logic_config.metta`: lines 18-18
- `pettachainer/metta/core/runtime_terms.metta`: lines 14-21
- `pettachainer/metta/core/search_terms.metta`: lines 112-112
- `pettachainer/metta/core/vocabulary.metta`: lines 17-17, 35-35, 52-67
- `pettachainer/metta/lib/collections.metta`: lines 2-36
- `pettachainer/metta/lib/natives.metta`: lines 13-32
- `pettachainer/metta/petta_chainer.metta`: lines 7-12
- `pettachainer/metta/runtime/application_discovery/plans.metta`: lines 6-13, 99-104, 127-127
- `pettachainer/metta/runtime/application_discovery/policy.metta`: lines 3-3
- `pettachainer/metta/runtime/backward/diagnostics.metta`: lines 35-35, 47-47
- `pettachainer/metta/runtime/backward/execution.metta`: lines 177-181, 224-224
- `pettachainer/metta/runtime/backward/forgetting.metta`: lines 15-30
- `pettachainer/metta/runtime/backward/skeleton.metta`: lines 22-22, 34-34, 73-95, 103-103, 163-163, 283-288, 312-312, 324-324, 355-362, 550-559, 620-620, 945-945, 961-969, 1045-1059, 1104-1104, 1145-1145, 1290-1295, 1309-1316, 1388-1398
- `pettachainer/metta/runtime/backward/upward.metta`: lines 91-91, 133-137, 155-155, 221-221
- `pettachainer/metta/runtime/configuration.metta`: lines 14-14, 24-24
- `pettachainer/metta/runtime/evaluator/core.metta`: lines 48-48, 118-118, 163-167, 178-178, 292-292, 319-319, 339-339, 383-383, 631-631, 665-665, 762-762, 802-802, 869-869
- `pettachainer/metta/runtime/evaluator/evaluation.metta`: lines 64-69, 78-78, 101-131, 199-199, 241-241, 253-253
- `pettachainer/metta/runtime/evaluator/folds.metta`: lines 3-3, 31-31, 44-44, 64-64, 246-246, 297-297, 307-307, 338-338
- `pettachainer/metta/runtime/evaluator/merge.metta`: lines 50-50, 58-58, 73-80, 92-98, 110-110, 119-119, 127-127, 188-188, 206-206, 214-214, 237-237, 246-246, 257-257, 270-270, 289-289, 300-300, 308-308, 319-319, 332-332
- `pettachainer/metta/runtime/evaluator/sampling.metta`: lines 2-2, 35-35
- `pettachainer/metta/runtime/evaluator/stored_facts.metta`: lines 72-72
- `pettachainer/metta/runtime/evaluator/values.metta`: lines 110-110, 118-136, 282-289, 305-305, 316-316, 330-334, 342-342, 517-517, 533-561, 577-577, 586-589, 607-607, 621-621, 630-644, 686-686, 703-721, 744-752, 791-791, 809-821, 837-837, 878-878, 939-947, 958-958, 975-975, 987-990, 999-999, 1021-1025, 1058-1069, 1077-1081, 1089-1096, 1104-1120, 1130-1134, 1150-1150, 1161-1172, 1185-1194, 1223-1230, 1238-1243
- `pettachainer/metta/runtime/evaluator/versions.metta`: lines 32-32, 84-84, 92-96, 129-129, 140-140, 153-153, 161-174, 192-210, 220-227, 235-244, 275-282, 374-388, 401-405, 420-420, 428-432, 456-460, 472-472, 516-537, 578-588, 624-624, 633-633, 671-683, 693-707, 741-741, 763-763, 850-857, 873-873, 912-912, 954-961, 970-970, 999-999, 1031-1031, 1114-1120, 1159-1179, 1202-1206
- `pettachainer/metta/runtime/evaluator/work.metta`: lines 172-172, 214-214, 288-288, 402-402, 421-421, 518-522, 590-597, 611-611, 621-621, 745-745, 777-777, 786-790, 814-821, 884-884
- `pettachainer/metta/runtime/fact_reads/policy.metta`: lines 7-18
- `pettachainer/metta/runtime/fact_reads/selection.metta`: lines 48-48, 75-75, 85-85
- `pettachainer/metta/runtime/hypothesis_mining.metta`: lines 102-102, 168-168, 182-182, 214-214
- `pettachainer/metta/runtime/hypothesis_review.metta`: lines 33-33, 60-60, 115-115
- `pettachainer/metta/runtime/ingest.metta`: lines 2-8
- `pettachainer/metta/runtime/installation.metta`: lines 49-56, 128-128, 142-149, 166-171, 188-188, 200-200
- `pettachainer/metta/runtime/kb_publication.metta`: lines 30-30, 71-75, 85-91
- `pettachainer/metta/runtime/kb_publication.metta.orig62`: lines 1-166
- `pettachainer/metta/runtime/kb_publication.metta.orig68`: lines 1-170
- `pettachainer/metta/runtime/observed_predicates.metta`: lines 25-25
- `pettachainer/metta/runtime/presentation.metta`: lines 11-11, 24-24, 38-38, 46-51, 63-63
- `pettachainer/metta/runtime/proofs.metta`: lines 3-10, 44-44, 52-55, 69-78, 149-151, 163-167, 292-292, 304-319
- `pettachainer/metta/runtime/query.metta`: lines 37-37, 76-76, 95-103
- `pettachainer/metta/runtime/statistics/aggregates.metta`: lines 46-46, 59-87, 101-101, 128-128, 154-154, 162-169
- `pettachainer/metta/runtime/statistics/base_rates.metta`: lines 30-30, 39-39, 47-51, 59-59
- `pettachainer/metta/runtime/statistics/ledger.metta`: lines 6-6, 17-17, 31-31, 61-61, 81-85, 96-96, 145-145, 162-171, 251-262
- `pettachainer/metta/runtime/statistics/plans.metta`: lines 11-18, 51-51, 82-105, 113-113, 130-130, 139-139, 153-157, 168-168, 179-179, 203-203
- `pettachainer/metta/runtime/store/allowances.metta`: lines 73-73, 81-81
- `pettachainer/metta/runtime/store/rule_identity.metta`: lines 35-35, 50-50, 61-61, 77-84
- `pettachainer/metta/runtime/store/search_index.metta`: lines 19-19, 99-99, 111-111, 152-152, 184-191, 203-213, 241-241
- `pettachainer/metta/runtime/store/value_store.metta`: lines 5-5, 46-46, 164-171, 190-190, 208-208, 275-275
- `pettachainer/metta/runtime/values.metta`: lines 97-112

## shim19 (388 hunks, 23 files)
- `pettachainer/metta/compiler/fold_sources.metta`: lines 3-3, 20-20
- `pettachainer/metta/core/runtime_terms_keys.metta`: lines 5-5, 25-32
- `pettachainer/metta/core/search_terms.metta`: lines 112-112, 135-135
- `pettachainer/metta/runtime/application_discovery/plans.metta`: lines 6-13, 21-21, 37-37, 55-62, 99-104, 127-127
- `pettachainer/metta/runtime/application_discovery/policy.metta`: lines 3-3
- `pettachainer/metta/runtime/backward/diagnostics.metta`: lines 21-25, 35-35, 47-47, 63-63
- `pettachainer/metta/runtime/backward/execution.metta`: lines 3-3, 119-119, 146-146, 157-164, 177-181, 216-216, 224-224
- `pettachainer/metta/runtime/backward/forgetting.metta`: lines 15-30, 45-45, 53-53, 64-71, 100-100, 118-118, 142-142
- `pettachainer/metta/runtime/backward/skeleton.metta`: lines 5-10, 22-22, 34-34, 44-44, 73-95, 103-103, 112-119, 148-148, 163-163, 173-173, 181-187, 283-288, 297-297, 312-312, 324-324, 336-336, 355-362, 506-506, 528-528, 550-559, 569-569, 598-598, 608-608, 620-620, 628-628, 637-641, 652-652, 732-732, 741-745, 773-785, 824-824, 900-900, 916-916, 933-933, 945-945, 961-969, 1045-1059, 1075-1075, 1085-1085, 1104-1104, 1120-1120, 1131-1131, 1145-1145, 1162-1167, 1192-1197, 1213-1214, 1247-1248, 1269-1269, 1290-1295, 1309-1316, 1335-1341, 1362-1362, 1371-1371, 1388-1398, 1424-1429
- `pettachainer/metta/runtime/evaluator/evaluation.metta`: lines 5-5, 14-14, 33-33, 43-43, 54-54, 64-69, 78-78, 88-88, 101-131, 139-139, 150-150, 175-175, 199-199, 214-214, 227-230, 241-241, 253-253
- `pettachainer/metta/runtime/evaluator/folds.metta`: lines 3-3, 31-31, 44-44, 64-64, 161-161, 193-193, 205-205, 216-216, 235-235, 246-246, 272-272, 288-288, 297-297, 307-307, 338-338, 363-363
- `pettachainer/metta/runtime/evaluator/merge.metta`: lines 5-5, 26-26, 50-50, 58-58, 73-80, 92-98, 110-110, 119-119, 127-127, 146-146, 160-160, 175-175, 188-188, 206-206, 214-214, 237-237, 246-246, 257-257, 270-270, 289-289, 300-300, 308-308, 319-319, 332-332
- `pettachainer/metta/runtime/evaluator/values.metta`: lines 21-21, 34-34, 45-45, 63-63, 75-75, 99-99, 110-110, 118-136, 148-161, 176-184, 204-204, 221-221, 231-235, 250-250, 282-289, 305-305, 316-316, 330-334, 342-342, 363-363, 374-382, 397-397, 424-424, 439-442, 487-495, 509-509, 517-517, 533-561, 577-577, 586-589, 607-607, 621-621, 630-644, 667-667, 678-678, 686-686, 703-721, 736-736, 744-752, 773-773, 791-791, 809-821, 837-837, 857-857, 878-878, 898-898, 920-920, 930-930, 939-947, 958-958, 975-975, 987-990, 999-999, 1007-1007, 1021-1025, 1034-1041, 1049-1049, 1058-1069, 1077-1081, 1089-1096, 1104-1120, 1130-1134, 1150-1150, 1161-1172, 1185-1194, 1223-1230, 1238-1243
- `pettachainer/metta/runtime/evaluator/versions.metta`: lines 1-8, 22-22, 32-32, 84-84, 92-96, 116-116, 129-129, 140-140, 153-153, 161-174, 192-210, 220-227, 235-244, 252-252, 265-265, 275-282, 292-299, 311-311, 332-332, 340-344, 360-366, 374-388, 401-405, 420-420, 428-432, 447-447, 456-460, 472-472, 507-507, 516-537, 545-549, 557-557, 578-588, 597-597, 607-607, 624-624, 633-633, 642-642, 652-652, 671-683, 693-707, 721-721, 741-741, 763-763, 787-787, 797-797, 813-813, 837-837, 850-857, 865-865, 873-873, 890-890, 912-912, 954-961, 970-970, 999-999, 1008-1008, 1017-1017, 1031-1031, 1054-1061, 1076-1076, 1114-1120, 1129-1129, 1159-1179, 1188-1193, 1202-1206, 1215-1215, 1232-1232, 1242-1242
- `pettachainer/metta/runtime/evaluator/work.metta`: lines 13-23, 39-57, 71-71, 80-80, 111-111, 141-144, 172-172, 186-186, 214-214, 240-240, 256-256, 288-288, 311-311, 350-350, 359-359, 373-373, 402-402, 421-421, 452-452, 503-503, 518-522, 540-540, 551-551, 590-597, 611-611, 621-621, 638-638, 646-652, 666-673, 685-685, 698-698, 745-745, 777-777, 786-790, 806-806, 814-821, 845-845, 853-853, 870-870, 884-884
- `pettachainer/metta/runtime/fact_reads/policy.metta`: lines 7-18, 26-26, 40-40
- `pettachainer/metta/runtime/fact_reads/selection.metta`: lines 3-3, 28-35, 48-48, 59-59, 75-75, 85-85, 103-109, 118-128
- `pettachainer/metta/runtime/kb_publication.metta`: lines 18-18, 30-30, 44-61, 71-75, 85-91, 101-101, 114-114, 132-132, 145-145, 156-156
- `pettachainer/metta/runtime/kb_publication.metta.orig62`: lines 1-166
- `pettachainer/metta/runtime/kb_publication.metta.orig68`: lines 1-170
- `pettachainer/metta/runtime/proofs.metta`: lines 3-10, 19-19, 33-36, 44-44, 52-55, 69-78, 149-151, 163-167, 175-181, 193-193, 220-220, 229-229, 266-266, 292-292, 304-319, 333-340, 351-351, 377-378, 401-401, 409-415, 424-434
- `pettachainer/metta/runtime/statistics/aggregates.metta`: lines 46-46, 59-87, 101-101, 120-120, 128-128, 142-142, 154-154, 162-169
- `pettachainer/metta/runtime/store/search_index.metta`: lines 5-11, 19-19, 27-27, 43-52, 63-63, 71-71, 86-86, 99-99, 111-111, 123-123, 152-152, 176-176, 184-191, 203-213, 221-221, 231-231, 241-241

## shim20 (2 hunks, 2 files)
- `pettachainer/metta/lib/natives.metta`: lines 13-32
- `pettachainer/metta/prolog/ingestion.pl`: lines 326-354

## shim21 (1 hunks, 1 files)
- `pettachainer/metta/runtime/store/fact_index.metta`: lines 28-28

## shim22 (1 hunks, 1 files)
- `pettachainer/metta/prolog/term_index.pl`: lines 108-110

## shim23 (14 hunks, 1 files)
- `pettachainer/metta/core/natives.metta`: lines 7-25, 57-57, 73-75, 91-94, 108-108, 120-127, 155-165, 178-193, 201-245, 253-261, 273-273, 292-292, 301-301, 324-341

## pcmig probe63 (2 hunks, 2 files)
- `pettachainer/metta/runtime/kb_publication.metta`: lines 44-61
- `pettachainer/metta/runtime/kb_publication.metta.orig68`: lines 1-170

## pcmig probe68 (1 hunks, 1 files)
- `pettachainer/metta/runtime/kb_publication.metta`: lines 44-61

## pcmig probe75 (1 hunks, 1 files)
- `pettachainer/metta/runtime/kb_publication.metta`: lines 44-61

## Untagged hunks
- `pettachainer/metta/bootstrap.metta`:33-34 — `(removed) (import_prolog_functions_from_file`
- `pettachainer/metta/compiler/source_lowering.metta`:623-623 — `(removed) (-[semidet]-> (-[semidet]-> KBContext Statement PremiseBundle) KBContext Bool St`
- `pettachainer/metta/compiler/source_lowering.metta`:732-732 — `(removed) (-[det]-> KBContext Statement (List Variable) (-[det]-> STVType STVType STVType)`
- `pettachainer/metta/core/natives.metta`:310-310 — `(removed) !(declare-natives! -[semidet]-> ((context-with-scope Atom (-[semidet]-> Atom $re`
- `pettachainer/metta/lib/natives.pl`:19-37 — `(removed) 'declare-natives!'(Mode,Entries,true).`
- `pettachainer/metta/prolog/context_overlay.pl`:27-27 — `(removed) Goal =.. [Space|Row], call(Goal),`
- `pettachainer/metta/prolog/context_overlay.pl`:48-48 — `(removed) ; Head =.. [Space|Row], assertz(Head) ).`
- `pettachainer/metta/prolog/context_overlay.pl`:56-66 — `(removed) ; Head =.. [Space|Pattern], retractall(Head) ).`
- `pettachainer/metta/prolog/pc_store_access.pl`:1-21 — `% pc_store_access: PeTTaChainer row access routed through the pymetta engine's`
- `pettachainer/metta/prolog/space_store.pl`:7-7 — `(removed) Row =.. [Space|Pattern],`
- `pettachainer/metta/prolog/space_store.pl`:17-17 — `(removed) Term =.. [Space|Row],`
- `pettachainer/metta/prolog/space_store.pl`:36-36 — `(removed) Head =.. [Space|Row],`
- `pettachainer/metta/runtime/evaluator/folds.metta`:77-77 — `(removed) (-[semidet]-> SkeletonValueReader (-[semidet]-> $acc SkFact $acc) SkeletonFilter`
- `pettachainer/metta/runtime/evaluator/folds.metta`:122-122 — `(removed) (-[semidet]-> SkeletonValueReader Number Atom $args (-[semidet]-> $acc SkFact $a`
