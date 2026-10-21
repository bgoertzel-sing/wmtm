# Goal engine on GoalChainer v2 (v0.7)

From v0.7.0-rc1 the goal engine's core (need regulation, legitimacy and ranking) is MesTTo's
[OmegaClaw-GoalChainer](https://github.com/MesTTo/OmegaClaw-GoalChainer) v2. WMTM keeps the layers v2 does not
have. The engine is still log only: everything said in `docs/RUNTIME.md` ("Goal engine") about gates, outputs and the
optional suggestions block still holds. `goal_engine: "native"` switches back to the v0.6 core, and is kept for one
release as the rollback switch.

## What runs where

| Layer | Owner | Code |
|---|---|---|
| Open items from memory: explicit markers, resolved/superseded detection (incl. v0.7 stamp references "the X from Mar03 14:05 is done"), request-history replies, `speaker_map` addressees, the bot's own promises as self-tasks | WMTM | `wmtm/goals/needs.py`, `requests.py` |
| Need levels (unc, comp) from the open items (count, age, salience) | WMTM | `needs.estimate` |
| Per-item candidate actions (ClarifyQuestion, FlagUncertainty, LookUp for factual gaps only, SummarizeStatus, RemindPending, SelfTask), remind/re-ask timing, one proposal per (person, topic) | WMTM | `actions.py`, `engine.prepare_v2` |
| Domain generation, readings, need observations, review-to-proposal mapping | WMTM | `wmtm/goals/v2.py` |
| Need regulation (bands, urgency, predicted reduction), deontic admissibility with proof trees, Pareto / motivational ranking, the propose / hold / escalate / blocked decision | **GoalChainer v2** | separate process: `wmtm/goals/v2_runner.py` in the v2 environment |
| Gates (shadow canary, v2 goal canary, structural check), logs, `latest.json`, display/asked logs, suggestions block | WMTM | `engine.py`, `goal_prompt.py` |

## Per run

1. `prepare_v2`: WMTM extracts open items, need levels and candidates as before.
2. `v2.build_series` generates a v2 domain. v2 declares actions statically, so the domain is generated per run.
   - Goals `settle_open_questions` and `keep_commitments` have priorities from `goal_weights`.
   - Needs `unc` and `comp` use scale [0, 1], band [`goal_targets`, 1] and drive 1. v2's urgency is then exactly v0.6's urge.
   - There is one `gc-action` per candidate. Its label is the action type and its description is the proposal text.
   - The declared effects are facts: `(given (wmtm-effect a message))`.
   - There is one candidate rule per action. It holds when the action's open-item signals are detected.
   - There is one `gc-need-expectation` per action and need. The other need gets 0, because a missing expectation is unknown in v2.
3. Each WMTM legitimacy rule (`legitimacy.RULES`) becomes a deontic norm:
   - `no_git_memory` and `read_only` are strict (`always ... forbidden`).
   - `no_live_change` and `no_push` are defeasible, `(prefer ... permit)`. An explicit approval of that action can defeat them, through `(prefer approved_change ...)`.
   - On an automated turn, `no_autonomous_<effect>` forbids every message, write, live-change, git or push effect: `(and (signal automated_turn) (wmtm-effect ?a E))`.
4. Readings and observations:
   - Each open item is a signal with an attributed reading. Its source is `wmtm:items:<item ids>`, never text, its estimator is `deterministic`, and `observed_at` is the item's last note.
   - `automated_turn` is detected or refuted, and `goal_review` is always detected.
   - The need levels go into a per-run motivation stream (SQLite in the run's scratch dir, deleted after the run) as `observe` records.
5. Expected change of an action is the level gain from closing its items × the geometric mean of WMTM's
   considerations (salience, specificity, fit, age, KB support) × the repeat discount. Two adjustments keep v2 decisive:
   - Exact ties are broken in candidate order.
   - A change that would reach the band is capped just below it, keeping the order. Asking does not close an item, and two actions that both "satisfy" a need would make v2 escalate.
6. One runner process answers the canary series and the main series. On an automated run it runs two passes over the same domain:
   - The `automated` pass is the logged result. Message actions are forbidden in it.
   - The `human` pass gives the display-only message suggestions (Track T).
7. v2 proposes one action per review. The runner then withdraws that action and its (person, topic) group, and
   reviews the rest again with the engine warm (about 0.2 s per review), up to `goal_max_proposals` times. The first
   disposition that is not `propose` ends the pass.
8. Mapping back to WMTM records:
   - `propose` becomes `status: proposed`. `score` is v2's projection (the urgency reduction).
   - The record keeps the same fields as v0.6, plus `engine: goalchainer-v2`, `decision`, `action_id` and `v2`. The `v2` object holds `review_id`, `fingerprint`, `rank`, `decided_at`, `reduction`, `level`, `predicted_level`, `expected_change`, the `proof` (for example `P(do a00_ask_…) <- permit <- cand_… <- (signal (item_…))`), `authority`/`authorization` (always advisory / unresolved), the ranking `steps`, and a one-step `plan`.
   - v2's planner is not used: no procedures are declared, and every WMTM action is a single step.
   - `forbidden` becomes `status: vetoed` with the F-proof and its rule ids. The withdrawn same-topic actions get `status: dup`.
   - `hold`, `escalate` and `blocked` are logged in `runs.jsonl` (`v2.decisions`, `v2.reviews` with the hold needs and escalation reasons) and never shown.

## Gates and failure handling

- If the shadow canary failed, v2 is not started (`shadow_canary_fail`).
- The v2 goal canary runs through the real runtime in the same runner process, with a made-up person and a known answer. A failure gives `canary_fail` and nothing is trusted. It passes when all of these hold:
  - the open question becomes ClarifyQuestion to the right person, as v2's first `propose`;
  - the live-change action is vetoed by v2's norms;
  - the automated pass proposes no message;
  - a note with no open question gives no uncertainty proposal.
- The runner is a separate process group:
  - It runs `<goal_v2_python> -I v2_runner.py` with a minimal environment and its own `RLIMIT_AS` (`goal_v2_mem_mb`).
  - It is killed with SIGKILL of the whole group after `goal_v2_timeout_s`.
  - It inherits the worker's nice/SCHED_IDLE/ionice, which the worker's PriorityGuard keeps re-asserting.
- Failure statuses: `v2_unconfigured`, `v2_timeout`, `v2_crash`, `v2_bad_output`, `v2_error`, `v2_review_error`. Each one means no proposals and an empty `latest.json`, and is recorded in `runs.jsonl`. The outer `goal_budget_s` (SIGALRM, now 90 s) still bounds the whole goal run.

## Flags (flags file; `wmtm/runtime_config.py`)

| Key | Default | Meaning |
|---|---|---|
| `goal_engine` | `v2` | `v2` or `native` (v0.6 core; rollback) |
| `goal_v2_python` | `""` | absolute path of the v2 environment's interpreter (deploy-time only) |
| `goal_v2_release` | `""` | the runtime's release tag, recorded in every `runs.jsonl` line |
| `goal_v2_timeout_s` | 60 | hard kill of the runner |
| `goal_v2_mem_mb` | 1536 | runner address-space cap (a run needs ~130 MB RSS; 768 MB AS is too little) |
| `goal_v2_inferences` | 50000000 | v2 inference budget per request |
| `goal_v2_runner` | `""` | development/test override of the runner script |
| `goal_budget_s` | 90 (was 10) | wall-clock cap of the whole goal run |

## Runtime (installed separately, never vendored)

The runtime is GoalChainer v2 as published, in its own environment outside the bot tree. The pieces and pins are:

- Release `pymetta-native.2`, which targets commit `5c6ecda6a646b8045bebb9080c842f03d3a29def` (branch `goalchainer_v2`).
- The release asset `pymetta-native2-linux-x86_64.tar.gz`, sha256
  `90ae8da8e9fee5cca181b5ddcfa212b73403e572133ec9877484c9f30b8b330c`.
- The wheel directory `pymetta-0.9.4+goalchainer.native.2-f50f8272710b2d56`.
- Submodules: OmegaClaw-Core `1a7624e` and PeTTaChainer `38b1473`.
- CPython 3.12–3.14 (3.13 used). The `dev` extra only; the `semantic` extra (torch) is not needed.

```sh
RT=<runtimes>/goalchainer-v2-pymetta-native.2
git clone --branch pymetta-native.2 --depth 1 --recurse-submodules --shallow-submodules \
  https://github.com/MesTTo/OmegaClaw-GoalChainer.git "$RT/src"
curl -fL -o "$RT/dl/pymetta-native2-linux-x86_64.tar.gz" \
  https://github.com/MesTTo/OmegaClaw-GoalChainer/releases/download/pymetta-native.2/pymetta-native2-linux-x86_64.tar.gz
echo "90ae8da8e9fee5cca181b5ddcfa212b73403e572133ec9877484c9f30b8b330c  $RT/dl/pymetta-native2-linux-x86_64.tar.gz" | sha256sum -c -
tar -xzf "$RT/dl/pymetta-native2-linux-x86_64.tar.gz" -C "$RT/wheels"
cd "$RT/src" && GOALCHAINER_NATIVE_WHEELS="$RT/wheels" uv run --python 3.13 --no-project scripts/native-wheels.py place
uv sync --frozen --python 3.13 --extra dev && .venv/bin/python scripts/native-wheels.py check
```

Then set `goal_v2_python` to `$RT/src/.venv/bin/python` in the bot's flags file. Measured on the development laptop
(niced, synthetic and replay data) per goal run:

- one runner process, about 5.3–5.9 s wall (about 4 s cold engine start, about 0.2 s per further review);
- about 130 MB max RSS;
- about 1 M inferences per review.

## Licensing

GoalChainer's own files are MIT, but the v2 distribution is **GPL-3.0-only AND MIT AND Apache-2.0**, because the
vendored SNARS chaining skeleton is GPLv3. Its pymetta wheels also carry LGPL components. WMTM is published
separately and keeps that boundary:

- WMTM neither vendors nor copies any GoalChainer code. No GoalChainer file is in this repository or in the
  vendored `wmtm-<tag>` distribution.
- WMTM's own interpreter never imports `goal_chainer`. The only v1 imports are the optional, pre-existing v1 bridges,
  and v2 removed those modules.
- v2 runs as a separate program from its own, separately installed environment. WMTM talks to it only over a JSON
  stdin/stdout protocol (`wmtm-gc2-job-v1` / `wmtm-gc2-result-v1`).
- `wmtm/goals/v2_runner.py` is WMTM's own code. It uses only v2's public request API and runs inside the v2
  environment.
- The runtime is fetched at deploy time from MesTTo's GitHub release, pinned by tag and sha256.
- `tests/test_goals_v2.py::test_runner_is_standalone_and_licence_boundary_holds` checks the import boundary.

## Open questions for MesTTo

- Is `pymetta-native.2` a supported distribution, and will release tags stay immutable? The request/review schemas
  are not declared stable yet. WMTM reads `disposition`, `proposal`, `candidates`, `deontic_support`, `steps`,
  `display_order`, `hold`, `escalation` and `blockers`.
- Exact ties escalate ("projection not decisive"). WMTM breaks ties and caps band-reaching expectations before v2
  sees them. Should the domain be able to declare a tie-break preference instead?
- Is there a supported way to ask for the k best admissible actions in one review, instead of re-reviewing with
  withdrawn actions?
- Should the motivation stream persist across runs? WMTM uses one per run, because it reports no host attempts yet.
