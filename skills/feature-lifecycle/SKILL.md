---
name: feature-lifecycle
description: "Running a single high-stakes feature end to end — autonomous goal discovery, demand research, verdict, spec with traceable acceptance criteria, parallel tech/UX design, a four-axis risk gate, a bounded implementation loop, independent acceptance verification, and ship. Use when a feature is customer-facing, cross-team, expensive to reverse, and its acceptance criteria must be derived rather than supplied. Don't use for a defect in shipped behavior, a bounded single build whose shape is settled, spec-only work with no code, or a multi-package plan."
---

<!--
CAPABILITIES_SUMMARY:
- goal_discovery: Autonomous scan → propose → prioritize → select a single highest-value goal with evidence refs and rejected alternatives
- lifecycle_orchestration: Phase 0-6 + Ship chain with a typed artifact and an exit gate at every boundary
- parallel_design: Tech track (architecture / API / schema) and UX track (sub-orchestrated where a UX orchestrator exists) run concurrently and reconverge at one gate
- four_axis_risk_gate: FMEA + blast radius + UX friction & a11y + security and data exposure as a single go/no-go before any code is written
- bounded_implementation_loop: Delegated loop with a declared iteration cap, convergence detection, cost-per-task tracking, and a circuit breaker
- acceptance_verification: Independent conformance pass plus a negative pass proving nothing outside the declared scope was built
- checkpoint_resume: Every phase boundary persisted so an aborted run resumes instead of restarting
- budget_envelope: Pre-declared run-level ceiling with an 80% warning and a hard stop that checkpoints rather than overruns
- no_hard_dependencies: Every roster row is work the chain owns — an installed specialist is delegated to, an absent one is performed by the chain against the identical gate
- tri_engine_roster: build / judge / breadth bound to Codex CLI, Claude Code and agy, probed once per run, with the acceptance verification pinned off the engine that built

COLLABORATION_PATTERNS:
- Pattern A: An upstream spec or reproduction packet → Feature Lifecycle (collapses the phases it already settled)
- Pattern B: Feature Lifecycle → a UX sub-orchestration brief, Feature Lifecycle → an implementation loop contract
- Pattern C: Feature Lifecycle → a performance-tuning residual (perf ACs unmet inside the envelope, with target and budget)
- Pattern D: An orchestrator → Feature Lifecycle (a routing envelope); Feature Lifecycle returns its handoff to the caller, never a direct agent-to-agent call

BIDIRECTIONAL_PARTNERS:
- INPUT: A spec authoring upstream (Spec Handoff Packet), a faithful-reproduction upstream (Clone Handoff Packet), an orchestrator (routing), User (goal or no-args)
- OUTPUT: A UX brief, a loop contract, an AC set + scope boundary to verify against, a PR, a release plan, a residual perf target, a stuck-loop diagnosis

PROJECT_AFFINITY: SaaS(H) E-commerce(H) Dashboard(H) Game(M) Marketing(M)
-->

# Feature Lifecycle

> **"Discover what is worth building, prove it is what got built, then ship it."**

Feature Lifecycle runs one high-stakes feature from an unstated need to a released change. It owns the phase chain, the gates between phases, and the budget the whole run is scored against; each roster row owns its work product. Scope per invocation: **one** feature. A multi-package plan is not a run.

Feature Lifecycle is **self-contained**: it needs no hub, and no external contract directory, to run. Every rule it depends on is in `reference/contracts.md`. Invoked directly it owns the whole chain end to end; invoked from an orchestrator it behaves as a sub-orchestrator and returns a handoff (§ Orchestrator Sub-Mode).

**Every roster row is work the chain owns, never a skill it requires.** Rosters are written in the chain's own vocabulary; `reference/delegation-map.md` is the single place a skill it does not own is named, and it is an optimization. Where a specialist is installed, delegate to it; where it is not, the chain performs that row itself against the identical exit gate. A missing specialist changes who does the work, never whether the gate is passed, what artifact the phase emits, or what the report claims.

**Principles:** Every phase emits a typed artifact · Every boundary has an exit gate · Design work runs parallel and reconverges once · The verifier shares neither context nor engine with the builder, or names which of the two it lacked · Convergence is not correctness · No silent partial ship

## Trigger Guidance

Use The chain when the request matches **at least 3** of:

- New customer-facing feature with a UI surface (not a backend-only fix)
- Cross-team impact (business + engineering + design)
- Reversibility cost is high — DB migration, API contract change, brand-visible UX
- Acceptance criteria are not pre-supplied and must be derived from user need
- An architecture decision is required, not just an implementation
- 5+ files / 2+ modules / 2+ days estimated

Route elsewhere when the task is primarily:
- A defect in shipped behavior — diagnose and fix, no discovery chain
- One bounded capability whose shape is already settled — a single guided build
- Spec and acceptance criteria only, no code
- Decomposition and sequencing only, no execution
- Design exploration without implementation
- Executing a pre-authored multi-package plan across several deliverables
- A behavior-preserving rewrite or port, where the oracle is the old behavior
- Improving one already-correct slow layer against a number

**Feature Lifecycle is opt-in, never a default.** It is for the case where an upstream gap — a missed user need, a weak spec, a hidden architecture risk, UX friction — is materially costly to discover after implementation. When that is not true, a lighter chain is the correct chain.

## Core Contract

- **Owned responsibility is the lifecycle control plane:** discover → ideate → decide → specify → design + gate → build → verify → ship. The chain sequences, scopes, gates, and aggregates; it never authors a specialist's work product.
- **Hub-and-spoke.** The chain is the top-level orchestrator for its run. `ux-direction` and the loop driver become sub-orchestrators where a skill is installed for them, and fold into the chain where none is. Direct agent-to-agent handoff across hubs is forbidden — everything crosses through the owning hub.
- **Every phase boundary is a gate.** A phase advances only on its declared exit criterion; a failed gate returns to the *originating* phase, never forward with a note.
- **The acceptance verification is independent and two-sided.** Conformance (every must-have AC met) *and* a negative pass (nothing outside the declared scope was built). It runs on the `judge` engine, which is never the engine that built wherever a second engine is reachable; on a single-engine workspace its independence is `context-only` and is reported as such (`reference/engine-roster.md`).
- **Three engine roles, probed once.** `build` (Codex CLI), `judge` (Claude Code), and `breadth` (agy) are bound at launch and recorded before the first spawn. A role is a property of the work; a missing engine rebinds the role and is reported, never worked around.
- **Bounded everywhere.** Implementation loop `≤ 6` cycles; acceptance-gap re-entry `≤ 2`; run-level budget ceiling is a hard stop that checkpoints, not a warning.
- **Consume upstream packets; never re-derive them.** A `spec` or `clone` packet collapses re-derivation, never verification → `reference/input-contracts.md`.
- **One human checkpoint in autonomous mode** — the Phase 0 boundary confirm. Downstream, only an internal gate, a circuit breaker, or the budget ceiling stops the run.
- **Every document is written to the Document Contract** (`reference/contracts.md` §9): ambiguity driven to zero first, then redundancy cut to nothing — one fact one home, no narration, no padding — with the scope bound, a number's source, a claim's status label and a rejected option's reason never compressed away.
- Output language follows the CLI global config; identifiers, protocol markers, and schema keys stay English.

## Boundaries

Overlap with neighbouring roles → § Overlap Boundaries below. Operating rules the chain carries with it → `reference/contracts.md`.

### Always

- Run the five-point loop precondition gate (`reference/contracts.md` §2) before entering the implementation loop, and report its verdict in the Delivery Report.
- Run the loop-driver availability gate (`reference/contracts.md` §4) before selecting the driver; on the fallback path record `project_local_fallback: true`.
- Probe the three engines once before the first spawn and record the resolved roster, its rebindings, and `engine_independence` in the Delivery Report (`reference/engine-roster.md`).
- Run a reuse scan in Phase 1 on any existing repository — building a second implementation of something the repo already ships is a Phase 1 failure, not a Phase 6 one.
- Open the run record before the first spawn, and seal each phase's document in the same step that records its gate verdict — outcome, findings, rejected options, and the gate's measured terms (`reference/run-record.md`). A gate verdict recorded against an unsealed document is not recorded.
- Persist every phase-boundary artifact as a resumable checkpoint (`reference/delivery-report.md` § Cross-Phase Checkpoint-Resume; on-disk shape → `reference/run-record.md`).
- Author a **measurement contract** in Phase 4 for the demand the feature was derived from, and carry it to Ship as a `hypothesis-open` residual. The chain never marks it closed — it cannot read the outcome.
- Rehearse the rollback at Ship. A plan that was never run is `E0`; `declared-impossible(reason)` is a legitimate outcome and a different one from never attempted.
- Declare the budget envelope at launch and track cumulative spend against it.
- Emit the Delivery Report on **every** exit, including aborts — best-so-far per phase, the residual gap, and the resume point.
- Check/log to `.agents/PROJECT.md`.

### Ask First

- **Confirm before launch** — the Phase 0 boundary confirm in autonomous mode, and any run whose estimated envelope exceeds the user's stated ceiling.
- **Engine unavailable at the Phase 5 → 6 handoff** — present the degradation choice with its restated cost model; never pick a runner on the user's behalf.
- Any out-of-boundary change the negative pass surfaces that the user may want to ratify rather than revert.
- L4 security triggers, destructive data actions, and external system changes inside the loop.

### Never

- Ship with an unmet must-have AC, or with an unratified scope violation. A loop that satisfies every AC *and* grew a surface nobody asked for is a failed run reported as a success.
- Treat loop convergence as correctness. The loop passing its own tests says nothing about whether it built what the spec required.
- Silently rebind an engine role or swap the loop runner. The cost and convergence model is scored against a named roster; a silent swap invalidates the envelope the run was authorized against.
- Ship a hypothesis with no way to settle it, or report a `hypothesis-open` residual as a closed one. Conformance to a spec says nothing about whether the demand behind it was real.
- Report a one-engine run as a three-engine one. A `deliberation` seat with no distinct engine behind it is a simulated voice and is listed as one; an acceptance verification with no model independence is `context-only`, not `model`.
- Re-litigate a settled upstream direction. An unbuildable must-have AC returns to the spec owner; it is never reinterpreted locally.
- Relax a gate because a packet arrived from upstream. Upstream removes re-derivation, never verification.
- Run open-ended. No unbounded loop, no advisory-only ceiling, no "one more iteration".

## Modes

**Default mode:** `AUTORUN_FULL`. In the AUTORUN modes, act without asking except where an **Ask First** gate or the boundary confirm requires it.

| Mode | Behavior at the Phase 0 boundary confirm |
|------|------------------------------------------|
| `INTERACTIVE` | Always confirm; the user may edit the goal before proceeding |
| `GUIDED` | Always confirm; the user approves or aborts |
| `AUTORUN` | Confirm with an explicit Y/N; **defaults to abort** on no response |
| `AUTORUN_FULL` | Show the goal with rationale, wait 60s for objection, then proceed. Any input inside the window aborts and re-runs Phase 0 with the objection as a hint |

The boundary confirm is the **Confirm-before-launch** tier: a launch gate on an expensive chain, not a deliverable checkpoint. Once approved, no further confirmation is required unless the Risk Gate, the loop circuit breaker, the engine-availability check, or the budget ceiling fires.

## Recipes

| Recipe | Subcommand | Default? | When to Use | Read First |
|--------|-----------|---------|-------------|------------|
| Goal-supplied run | `run` | ✓ | A feature description is supplied; start at Phase 1 | `reference/phase-contracts.md` |
| Autonomous run | `bootstrap` | | No goal supplied; discover the highest-value goal first | `reference/phase-contracts.md` § Phase 0 |
| Resume | `resume` | | A prior run aborted at a phase boundary and its checkpoint exists | `reference/delivery-report.md` § Cross-Phase Checkpoint-Resume |

## Subcommand Dispatch

Parse the first token of user input.
- Matches a Recipe Subcommand above → activate that Recipe; load only its "Read First" file at the initial step.
- **`auto`, `goal=auto`, or a bare `feature-lifecycle` with no goal** → `bootstrap`; run Phase 0. This is the documented no-args behavior, not a missing argument.
- **A bare invocation with a resumable checkpoint present** (a `RUN.md` under `.agents/feature-lifecycle/runs/` whose status is not `shipped` → `reference/run-record.md`) → name the checkpoint and ask which: `resume` it, or start a fresh `bootstrap`. Never pick one silently — resuming the wrong run and re-deriving a finished one cost the same as each other's mistake.
- Otherwise → default Recipe (`run`) with the input as the goal description.

Behavior notes per Recipe:
- `run`: Phase 1 → 6 → Ship with the supplied goal bound as Phase 1 input. Optional args: `scope=Lite|Standard|Full`, `ui=`, `api_change=`, `db_change=`, `budget=`.
- `bootstrap`: Phase 0 (scan → propose → prioritize → select → confirm) emits `auto_selected_goal`, then the `run` chain verbatim. `auto` and `goal=auto` are accepted aliases.
- `resume`: read the last good phase checkpoint, re-bind its artifact, and continue from the next phase. Never restarts from Phase 1.

## Workflow

`P0_BOOTSTRAP? → P1_DISCOVER → P2_IDEATE → P3_VERDICT → P4_SPEC → P5_DESIGN+GATE → P6_LOOP → VERIFY → SHIP`

| Phase | Focus | Exit gate |
|-------|-------|-----------|
| `P0_BOOTSTRAP` | Scan project + real signals, propose 3-5 goals, score, select one, confirm | A single `auto_selected_goal` with evidence refs and rejected alternatives, boundary-confirmed |
| `P1_DISCOVER` | Synthetic demands across personas + evidence anchor + friction baseline + reuse scan | Top-3 demands each carry a persona rationale and an evidence anchor |
| `P2_IDEATE` | Diamond thinking (expand → propose → evaluate → subtract) | ≥2 comparable decision candidates |
| `P3_VERDICT` | Tri-engine deliberation → chosen option + AC seed | Verdict carries option, AC seed, scope boundary, failure conditions; a split escalates |
| `P4_SPEC` | L0 vision → L1 requirements → L2 detail → L3 acceptance criteria + traceability + the measurement contract | Traceability ≥ scope threshold; L3 ACs measurable and loop-consumable |
| `P5_DESIGN+GATE` | Tech track ‖ UX track, reconverging at the four-axis Risk Gate | `blast_radius.verdict ∈ {Go, Conditional-Go} ∧ failure_modes.high_rpn_count == 0 ∧ friction.gate_pass ∧ security.unmitigated_high == 0` |
| `P6_LOOP` | Bounded implementation loop under the selected driver and engine | Convergence, cap-reached, or circuit breaker — never an unbounded run |
| `VERIFY` | Independent conformance pass + negative scope pass + a conditional integration-evidence pass | `conformance ≥ threshold ∧ unmet_must_haves == 0 ∧ non_goal_violations == 0`, with `integration_evidence` recorded |
| `SHIP` | Commit policy + PR, release plan + CHANGELOG + rollback, then rehearsing the rollback | Delivery Report emitted, and `rollback_verified ∈ {true, declared-impossible(reason)}` |

Rosters, conditional rows and the chain template are `reference/phase-contracts.md`; P6 and VERIFY are `reference/loop-engine.md`; SHIP is `reference/delivery-report.md`. This skill never restates a roster in two places, and every exit gate above is also the seal point for that phase's document in the run record (`reference/run-record.md`).

## Execution Model

**Detect the hub engine once, before the first spawn** — `Agent` → Claude Code; `spawn_agent` → Codex CLI; `/agent` in a TUI main session → agy. Bind the spawn API and model map per `reference/contracts.md` §5. The hub owns sequencing, gates, checkpoints, the budget ledger, and the Delivery Report, and delegates none of them.

**Then probe all three CLIs and resolve the engine roster** → `reference/engine-roster.md`. The chain runs against three roles, not one engine:

| Role | Chosen for | Default CLI |
|------|-----------|-------------|
| `build` | Tool-heavy edit loops | Codex CLI |
| `judge` | Adversarial reading against a stated contract | Claude Code |
| `breadth` | Wide sweeps, long context, multimodal | agy |

Which row runs on which role is `reference/engine-roster.md` § Phase → Role Map — the one copy, so there is nothing to drift against.

A role whose CLI **is** the hub uses the native spawn API; a role whose CLI is not uses the headless invocation contract of `reference/engine-roster.md`. A cross-engine spawn is a subprocess joined by the hub, never a direct agent-to-agent handoff.

**Fewer than three reachable is a supported run, not a failed one.** The missing role folds by the fallback order and the run records the degradation. Two rules survive it: the acceptance verification never runs on the engine that built **wherever a second engine is reachable**, and no gate threshold moves because an engine was missing — the single-engine case reports `engine_independence: context-only` rather than implying an independence it did not have (`reference/engine-roster.md` § Degradation).

**Phase 6 crosses an engine boundary** to whichever CLI resolved to `build`. The availability check and the degradation protocol are in `reference/loop-engine.md`; a silent fallback is forbidden.

**Spawn prompt non-negotiables** — front-load the phase's acceptance criteria, the output envelope, the scope bound (the spec's `non_goals` verbatim), the completion bound, prohibited outcomes, and least-authority `Authority` with `redelegation: false`. Never ask a producer to verify its own output; verification is a separate spawn with no shared context.

> **MANDATORY before spawning agy or codex as an agent** — read `reference/contracts.md` § Silent-output regressions: agy headless MUST allocate a real pty (bare `agy -p` fails silently, so capture via artifact/sentinel, never stdout), and codex `-o <abs path>` is the authoritative artifact. These are silent-output regressions, not edge cases.

## Sub-Orchestration

| Hub | Engine | Roster | Cap |
|-----|--------|--------|-----|
| **Feature Lifecycle** (top) | hub, fanning out to all three roles | Phase 0-5 + Ship → `reference/phase-contracts.md` | ≤11 concurrent; phases serialise the rest, and the acceptance verification then `commit-and-pr` then `release-plan` run sequentially at the tail |
| **UX** (sub, where installed) | `breadth` | The Phase 5 UX rows there | ≤9, parallelisable inside |
| **Loop driver** (build sub, where installed) | `build` to implement, `judge` to check | In-loop → `reference/loop-engine.md` | ≤7 — the roster's rows excluding the driver. An eighth is a cap decision, not a roster edit |

Two tiers keep every hub at ≤11 with a real merge surface each. The chain adds a sub-orchestrator only when it owns a distinct merge surface — never a role-name-only supervisor. Where neither sub-orchestrator's skill is installed, the topology flattens to one tier and every cap, merge surface, and gate is unchanged.

## Gates

| Gate | Fires at | Passing condition | On failure |
|------|----------|-------------------|------------|
| **Boundary confirm** | Phase 0 exit (autonomous only) | Per the Modes table | Abort; re-run Phase 0 with the objection as a hint |
| **Verdict gate** | Phase 3 exit | A non-split verdict with an AC seed and a scope boundary | 1-1-1 split → human verdict, then re-enter Phase 3 |
| **Traceability gate** | Phase 4 exit | Full ≥95% / Standard ≥85% / Lite ≥70% | Re-run the spec with a scope downgrade or refined inputs |
| **Risk Gate** | Phase 5 exit | `blast_radius.verdict ∈ {Go, Conditional-Go} ∧ failure_modes.high_rpn_count == 0 ∧ friction.gate_pass ∧ security.unmitigated_high == 0` | No-Go → the originating phase (4, or the failing Phase 5 track) |
| **Demand↔reaction closure** | Phase 5, inside the Risk Gate | The walkthrough reaction does not diverge fatally from the predicted demand | Return to Phase 4 for re-spec — even when every axis nominally passes |
| **Engine roster** | Before the first spawn | All three CLIs probed and every role bound, with any rebinding recorded | Fold by fallback order and record the degradation; never proceed on an unrecorded roster |
| **Engine availability** | Phase 5 → 6 handoff | `build` answers a spawn, `judge` reachable **and a different CLI from `build`** where a second CLI exists, `agents.max_depth ≥ 2`, subagent tools permitted | Degradation protocol — a confirmed choice, never a silent fallback. One reachable CLI records `context-only` and proceeds; it never blocks the run |
| **Loop precondition** | Before Phase 6 | The five points of `reference/contracts.md` §2 | Do not enter the loop; report which point failed |
| **Acceptance verification** | Phase 6 → Ship | `conformance ≥ threshold ∧ unmet_must_haves == 0 ∧ non_goal_violations == 0` | Re-enter Phase 6 with the gap list, ≤2 times, then escalate |
| **Ship gate** | Ship exit | `rollback_verified ∈ {true, declared-impossible(reason)}`, and the Delivery Report emitted | Do not open the PR; rehearse, or record the reason the rehearsal is impossible |
| **Budget ceiling** | Continuously | Cumulative spend < ceiling | Hard stop with a resumable checkpoint; warn at 80% |

## Termination Bounds and Cost

Implementation loop `≤ 6` cycles by default, keyed to the `build` engine (`reference/loop-engine.md` § Termination Bounds); acceptance-gap re-entry `≤ 2`, then the user decides. On any non-`ACCEPT` exit the Delivery Report states which acceptance criteria remain unmet and the residual gap — the chain never ships a silent partial. Exit reasons → `reference/loop-engine.md` § Termination Bounds.

Cost runs 11-13 agents (Lite) / 17-22 (Standard) / 23-30 (Full), plus 4-8 for Phase 0, plus loop iterations — 27-61 spawns at the Full autonomous profile. The chain is not free; the run-level budget envelope, the loop's cost-per-task breaker, and the Ask First gates are what bound it → `reference/delivery-report.md` § Cost Profile. For repeated similar requests, propose a project-local skill to amortise the chain design cost instead of re-running the chain.

## Gotchas

- **A loop that converges is not a loop that is correct.** It can stop on an implementation that passes its own tests and misses the spec entirely. Gate Ship on the independent acceptance verification, never on the loop's exit reason.
- **Conformance alone is a one-sided test.** An implementation can satisfy every AC *and* have grown a surface, dependency or table nobody specified — from inside a loop, "add a little more" always looks like progress. The negative pass is what makes the scope boundary load-bearing.
- **An upstream packet collapses derivation, not verification.** Arriving from `spec` makes Phases 1-4 validation; it does not lighten the Risk Gate or the verification. The two common wastes are re-running discovery over a settled spec, and reading the packet as a gate exemption.
- **Three seats on one model is not a tri-engine verdict.** Phase 3's cost is justified by three engines actually disagreeing; one model arguing with itself converges on its own priors and returns a confident split that means nothing. Fewer than three reachable → the simulated voices are listed as such.
- **Every gate points forward.** Four risk axes and a two-sided verification stand between the run and a merge; until the rollback is rehearsed, nothing stands between it and a bad merge it cannot undo.
- **Conformance is not validity.** The verification proves the spec was built; it is silent on whether the demand behind it existed. A run can pass every gate and be wrong in the only sense Phase 0 cared about — which is why the measurement contract leaves the run open.
- **A silent runner swap invalidates the run's cost figures.** Ceilings and envelopes are scored against one named engine. Surface the choice with a restated model and record the runner — a fallback nobody was told about produces numbers read against the wrong model.
- **Hard-failing the Phase 5 → 6 handoff throws away five completed phases.** The abort option is a *checkpointed* resume at Phase 6, not a restart.
- **A clone's declared parity ceiling is a constraint, not a defect.** A loop given a parity harness will happily "fix" a ceiling-bound behavior and move the product off its baseline. Ceilings are inputs to the loop contract.
- **Phase 1 on an existing repo means a reuse scan first.** A second implementation of something the repo already ships is discovered in Phase 1 for the cost of a scan, or in Phase 6 for the cost of the whole loop.

## Lifecycle

- **Failure:** a high-stakes feature shipped against the wrong need, an unmeasurable spec, an unexamined blast radius, or a loop that converged on something the spec never asked for — each of which is cheap to catch upstream and expensive to catch after release.
- **Effect:** every phase boundary emits a typed artifact and passes a named gate; the ship decision is bound to an independent two-sided acceptance verification. It does **not** cover multi-package delivery, behavior-preserving rewrites, or post-release operation — each routes to the capability that owns it, and the chain reports the residual where none is installed.
- **Owner:** the chain (this skill); whatever routing surface reaches it owns the routing.
- **Removal:** delete or merge when the lighter build paths carry an equivalent risk gate and acceptance verification, making the heavyweight chain redundant rather than opt-in.

## Output Requirements

A complete run carries the following — a ceiling, not a floor. Emit only what the run exercised; never pad with `N/A`:

- The **Feature Lifecycle Delivery Report**, carrying every section of `reference/delivery-report.md` § The Feature Lifecycle Delivery Report — discovery summary · spec & AC with traceability % · design decisions · the four-axis Risk-Gate verdict · engine roster · loop record · AC-verify · upstream packet · follow-ups · measurement contract · ship status. Field-level content is that table's, not restated here.
- Acceptance Provenance, the Decision Ledger, and the Residual Ledger with a class per leftover, plus the completion-sweep line and the resumable checkpoint on any non-ship exit
- The **run-record path** (`.agents/feature-lifecycle/runs/<run-id>/`) and `run_record_committed`, so the phase documents behind every number above can be opened (`reference/run-record.md`)
- Output language follows the CLI global config (`settings.json` `language` field, `CLAUDE.md`, `AGENTS.md`, or `GEMINI.md`). Code, identifiers, file paths, CLI commands, and technical terms remain in English.

## Collaboration

The chain receives a goal, or an upstream handoff packet. It sends a UX brief to the UX track, a loop contract to the loop driver, and a PR plus a release plan at Ship. Every counterparty below is a **capability**, not a skill that must exist — where one is absent, the chain does the work and reports the residual (`reference/delegation-map.md`).

| Direction | Handoff | Purpose |
|-----------|---------|---------|
| Spec authoring → Feature Lifecycle | `SPEC_HANDOFF_PACKET` | ACs, non-goals, assumption ledger, refutation flags, reuse findings |
| Faithful reproduction → Feature Lifecycle | `CLONE_HANDOFF_PACKET` | Stack decision record, parity ceilings, parity harness, coverage gaps |
| Feature Lifecycle → UX track | `FEATURE_LIFECYCLE_TO_UX` | Creative direction brief + the UX slice of the spec |
| Feature Lifecycle → Loop driver | `FEATURE_LIFECYCLE_TO_LOOP` | Loop contract: L3 ACs + mitigations + friction signals + the declared cap |
| Feature Lifecycle → Acceptance verification | `FEATURE_LIFECYCLE_TO_VERIFY` | The AC set and the scope boundary to verify against |
| Feature Lifecycle → Performance tuning | `FEATURE_LIFECYCLE_TO_PERF` | A perf AC left unmet inside the envelope, with its target and budget |
| Feature Lifecycle → User | `FEATURE_LIFECYCLE_COMPLETE` | Delivery Report + ship status |

### Overlap Boundaries

| Neighbouring capability | The chain owns | They own |
|-------------------------|-----------|----------|
| Intent routing | The full-lifecycle chain for one feature, its gates, and its budget | General intent routing and every other chain shape |
| Spec authoring | Consuming the spec and binding its L3 ACs to a gate | Authoring the spec, the traceability, and the AC wording |
| UX orchestration | Whether UX passes the Risk Gate | How the UX is designed and which UX rows run |
| Loop running | The loop contract, the cap, and the ship gate | Loop mechanics, runner scripts, convergence detection, recovery |
| Acceptance verification | When it runs, on which engine, and what blocks on it | The conformance judgment and the traceability matrix |
| Multi-package planning | Sequencing phases inside one feature | Decomposing work across features and packages |

Each row is a boundary, not a dependency: where the neighbouring capability is not installed, the chain performs it and the boundary describes what it must not let bleed into its own scope.

## Reference Map

| File | Read this when... |
|------|-------------------|
| `reference/phase-contracts.md` | You need a phase roster, its conditional agents, its exit gate, or the chain template |
| `reference/delegation-map.md` | You want to know whether a specialist exists for a roster row — never needed to run one |
| `reference/engine-roster.md` | Before the first spawn, at the Phase 3 verdict, at the Phase 5 → 6 handoff, or before the acceptance verification |
| `reference/loop-engine.md` | You are at the Phase 5 → 6 handoff, inside the loop, or at the acceptance verification |
| `reference/run-record.md` | You are launching, sealing a phase at its gate, resuming, or deciding whether something belongs in the record, the journal, or the report |
| `reference/input-contracts.md` | An upstream packet arrived, or you must decide what a bare invocation re-derives |
| `reference/delivery-report.md` | You are emitting output, sizing the budget envelope, resuming, or classifying a failure |
| `reference/contracts.md` | Any operating rule the chain depends on — precedence, the loop precondition gate, the evidence ladder, driver availability, the spawn contract, the Work Gate, handoff envelopes, the run record and journal, how every document is written, and Git conventions |

## Operational

**Run record** (`.agents/feature-lifecycle/runs/<run-id>/`): this run's analysis — a sealed document per phase carrying outcome, findings, rejected options and the gate's measured terms, plus the artifacts that outlive their phase. Opened before the first spawn, committed with the change it describes → `reference/run-record.md`.

**Journal** (`.agents/feature-lifecycle.md`): Record only lifecycle-chain learnings — which gate caught what, where a phase's estimate diverged from its actual cost, and which upstream packet collapsed which phases. Not a run log; this run's material goes in the run record instead.

- Activity log: append `| YYYY-MM-DD | Feature Lifecycle | (action) | (files) | (outcome) |` to `.agents/PROJECT.md`.

**Operating contracts** — in effect on every run, precedence in `reference/contracts.md` §1: the loop precondition gate (§2), the evidence ladder (§3), the driver availability gate (§4), the spawn contract (§5), the Work Gate (§6), handoff envelopes (§7), the run record, journal and activity log (§8), the Document Contract (§9), and Git conventions (§10). When the chain runs inside a repository that ships its own `_common/` protocol set, those originals outrank this file.

Emit `WORK_GATE` (`reference/contracts.md` §6) alongside the Delivery Report.

## AUTORUN Support

When Feature Lifecycle receives `_AGENT_CONTEXT`, parse `task_type`, `description`, and `Constraints`, run the standard chain (skip verbose explanations, focus on deliverables), and return `_STEP_COMPLETE`.

### `_STEP_COMPLETE`

```yaml
_STEP_COMPLETE:
  Agent: Feature Lifecycle
  Status: SUCCESS | PARTIAL | BLOCKED | FAILED
  Output:
    deliverable: "Feature Lifecycle Delivery Report"
    artifact_type: "feature-lifecycle-run"
    parameters:
      goal: "[the feature shipped or attempted]"
      phases_run: "[e.g. 0-6 + Ship, or 4-6 when a spec packet collapsed 1-3]"
      runner: "codex | claude-code | agy"
      engine_roster: "build/judge/breadth CLIs, engine_independence: model | context-only"
      risk_gate: "Go | Conditional-Go | No-Go (four axes)"
      rollback_verified: "true | declared-impossible(reason)"
      conformance: "[percent] / unmet_must_haves: [n] / non_goal_violations: [n]"
      budget: "[spent] of [ceiling]"
  Validations:
    completeness: "complete | partial | blocked"
    quality_check: "passed | flagged | skipped"
  Next: [NextAgent] | DONE
  Reason: [Why this next step]
```

## Orchestrator Sub-Mode

When the input carries a host orchestrator's routing envelope (e.g. `## NEXUS_ROUTING`), the chain runs as a sub-orchestrator: it still owns its own phase chain and its own sub-hubs, but it does not call other top-level skills directly and returns all work under the host's handoff heading (e.g. `## NEXUS_HANDOFF`; envelope → `reference/contracts.md` §7). Surface: the phases run, the Risk-Gate verdict, the runner and its envelope, the acceptance-verification result, the residual gap, and the resumable checkpoint.

---

> The chain is expensive on purpose: the cheapest place to find out you built the wrong thing is before you build it.
