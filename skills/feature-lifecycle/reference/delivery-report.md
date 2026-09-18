# Feature Lifecycle Delivery Report, Budget Envelope, and Failure Escalation

**Purpose:** The output envelope the chain emits, the run-level budget ceiling, the checkpoint-resume guarantee, and the consolidated table of what each gate guards against.
**Read when:** You are emitting output, sizing or enforcing the envelope, resuming an aborted run, or classifying a failure.

## Contents
- Output envelope
- The Feature Lifecycle Delivery Report
- Cost Profile
- Run-Level Budget Envelope
- Cross-Phase Checkpoint-Resume
- Failure Escalation
- Boundaries vs neighbors

---

## Output Envelope

The chain emits `## FEATURE_LIFECYCLE_COMPLETE` when invoked directly. Under an orchestrator's routing marker it emits a handoff instead (`reference/contracts.md` §7) and the Delivery Report travels inside it; when a hub asks for `NEXUS_COMPLETE` semantics, the Delivery Report is the named recipe report inside that envelope. The **content below is identical in all three cases** — only the wrapper changes.

```
## FEATURE_LIFECYCLE_COMPLETE
Goal: [feature title]
Mode: [run | bootstrap | resume]  ·  Scope: [Lite | Standard | Full]
Phases run: [e.g. 0-6 + Ship, or 4-6 with a spec packet]
Status: SUCCESS | PARTIAL | BLOCKED | FAILED

### Feature Lifecycle Delivery Report
[the table below]

### Acceptance Provenance
| Criterion | Class | Evidence / gap |
|-----------|-------|----------------|
| [AC] | verified \| partial \| missed \| dropped(DEC-n) | [observed evidence, or the precise gap] |
| [prohibited outcome / non-goal] | held \| violated \| unverified | [evidence it did not occur] |

### Decision Ledger
- [DEC-n (class)]: [decision] — [why]   (omit the section when empty)

### Residual Ledger
| ID | Residual | Class | Blocker / owner | Marker location | Route |
|----|----------|-------|-----------------|-----------------|-------|
| RES-n | [what is not done] | blocked-external \| gate-pending \| out-of-contract \| budget-exhausted \| user-declined \| hypothesis-open | [named blocker] | [file:line `#TODO(agent):`, or `none`] | [the capability that finishes it, or `none installed`] |

Completion sweep: [command run] — [N hits, each mapped to a RES-n, or `pre-existing`]
Run record: .agents/feature-lifecycle/runs/[run-id]/ — run_record_committed: [true | false]
Checkpoint: [resume point, on any non-ship exit]
```

A prohibited outcome is `held` only with evidence that it did not occur. `unverified` is honest; `held` by assumption is not, and `violated` caps the run at `FAILED`.

## The Feature Lifecycle Delivery Report

| Section | Content | Sourced from |
|---------|---------|--------------|
| Discovery summary | Decision-driving needs, source/status/support scope and unresolved hypotheses; selected goal and actual rejected alternatives | Phase 0-1 |
| Spec & AC | Obligation → AC traceability; required/decision-critical and optional status; percentage as summary only | Phase 4 |
| Design decisions | ADR(s) + API/schema deltas; UX direction + token/interaction summary | Phase 5 |
| Risk-Gate verdict | Four-axis result (failure-mode RPN / blast radius / friction + a11y / security exposure) and any Conditional-Go conditions | Phase 5 gate |
| Engine roster | Probe result per CLI, the `build`/`judge`/`breadth` bindings, any rebinding with its reason, `engine_independence: model \| context-only`, `simulated_voices`, and the per-engine spend sub-ledger | Resolved before the first spawn |
| Loop iterations | **`runner: codex \| claude-code \| agy`** (the CLI that resolved to `build`) + the envelope it was scored against, iteration count, cost per task, convergence reason, circuit-breaker status, loop-precondition verdict | Phase 6 |
| AC-verify | Conformance % as summary + obligation/AC/oracle/evidence matrix; `unmet_must_haves: 0`, `unmet_required: 0`; **negative pass: `non_goal_violations: 0`**, with any ratified out-of-boundary change named; `integration_evidence: E5 \| unavailable`, required evidence and any blocking gap; the engine it ran on, which is never the engine that built wherever a second one was reachable | Phase 6 → Ship gate |
| Upstream packet | Which input contract was consumed (`spec` / `clone` / none) and which phases it collapsed | `reference/input-contracts.md` |
| Follow-ups | Perf ACs unmet inside the envelope → a performance-tuning capability, with target and budget; coverage gaps → backlog; the open measurement contract → whoever reads the metric | Ship |
| Measurement contract | The metric or qualitative observation, supported prediction (otherwise unmeasured), window and reader — and its `hypothesis-open` residual. Never marked closed by the run that opened it | Phase 4 → Ship |
| Ship status | PR + release/rollback plan; `rollback_verified: true \| declared-impossible(reason)`; required recovery evidence, compensating-control tests and explicit risk acceptance where impossible; cumulative budget vs ceiling | Ship |
| Run record | The run-record path and `run_record_committed`. Every number above is a summary of a phase document under it; without the path the report is a set of figures nobody can go behind | `reference/run-record.md` |

On **any** non-ship exit — budget ceiling, Risk-Gate No-Go, acceptance-verification fail past the re-entry cap, engine unavailable with no answer — the Delivery Report still emits, with best-so-far per phase, the residual gap, and the resumable checkpoint. Never a silent stop.

## Cost Profile

| Profile | Phases active | Approx agent count | Approx cost |
|---------|---------------|--------------------|-------------|
| Lite (no UI, spec scope Lite) | 1, 2, 3, 4, 5-Tech, 5-Gate, 6, Verify, Ship | 11-13 | Low |
| Standard (UI, spec scope Standard) | All | 17-22 | Medium |
| Full (greenfield, spec scope Full) | All + `scope-cutting` + `formal-spec` + `design-file-extraction` + `i18n-strategy` | 23-30 | High |
| Autonomous bootstrap (Phase 0 added) | + `project-scan` + `goal-proposal` + `goal-scoring` + the conditional signal rows as available | +4-8 over base | +10-20% over base |

Every profile carries **three rows more than it did before the security, measurement, and rollback-rehearsal additions** — those three are required, not conditional, so they land on the Lite profile too. `instrumentation` and the integration-evidence pass add up to two more where they apply. The figures above already include them.

The agent counts are engine-agnostic; the **cost** is not. A run spread across three CLIs spends against three pricing models, so the envelope carries a per-engine sub-ledger and a single mixed total is never quoted as the figure (`reference/engine-roster.md` § Cost and Recording). A roster that degraded to one engine changes the cost shape, not the agent count — which is why the roster is reported next to the spend rather than instead of it.

The historical profile assumes Phase 0 adds roughly 10-15 minutes; this is an uncalibrated estimate, not a runtime promise. Missing launch authority stops at a proposal; a sufficient grant adds no duplicate routine confirm. For repeated similar requests, propose a project-local skill to amortise the chain design cost rather than re-running the chain.

## Run-Level Budget Envelope

The loop's cost-per-task breaker bounds the *loop*. The *whole run* — Phase 0-6 + Ship, up to 30 agents × loop iterations, so 27-61 spawns at the Full autonomous profile — carries a **pre-declared budget envelope**, bound to the explicit launch grant alongside the agent/time/token estimate. An estimate does not authorize its own ceiling or a later increase.

- `budget_ceiling` (tokens or agent-spawn count). The chain tracks cumulative spend across all phases and **hard-aborts with a resumable checkpoint** when the ceiling is reached, rather than running open-ended. Default ceiling = the cost-profile estimate × 1.5; the user may override at launch.
- At **80% of the ceiling**, emit a warning. In `GUIDED`/`INTERACTIVE`, pause for a continue/abort decision; in `AUTORUN_FULL`, log the warning and proceed to the ceiling.
- The ceiling is a hard stop, not advisory. It is what protects against a runaway Phase 6 loop or a re-entry storm from the acceptance-verification gate.

## Cross-Phase Checkpoint-Resume

The chain persists each phase-boundary output as a resumable checkpoint: the Phase 0 goal artifact, the Phase 3 verdict + AC seed, the Phase 4 spec + traceability, the Phase 5 design + Risk-Gate result, and the Phase 6 build state.

**Where those checkpoints live on disk, and the write discipline that makes one trustworthy, is `reference/run-record.md`.** This section owns *what* is persisted and *what the guarantee is*; that file owns the directory, the document shape, and the seal-at-the-gate rule. A checkpoint whose location is unstated is a guarantee with no mechanism under it.

A run that aborts mid-flight — budget ceiling hit, Risk-Gate No-Go, circuit breaker, engine unavailable, user interrupt — **resumes from the last good phase** instead of restarting from Phase 1. The loop driver already owns in-loop checkpoint-resume; this extends the same guarantee to the cross-phase boundaries, so the most expensive chain never re-pays for upstream phases it already completed.

`feature-lifecycle resume` reads `RUN.md`, re-binds the artifacts it names, and continues from the next phase. It never infers the resume point by scanning the directory — a listing cannot tell a sealed phase from one killed a second before its gate.

## Failure Escalation

What each gate guards against, merging the operational trigger (what happens now) with the failure class (what it prevents).

| Failure | Cause / detected by | Escalation / prevented by |
|---------|---------------------|---------------------------|
| No data sources for the Phase 0 scan | Greenfield project, no real users yet | Fall back to "propose from the project scan only"; flag candidates `confidence: low` |
| Phase 0 no candidates | `goal-proposal`; project state extremely stable | Abort; suggest invoking with an explicit goal |
| Phase 0 priority unsupported | Missing or biased scoring inputs | Leave inputs unknown; present the unresolved choice or stop, never invent a priority |
| Phase 0 unresolved choice | Evidence cannot distinguish candidates | Present actual trade-offs within delegated product authority; otherwise request selection |
| Launch authority missing or goal rejected | User/grant check | Stop at the proposal or checkpoint; no response is not consent. Return objections to the goal owner |
| Build the wrong thing | No evidence anchor for the feature | Phase 0 discovery + Phase 1 (`demand-modeling` + `evidence-validation` anchor) + the boundary confirm |
| Phase 3 split decision | `deliberation` | Pause for a human verdict; prevents an arbitrarily-resolved deadlock |
| Weak / unmeasurable spec | "Done" is subjective; scope creeps | Phase 4 required/decision-critical coverage + L3 measurable, loop-consumable ACs |
| Phase 4 obligation not traced | `spec-authoring` | Return to P4 or the intent owner; no unilateral demotion, omission or scope downgrade |
| Hidden architecture / blast-radius risk | A migration or contract change breaks neighbors post-merge | Risk Gate: `failure-mode-analysis` (high-RPN residuals = 0) + `blast-radius-analysis` (No-Go blocks) |
| Risk Gate No-Go | `failure-mode-analysis` / `blast-radius-analysis` / `friction-walkthrough` / `security-review` | Return to the originating phase |
| New attack surface, unowned data, or regulatory exposure shipped | A new entry point without an authz rule, a new persisted field without a data class, a new dependency nobody vetted | Risk Gate `security-review`: `unmitigated_high == 0`, and the row is required rather than conditional so it cannot be skipped by the judgment it exists to make |
| UX friction / dark patterns shipped | Brand-visible flow frustrates users; a11y regressions | the Phase 5 `friction-walkthrough` gate + the demand↔reaction divergence check |
| Demand↔reaction divergence | Sourced observation, not synthetic self-validation | Demand → P1; spec → P4; interaction/design → P5; goal change → launch authority |
| Convergence mistaken for correctness | The loop passes its own tests but does not satisfy the spec | Acceptance verification: independent meaning/conformance check ∧ 0 unmet required obligations, run on the `judge` engine, in a fresh context, off build where available; model/evidence/oracle provenance is stated separately and a single engine remains `context-only` |
| Scope creep shipped as success | The loop satisfies every AC *and* adds surfaces, deps, or persisted state nobody specified | Acceptance verification **negative pass**: `non_goal_violations == 0`; out-of-boundary changes reverted or explicitly ratified |
| Stuck loop | Driver convergence detection | Typed residual to a diagnosis capability; reported as a residual where none is installed |
| Loop budget exceeded | Driver cost-per-task | User confirmation before continuation |
| Runaway loop / re-entry storm | Open-ended spend, stuck iterations | Circuit breaker + § Run-Level Budget Envelope + the acceptance re-entry cap |
| Repeat implementation failure | `code-review` / `test-authoring` | Diagnose first; return to the originating decision, not automatically another code cycle |
| Unmet acceptance criteria | The acceptance verification | First wrong decision → P1/P2/P3/P4/P5; implementation → P6. At most 2 acceptance-triggered re-entries total; retain unaffected artifacts |
| Engine silently degrades | Runner unreachable → a silent swap breaks the cost/convergence model | Phase 5→6 availability check + the Engine Degradation Protocol: an explicit confirmed choice with a restated ceiling and budget, recorded in the report; no answer → checkpoint and stop |
| Five phases thrown away over a runner problem | Runner unavailable → the whole run would otherwise hard-fail and restart later from scratch | The degradation protocol's abort option is a **checkpointed** resume at Phase 6, not a restart |
| Re-deriving a settled spec | The chain re-runs discovery/verdict over a spec already locked and refuted | `reference/input-contracts.md` § Spec Handoff Packet |
| Rebuilding what the repo already ships | A second implementation of an existing module | The Phase 1 reuse scan is mandatory on an existing repo, or inherited via `reuse_findings` |
| Filing a stack-imposed limit as a defect | A clone's declared parity ceiling gets "fixed", moving the product off its baseline | `reference/input-contracts.md` § Clone Handoff Packet |
| Run budget ceiling reached | The chain's run-level envelope | § Run-Level Budget Envelope |
| A false hypothesis shipped as a success | Every gate passes on conformance to a spec derived from a demand nobody ever measured | Phase 4 `measurement-contract` + the `hypothesis-open` residual. The chain cannot close it; it can refuse to ship one with no way to settle it |
| A rollback plan that has never been run | The reverse path is prose while the forward path has four gate axes and a two-sided verification | Ship `rollback-rehearsal`; impossible stays distinct from verified and blocks without required recovery evidence, tested controls and explicit residual-risk acceptance |
| The next Phase 0 goes blind | A feature ships with no events behind its own measurement contract, so the following autonomous scan cannot see it | Phase 6 `instrumentation`, conditional on the contract naming a metric the codebase does not already emit |
| Local green, real-surface red | Every AC passes against local mocks; the integration surface would have rejected it | Risk-specific integration evidence: record availability honestly and block when required evidence is missing; local conformance does not establish safety on an untested critical surface |
| Lost progress on interrupt | An abort would otherwise re-pay for completed upstream phases | § Cross-Phase Checkpoint-Resume, on the on-disk record of `reference/run-record.md` |
| A finding paid for twice | A failed gate returns to its originating phase, which re-derives the evidence the first pass already produced because only the verdict was kept | `reference/run-record.md`: the phase document is sealed at the gate — failures included — and a re-entry appends rather than rewrites |
| A number nobody can go behind | The Delivery Report quotes a conformance %, an RPN or a friction score whose derivation lived only in a finished conversation | `reference/run-record.md` § Per-Phase Contents, and the rule that a number is written with what produced it |

## Boundaries vs Neighbors

Feature Lifecycle is the discovery-through-ship **single-feature** chain. How it differs from the capabilities nearest it — each named by what it does, since none of them need exist for the chain to run:

| vs neighbor | Feature Lifecycle | The neighbor |
|-------------|------|--------------|
| **Spec authoring** | Discovers the need, specs it, **and** designs + builds + ships it. Entered *from* a spec packet, it validates rather than re-derives | Authors the spec and ACs only — stops at the document |
| **Performance tuning** | Ships the feature; a perf AC it could not meet inside the envelope is handed over with its target and budget | Measures and improves one already-correct slow layer against a number — no discovery, no ship cycle |
| **Charter execution** | Self-contained: discovers its own goal and ships one feature in one chain | Executes a pre-authored multi-package roster end-to-end, with no discovery |
| **Quality-max tournament** | Optimizes for shipping one feature correctly through verification gates | Multiple candidate solutions compete and are judged to a winner |
| **A lighter guided build** | Unresolved upstream decisions with costly late discovery that proportionate lifecycle work can reduce | A single guided build for small/medium work — lighter chain, no Phase 0, no four-axis gate |
| **Charter authoring** | Builds the thing | Authors the durable team-design document the charter-execution path consumes; never builds |

Decision line: apply `SKILL.md` § Trigger Guidance before assigning this chain ownership; high stakes or end-to-end wording alone is insufficient. Spec and ACs only → the spec path. A pre-authored roster → charter execution. Competing candidates judged to a winner → the tournament path. Small or medium guided build → the feature path.
