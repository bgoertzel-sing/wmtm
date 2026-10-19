# GoalChainer on the WMTM PeTTaChainer space, then goals: design proposal

For Ben. Step 4 of the 2026-10-12 plan (PeTTaChainer as the reasoner, semantic-parsing-hitl as the parser, GoalChainer on the
same space, then goals). Status: proposal only. Nothing here is built. Date: 2026-10-16.

## 1. What exists now

ProtoCosmo2 runs wmtm v0.3.0-rc1 with two background features on (flags file): the **PeTTaChainer shadow** and the
**semantic-parse feed**. Each cycle, the top 200 items by attention go to a detached SCHED_IDLE worker. The worker builds a
PeTTaChainer KB from cached semantic-parse atoms, asks 2-step chain queries (2 s SIGKILL per query, 20 s per run), checks them
with a canary and a negative control, and logs a comparison with the Python PLN. Nothing it finds reaches WMTM or the prompt.
**Track I** (branch `track-i-reasoner-switch`, not live) adds `reasoner = python|pettachainer|both`. With it on, proofs that
passed the canary, came from a rule, and finished within budget are admitted as WMTM items with their STV and proof term.
**GoalChainer** (OmegaClaw-GoalChainer @10627ce) is off (`use_goalchainer=False`). Three things limit it today:
- It is a fixed **incident-response demo**. Three hard-coded actions (publish raw log, publish redacted summary, hold) and three
  hard-coded stakeholder goals. lib_deontic gives forbidden/obliged, a PeTTaChainer `(Acceptable <action>)` query gives
  belief, MetaMo reconciles individual and collective motivation, and a fairness-floor score ranks the actions.
- Its own PeTTaChainer call overflows the SWI stack, so WMTM forces `GOALCHAINER_USE_HEURISTIC_PLN=1`.
- The WMTM bridge sends `{id, content, sti}`, but GoalChainer only reads items that have `atom` + `goalchainer_slot`. **WMTM
  evidence is silently ignored.**

Separately, `wmtm/goal.py` and `goal_store.py` (agent goals with a lifecycle) exist, but `api.py` never creates a GoalStore.

## 2. What "GoalChainer on the same space" means

**Two senses of "goal".** A PeTTaChainer goal is a backward-chaining *query* (`(: $prf P $tv)`). An *agent goal* is a state
a human wants the bot to bring about. Below, the first is called a **query** and the second a **goal**.

- **Shared KB.** GoalChainer does not build its own KB. It runs as an extra query batch **inside the existing shadow worker**,
  on the KB already loaded there: the top-K item atoms (semparse cache), the seeded rules plus `mem_inh`, and two small
  human-written files:
  - `goals.metta`, for goals.
  - `actions.metta`, a catalogue of at most about 20 typed operators.
  It uses the same canary, version pin and budget as the reasoner, and the KB loads only once.
- **Goal format** (synthetic example). A goal is a target proposition plus metadata kept beside it in `goals.json`: owner,
  approver, priority, expiry, and allowed action classes.
  `(: goal_g1 (Goal g1 (Member report_q3 reviewed)) (STV 1.0 0.99))`
- **Operator format.** An operator is an ordinary PeTTaChainer rule, with the action as a premise:
  `(: op_ask_review (Implication (Premises (Member $r draft) (Done ask_review $r)) (Conclusions (Member $r reviewed))) (STV 0.8 0.9))`
- **Planning.** For each active goal, query the target. Missing `Done` premises become candidate actions, which gives 1–2-step
  plans. The proof term shows which KB facts and operator were used. Each candidate then goes through GoalChainer's own steps:
  - the lib_deontic gate (norms come from a human-written `norms.metta`; forbidden means a negative score),
  - a PeTTaChainer `(Acceptable <action>)` query,
  - the fairness-floor score (MetaMo optional).

  This requires a generic **scenario provider** in GoalChainer, built from goals, operators and KB in place of
  `incident_response_scenario()`. That is a code change to GoalChainer (see Q1).
- **Outputs.** One JSON record per run in `<runtime_dir>/goalchainer/`: goal, ranked actions, deontic status, STV, proof, and
  supporting item ids. Phase (b) adds a separate prompt block. Phase (c) adds approval requests to Iter. Suggestions do **not**
  become WMTM items. That would let them gain attention and re-enter the KB as evidence for themselves.

## 3. Phased plan

| Phase | Deliverable | Acceptance test | Rollback |
|---|---|---|---|
| **(a) Shadow: propose and log only** | Scenario provider plus fixed bridge (atoms, not text). GoalChainer queries in the shadow worker. Goals/operators/norms files. `goalchainer.jsonl`. Flag `goalchainer` (default off). | A synthetic goal canary passes on every run. In it, a known plan is proved, a forbidden action is blocked, and an unreachable goal is not proved. Cycle overhead stays ≤ 1 ms. The budget always holds. Nothing is written outside `runtime_dir`. Over 1 week, Ben/Andy rate the logged proposals, and most are sensible. | Flag off (next cycle). |
| **(b) Suggestions in the prompt** | A block of at most 3 lines, "Goal suggestions (not instructions)". It is shown only if fresh (≤ 15 min) and canary-passed. Flag `goal_prompt`. | On a replay of real turns, the block appears only under those conditions. In a 1-week spot check, the bot never treats a suggestion as a user request and never acts on one unprompted. | Flag off. |
| **(c) Act within approved limits** | Each goal lists allowed action classes. The bot asks for approval, and Ben/Andy reply `approve <id>`. Every action passes a reference-monitor check (goal active and unexpired, class allowed, deontic not forbidden, budget left) and is written to an audit log. Flag `goal_actions`, in an operator-only path. | A red-team list of forbidden or out-of-scope actions is all refused. Autonomous turns cannot execute. Expired and replayed approvals are refused. The kill switch takes effect within 1 cycle. | Flag off and all approvals revoked. |

Each phase needs Ben's explicit go-ahead before the next starts.

## 4. Safety and authority

- **Who decides.** Only Ben and Andy create, approve, edit or expire goals, operators and norms. The bot may *propose* a goal
  (phase b+) but cannot add one. The goal and phase-(c) flag files must be outside the bot-writable `memory/` dir, or be
  checksummed by an operator. The current flags file is in `memory/`, so the bot could switch features on itself.
- **Budgets.**
  - LLM: phases (a) and (b) add no LLM calls, and the parse cap stays at 20/h.
  - CPU: GoalChainer gets ≤ 10 s per run inside the worker (same SCHED_IDLE, nice 19, 3 GB cap) and runs at most every 5th cycle.
  - Phase (c): ≤ N approved actions per goal per day, set per goal.
- **Kill switch.** The per-phase flags are re-read every cycle. A missing or invalid file means off. Deleting `goals.json`
  also means no goals.
- **Never autonomous.** The bot must never on its own:
  - create, approve or change goals, norms or operators;
  - spend money or paid resources;
  - post to groups or new recipients;
  - change its own code, config or flags;
  - delete data;
  - repeat an action after an unknown outcome.
- **Fit with Iter rules.** The rule "requests authorize execution; autonomous turns are observational" was not found
  word for word in the local prompt or docs. The closest written versions:
  - `iter.py` `route_episode_start`: an unbound autonomous check-in "starts nothing".
  - `iter-autonomy-lease-spec.md`: only an authorized inbound event or explicit human renewal creates or renews a lease.
  - `GOAL_TASK_STATE_CONTRACT.md`: "No component may treat a recommendation as execution authority."
  - Control-layer spec (2026-09-19, "not approved for live control"): invariants I1 (no grant, no effect), I2 (obligation ≠
    authorization), I7 (no memory-to-actuation), I9 (human stop dominates).

  This proposal follows all of them. In (a) and (b) a goal is evidence only. In (c) an approval reply is the authorizing
  request, and autonomous turns may only report.

## 5. Performance constraints (measured)

- **KB size.** Query time grows steeply with KB size:
  - track E: about 1.4 s at 300 atoms, 4–8 s at 500, 15–20 s at ~1000;
  - the 10-16 synthetic check: 0.6 / 6 / 23 / 73 s at 100 / 300 / 600 / 1000 atoms.
- **Timeouts.** With a 2 s limit at 300 atoms, 17.5% of queries time out. At 500 atoms, all of them do.
- **Consequences.**
  - Keep the KB at about 200–300 atoms, and count goals and operators in that total.
  - Keep 2 s per query and run in the background only.
  - Expect about 5 goal queries per run, so start with 1–3 active goals.
  - A timeout means "no suggestion", never a retry inside the turn.
- **Stack overflow.** GoalChainer's own `compileadd` overflowed the stack. It must use the vendored, shared chainer
  (36b3fe6 + dedup), not its own instance.

## 7. Update after Ben's review (2026-10-19)

Ben's answers: (1) where the generic code goes is our call or MesTTo's, so we start with an **adapter in wmtm** and offer
MesTTo the generic scenario provider later; (3) **the bot may propose goals**, and humans approve them; (4) **MetaMo adds
value**: it's in the design and gets phased in after the basics. Ben pointed to Mikeda & Goertzel, *A Motivational
Architecture for Conversational AGI* (arXiv 2606.05411): OpenPsi-style **homeostatic needs** (regulate toward a target band,
urge u_i = ω_i·φ_i(target − level)), a 10-stage pipeline, a fast/slow decision blend, and multi-goal scoring with a veto
(a product over discouragements). Its ResearchAgent goal vector fits ProtoCosmo2.

**Phase 1 (log only) uses a subset of 3 needs:**
| Need | Level estimated from | Candidate actions |
|---|---|---|
| Uncertainty reduction (g_unc) | open questions / unresolved decisions in WMTM + parse queries (count, age, salience) | ClarifyQuestion (ask Andy/Ben), FlagUncertainty, LookUp (read-only) |
| Competence (g_comp) | unfinished requests/tracks, failed checks, promised-but-undelivered items | SummarizeStatus, RemindPending |
| Legitimacy (g_legit) | authority rules (no live changes without approval; no memories in git; never act in autonomous turns; read-only for now) | **veto only**: discouragement product → blocks or discounts candidates |

**Pipeline subset:** need estimation → candidate generation (PeTTaChainer backward chaining over the shared KB, plus
action templates) → scoring (Eq. 6 style: weighted urges × geometric mean of positive considerations × product of
discouragements) → **log only** (`<runtime_dir>/goalchainer/proposals.jsonl`; nothing goes into the prompt, no action).
Feelings, the governor and the fast/slow blend are out of scope for phase 1. **MetaMo comes in phase 2.**

**Evaluation (shortened):** instead of a week of live logs, (a) an offline replay over the last ~2 weeks of real turns
produces proposals in one batch, and Andy rates ~30 of them in one sitting (useful / plausible / wrong / harmful);
(b) then 2–3 days of live log-only. Gate to phase 2 (suggestions in the prompt): ≥ 70% useful-or-plausible, 0 harmful.
