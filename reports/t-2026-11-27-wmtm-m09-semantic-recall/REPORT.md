# t-2026-11-27-wmtm-m09-semantic-recall: semantic recall behind a flag (M-09)

## Summary

The order asked for semantic recall behind a flag, with keyword-only fallback: with the flag on, recall should find a cluster that shares meaning but no token with the query, and with it off recall must stay exactly as on main. That is done on wmtm main 915bc8caeb32 (origin/main at 01:42 UTC). The new runtime flag `recall_semantic` is off by default. When it is on, `RecallBridge.recall` fuses its keyword ranking with `embed_index.EmbedIndex.rank` by `embed_index.rrf`. A cluster found only by the embedding ranking must have a cosine above `recall_semantic_min_sim` (default 0.6) and above the relevance floor. If sentence-transformers or the pinned model is missing, or the ranker raises an error, recall is keyword-only and logs this once.

With the flag off, nothing new is imported or called. Neither sentence-transformers, torch nor `wmtm.embed_index` is loaded, and a recall replay gives byte-identical output to main. With the flag on, the model is loaded with the pinned revision and `local_files_only=True`, so it never downloads at run time. sentence-transformers is not installed on this host, so the real-model test is skipped here. Still open: the shadow run that decides whether to turn the flag on (a later task).

## What changed
- `wmtm/recall_bridge.py`: `recall(..., semantic=False, semantic_min_sim=0.6)` and `_semantic_fuse`. The ctor takes an optional `semantic_ranker`, which tests use for a stub. `_default_semantic_ranker()` imports embed_index lazily, and `_log_semantic_fallback` logs once per process. With `semantic=False` the code path is the old one verbatim.
- `wmtm/embed_index.py`: `PINNED_REVISION = 5c38ec7c405ec4b44b94cc5a9bb96e735b38267a` (BAAI/bge-small-en-v1.5, HF commit 2024-02-22). `MODEL_REVISION` can be overridden by `WMTM_EMBED_MODEL_REVISION`. The load uses `revision=MODEL_REVISION, local_files_only=True`.
- `wmtm/runtime_config.py` + README: `recall_semantic` (bool, false) and `recall_semantic_min_sim` (float, 0.6).
- `wmtm/api.py`: `_recall_semantic_kw(cfg)` returns `{}` when the flag is off, so the flag-off call is the pre-M-09 one.
- `pyproject.toml`: extra `embed = ["sentence-transformers==6.3.0"]` (the PyPI release on 2026-11-27), plus a comment on how to install CPU-only torch first.
- `scripts/cache_embed_model.py`: caches the pinned model (snapshot_download at the pinned revision) and then checks that it loads offline. Without the extra installed it exits 1 with a message (checked on this host).
- `tests/test_m09_semantic_recall.py` (11 tests: 10 run here, 1 skipped):
  - Stub flag on: "forgetting" recalls cluster "forgotten items" (no shared token), and the unrelated cluster is not ranked above it.
  - Flag-off twin: same ids and scores as a plain bridge, and the ranker is never called.
  - min_sim gate; active items excluded; a ranker error falls back to keyword-only; an unavailable model gives keyword-only, logged once over 3 recalls.
  - The load passes `local_files_only=True` and the pinned 40-hex revision.
  - `_recall_semantic_kw` returns `{}` when off; the version pin is in pyproject.
  - A subprocess check that a flag-off recall loads none of sentence_transformers, torch, transformers or wmtm.embed_index.
  - Real-model twin: skipped unless sentence-transformers and the cached pinned model are both available.

## Checks
- Flag-off imports: `flag off loaded: []` (after a recall through the api kwargs path). The same check runs as a test.
- Flag-off recall replay: `tools/flagoff_recall_replay.py` (in this folder; run from the repo root with PYTHONPATH=.).
  - Input: the synthetic journal (36 clusters), 300 seeded queries × 2 argument sets (the defaults, and api-style floor 0.1 + turn + add_pct 10), with random residents.
  - Output: 600 recalls, 1870 candidates; ids and scores rounded to 1e-12.
  - The clock is frozen because the recency term reads time.time(). Without that, two runs on base differ.
  - Result: branch == 915bc8c, sha256 5319be33ec56e1a03552ced8b46cd5c79141553094ca5343d5e27400a11c36d0 (2 runs each).
- Full pytest: see the result post for the final counts.

No note text is in the repository: the test clusters are synthetic strings, and the replay prints ids, scores and a hash.
