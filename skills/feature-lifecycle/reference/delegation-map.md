# Feature Lifecycle Delegation Map

**Purpose:** The one place this skill names skills it does not own. Every roster elsewhere is written in its own work-role vocabulary; this file says which installed skill, if any, each role prefers — and what it does when none is there.
**Read when:** You are about to fill a roster row and want to know whether a specialist exists for it. Never needed to *run* a phase.

## The Rule

**A roster row is work, not a callee.** The chain names what has to be produced and which gate it must pass. Who produces it is resolved at run time:

1. A skill in the delegation table below is installed and reachable → delegate to it, with the row's acceptance criteria and scope bound front-loaded per `reference/contracts.md` §5.
2. Nothing is installed for the row → **the chain performs the work itself**, on the engine the row's role resolves to (`reference/engine-roster.md`), against the identical exit gate.

A missing specialist changes *who* does the work. It never changes whether the gate is passed, what artifact the phase emits, or what the Delivery Report claims. **The chain has no required dependency; this whole file is an optimization.**

Two things follow, and both are load-bearing:

- **Nothing downstream reads a skill name.** Gates, artifacts, checkpoints, and the report are written against role names. A delegation table that went stale cannot break a run — at worst it fails to find a skill and the chain does the work.
- **A row the chain performed itself is recorded as such**, so a run's cost and its evidence are read against what actually ran.

## Delegation Table

Names are those of the `agent-skills` ecosystem this skill was extracted from. Treat them as *candidate* names: a workspace that ships a differently-named skill for the same work is matched on the work, not the string. A row marked **no candidate claimed** is one the chain has no known specialist for — it is not a gap in the row, only in this table, and the chain performs it as it performs any undelegated row.

| Phase | Work role | Prefers, if installed | Its own fallback |
|-------|-----------|----------------------|---------------------|
| 0 | `project-scan` | — (always the chain's own) | Read git history, open issues/PRs, in-code TODOs, `.agents/PROJECT.md`, README |
| 0 | `user-signal` | `voice` | Read whatever feedback source is configured; skip and flag `confidence: low` if none |
| 0 | `metric-signal` | `pulse` | Read the configured analytics export; skip and flag if none |
| 0 | `competitor-gap` | `compete` | Skip unless a competitor list is maintained in-repo |
| 0 | `session-replay` | `trace` | Skip unless a replay export is available |
| 0 | `goal-proposal` | `spark` | Propose plausible distinct candidates from the scan without filling a quota |
| 0 | `goal-scoring` | `rank` | Compare sourced inputs with a suitable framework; leave unknown inputs unscored |
| 0 | `advisory-check` | `magi[advisor]` | One adversarial pass over the top candidate |
| 1 | `demand-modeling` | `echo[demand]` | Generate optional relevant scenarios, explicitly hypothetical; no persona quota |
| 1 | `evidence-validation` | `field` | State each need's provenance and claim-specific support; deduplicate observations and keep unsupported claims hypothetical |
| 1 | `friction-baseline` | `echo` | Walk the current flow and record where it costs the user |
| 1 | `reuse-scan` | `lens` | Grep and read the repo for an existing implementation of the same capability |
| 2 | `option-generation` | `flux` | Expand → propose → evaluate → subtract, bounded to 4 turns |
| 3 | `deliberation` | `magi` | Run the three voices as three spawns, one per engine |
| 4 | `spec-authoring` | `scribe[unified]` | Author L0→L3 and the traceability matrix directly |
| 4 | `scope-cutting` | `void` | One YAGNI pass over the spec |
| 4 | `formal-spec` | `scribe` | Emit the formal document in the requested shape |
| 4 | `measurement-contract` | — (no candidate claimed) | State the quantitative or qualitative observation, reader and window; unsupported size stays unmeasured, or state why the demand is unmeasurable |
| 5 | `architecture-decision` | `atlas` | Author the ADR and the dependency graph |
| 5 | `api-design` | `gateway` | Author the API surface and its OpenAPI document |
| 5 | `schema-design` | `schema` | Author the schema delta and the migration plan |
| 5 | `ux-direction` | `vision` | The chain owns the UX sub-roster directly instead of sub-orchestrating |
| 5 | `design-tokens` | `muse` | Author the token set |
| 5 | `interaction-design` | `palette` | Author the interaction and a11y spec |
| 5 | `microcopy` | `prose` | Author the strings, error and empty states |
| 5 | `motion-spec` | `flow` | Author durations, easing, and the reduced-motion path |
| 5 | `design-file-extraction` | `frame` | Read the design file through whatever integration exists, or skip |
| 5 | `prototype` | `forge` | Build the working slice |
| 5 | `friction-walkthrough` | `echo` | Run the cognitive walkthrough and the a11y simulation |
| 5 | `i18n-strategy` | `polyglot` | Author the extraction strategy |
| 5 | `mockup-to-code` | `pixel` | Translate the supplied mockup |
| 5 | `failure-mode-analysis` | `omen` | Run the FMEA and author the three mitigation layers |
| 5 | `blast-radius-analysis` | `ripple` | Trace callers, data, and contracts outward from the change |
| 5 | `security-review` | — (no candidate claimed; a workspace security-review skill matches on the work) | Walk every new entry point for authz, every new dependency, every newly persisted or transmitted field for its data class, and the regulatory exposure that follows |
| 6 | `loop-driver` | `orbit` | The chain drives the bounded loop itself — `reference/contracts.md` §4 |
| 6 | `implementation` | `builder` | Write the backend and business logic |
| 6 | `frontend-implementation` | `artisan` | Promote the prototype to production frontend |
| 6 | `component-catalog` | `vitrine` | Author the component stories |
| 6 | `code-review` | `judge` | Review the cycle's diff against the contract |
| 6 | `test-authoring` | `radar` | Author unit and integration tests |
| 6 | `e2e-persona-tests` | `voyager` | Author E2E flows from the Phase 1 personas |
| 6 | `instrumentation` | — (no candidate claimed) | Emit the events, counters, or spans the measurement contract names |
| Verify | `acceptance-verification` | `attest` | Run both passes directly — always on the `judge` engine |
| Ship | `commit-and-pr` | `guardian` | Apply `reference/contracts.md` §10 and open the PR |
| Ship | `release-plan` | `launch` | Author the release notes, CHANGELOG entry, and rollback plan |
| Ship | `rollback-rehearsal` | — (no candidate claimed) | Execute the rollback plan; exercise a migration's down-path against production-shaped data |

## Outward Routes

The chain also *hands work off* at five points. Each is a typed residual in the Delivery Report, addressed to a **capability**, not to a skill that must exist:

| Residual | Goes to | If nothing is installed |
|----------|---------|-------------------------|
| A performance AC unmet inside the envelope | A performance-tuning capability (`optimize`) | Report the target number and the remaining budget as an open residual |
| A loop the circuit breaker stopped | A diagnosis capability (`triage`) | Report the iteration history and the last good checkpoint |
| A must-have AC that is unbuildable as written | Whoever owns the spec | Report it as blocking; the chain never reinterprets the AC locally |
| Coverage gaps the run did not close | The backlog | Report the gap list with a class per item |
| The measurement contract, still open at ship | Whoever reads the metric | Report it as `hypothesis-open` with the window and where the number is read — the chain cannot close it and never marks it closed |

A residual with nowhere to go is still **reported**, never absorbed. The chain not having a downstream is a fact about the workspace, not a reason to drop the finding.

## Sub-Orchestration and This File

Two roles are sub-orchestrators when their skill is installed — `ux-direction` and `loop-driver`. When neither is, the chain runs their rosters directly and the topology flattens from two tiers to one. The concurrency cap, the merge surface, and every gate are unchanged; only the number of hubs differs (`SKILL.md` § Sub-Orchestration).
