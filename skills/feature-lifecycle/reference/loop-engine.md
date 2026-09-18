# Feature Lifecycle Phase 6 — Loop Engine and Acceptance Verification

**Purpose:** The implementation loop's driver selection, engine boundary, spawn sequence, degradation protocol, termination bounds, and the two-sided acceptance verification that gates Ship.
**Read when:** You are at the Phase 5 → 6 handoff, inside the loop, or deciding whether the run may ship. Which CLI each engine role resolved to is in `reference/engine-roster.md`; who performs a roster row is `reference/delegation-map.md`; where the loop contract, the per-cycle record and the acceptance matrix are written is `reference/run-record.md`.

## Contents
- Loop driver selection
- Runner engine and the engine boundary
- In-loop roster and spawn sequence
- Engine availability check
- Engine Degradation Protocol
- Loop precondition gate
- Termination bounds
- Acceptance Verification (Phase 6 → Ship gate)
- Integration evidence (conditional third pass)

---

## Loop Driver Selection

Run the availability gate of `reference/contracts.md` §4 **before** selecting the driver.

| Path | Condition | Who owns the loop |
|------|-----------|-------------------|
| A project-local loop-runner skill | The workspace availability gate passes | It consumes the L3 ACs + mitigations + friction signals, authors the loop contract, generates the runner script set, and audits convergence |
| Fallback | No project-local installation | The chain drives the same bounded loop directly and owns the contract, convergence, and circuit-breaker duties. Record `project_local_fallback: true`; no repository-specific runner is generated |

For the rest of this file, "the driver" means whichever of the two was selected. The **duties do not change** with the path — only who discharges them.

## Runner Engine and the Engine Boundary

**The runner is whichever CLI resolved to the `build` role** — Codex CLI by default (`reference/engine-roster.md`). It changes only through role resolution at launch, or through the Engine Degradation Protocol below when the bound engine turns out to be unreachable at the handoff — a confirmed choice with a restated cost model, never a silent swap.

The Phase 5 → Phase 6 boundary is **both a phase boundary and an engine boundary**. Nothing crosses it except the loop contract; the driver's spawns cross through the documented subagent contract — native `spawn_agent` when `build` is the hub, headless `codex exec … -o <abs path>` when it is not — never as a direct agent-to-agent handoff.

**Not every in-loop row runs on `build`.** The loop is where maker ≠ checker has to hold, so the checkers are pushed off the building engine: implementation on `build`, review and tests on `judge`, long-flow E2E on `breadth`. The roster below names the role per row; `reference/engine-roster.md` names the CLI each role resolved to.

## In-Loop Roster and Spawn Sequence

| Agent | Work | Required | Engine role |
|-------|------|----------|-------------|
| `loop-driver` | Loop contract design + convergence detection + cost-per-task tracking + circuit breaker | Conditional: a project-local loop runner is available; otherwise the chain owns this row | hub — then writes the runner spawn scripts |
| `implementation` | Business logic / backend implementation | Yes | `build` |
| `frontend-implementation` | Production frontend (promotes the Phase 5 prototype) | Conditional: UI surface | `build` |
| `component-catalog` | Component stories | Conditional: components added | `build` |
| `code-review` | Per-iteration review of the cycle's diff | Yes | `judge` |
| `test-authoring` | Unit / integration tests | Yes | `judge` |
| `e2e-persona-tests` | E2E persona-driven tests (reuses the Phase 1 personas) | Conditional: UI flows | `breadth` |
| `instrumentation` | Emit the events, counters, or spans the Phase 4 measurement contract needs to be readable | Conditional: the contract names a metric the codebase does not already emit | `build` |

**`instrumentation` is what keeps autonomous mode from going blind.** When Phase 0 selected the goal from `metric-signal`, a feature shipped without the events behind its own measurement contract is invisible to the next Phase 0 scan — so each `feature-lifecycle bootstrap` run adds a surface the following run cannot see. The blind spot compounds silently, and it compounds fastest on exactly the features the loop was most confident about.

Putting `test-authoring` on `judge` separates the maker from the checker; it does not make an oracle independent. Record the expectation source, not just the engine. The final acceptance pass uses a fresh context even when it shares the test-authoring engine, and checks original intent/source constraints rather than inheriting the test author's interpretation (`reference/contracts.md` §3).

Per-cycle sequence:

```
spawn(build,   implementation,          prompt=<BE contract>)   ‖
spawn(build,   frontend-implementation, prompt=<FE contract>)?
  → join(all)
  → spawn(build,   component-catalog)?  → join
  → spawn(judge,   code-review)         → join
  → spawn(judge,   test-authoring)      → join
  → spawn(breadth, e2e-persona-tests)?  → join
  → spawn(build,   instrumentation)?    → join
```

`spawn(role, …)` is the native subagent API when that role is the hub, and the headless invocation of `reference/engine-roster.md` when it is not. `join` is `wait_agent` on the native path and a process wait plus an artifact read on the headless one.

The driver audits via the subagents' return values: `convergence_detection`, `deduplication_guard`, `cost-per-completed-task`, `circuit_breaker`. A stuck loop or an exceeded budget terminates the running spawn — `close_agent` on the native path, killing the subprocess on the headless one — and escalates to the user.

**Each cycle appends to `06-loop.md`** — what changed, what `code-review` flagged, and Δ. A loop that exits on `cap-reached` or `BLOCK` is the one whose per-cycle history the diagnosis handoff needs, and it is exactly the exit at which nobody has time to reconstruct it (`reference/run-record.md`).

## Engine Availability Check

A **Phase 5 → 6 handoff prerequisite.** Before consuming the contract, verify:

- the CLI bound to `build` is reachable and answers a spawn, not merely `--version`,
- the CLI bound to `judge` is reachable **and is not the same CLI as `build`**, wherever a second CLI is reachable at all — the in-loop checker separation and the acceptance verification both depend on it. On a single-engine workspace the condition is unsatisfiable by construction: this is the one check that **reports** the collapse rather than blocking on it, and the run carries `engine_independence: context-only`,
- `agents.max_depth ≥ 2` on the native path,
- the required subagent tools are permitted (`spawn_agent`, `wait_agent`, `send_input`, `resume_agent`, `close_agent`), or the headless binary accepts its artifact flag.

If any check fails, **never silently fall back.** The chain's cost and convergence model assumes the declared engine, and a silent swap invalidates the budget envelope the run was authorized against. Enter the degradation protocol instead.

## Engine Degradation Protocol

Hard-failing the handoff throws away five completed phases over a runner problem. So unavailability is surfaced as an **explicit choice with a restated cost model**, presented once via `AskUserQuestion`. It is a confirmation gate, not a fallback.

| Option | `build` rebinds to | Restated model | When it is the right call |
|--------|--------------------|----------------|---------------------------|
| **Abort & resume later** (default recommendation) | — | Phase 0-5 output is checkpointed; the run resumes at Phase 6 once the engine is reachable. The roster is unchanged, so the envelope still holds | The blocker is transient — config, auth, quota. Prefer this whenever the engine is *present but unusable* rather than absent |
| **Claude Code** | `Agent(... run_in_background)`, or headless `claude -p … --output-format json` | **Iteration ceiling drops to `≤ 4`** (§ Termination Bounds) and the **budget envelope is recomputed** at Claude per-token rates before cycle 1. `judge` must rebind off Claude Code — to agy where reachable, otherwise the run drops to `engine_independence: context-only` and says so | The feature is small-to-medium and the run should finish now |
| **agy** | `/agent`, or pty-wrapped `agy -p` (`reference/engine-roster.md`) | Every in-loop spawn runs on the Gemini mandate; long-context branches benefit, code-gen throughput is lower, so the **budget envelope** is recomputed upward at agy's rates while the ceiling stays `≤ 6` (§ Termination Bounds). `judge` stays on Claude Code — this is the cheapest degradation for independence | Long-context or multimodal-heavy implementation work |
| **Proceed on one engine** | — (`build` stays on the hub) | Every role folds onto the hub, so `judge` cannot separate from `build`: the in-loop checker separation and the acceptance verification drop to context isolation and the run records `engine_independence: context-only`. The ceiling is whatever § Termination Bounds gives the hub engine; **no gate threshold moves** | The workspace ships one CLI at all. The chain is standalone by design, and blocking here would trade a recorded degradation for no run — offer it only when no second CLI can be reached, never as an escape from a transient blocker |

**Rules:**
- The chosen engine and its restated envelope are recorded in the Delivery Report's *Loop iterations* row (`runner: codex | claude-code | agy`) alongside the `engine_roster` block, so a run's cost figures are never read against the wrong model.
- A rebind of `build` **re-runs role resolution for `judge`**, never just for itself. Hard rule 1 of `reference/engine-roster.md` binds after degradation exactly as it binds before it.
- A fallback **never** relaxes the acceptance verification — it stays on `judge`, off the engine that built. Where no second engine exists, the verification still runs and is recorded as `context-only`.
- If the user does not answer, the run **checkpoints and stops**. It does not pick an engine on their behalf.

## Loop Precondition Gate

Run the five-point gate of `reference/contracts.md` §2 before entering the loop. Point #2 is the declared cap below; point #3 is the driver's evaluator separation (`code-review`/`test-authoring` are neither the implementer nor its engine). Report the verdict in the Delivery Report.

## Termination Bounds

**The iteration ceiling is keyed to the engine that resolved to `build`, and this table is its only source.** Everywhere else states the default and points here.

| `build` engine | Ceiling | Why |
|----------------|---------|-----|
| Codex CLI | `≤ 6` | The default the cost profile is written against |
| agy | `≤ 6` | Code-gen throughput is lower, so a cycle achieves less — the run needs the headroom, not less of it. What changes is the **budget envelope**, recomputed at agy's rates, never the safety bound |
| Claude Code | `≤ 4` | Context isolation is weaker: in-loop spawns share a main session that accumulates rot, so drift arrives earlier in the cycle count. The tighter bound is about isolation, not speed |

A lower ceiling is not a penalty for a slower engine. Confusing the two produces the exact wrong move — cutting cycles from the engine that needs more of them.

| Loop | Bound | Exit reasons |
|------|-------|--------------|
| **Implementation loop** | Per the table above | `ACCEPT` · `diminishing-returns (Δ < ε)` · `cap-reached` · `BLOCK` |
| **Acceptance-gap loop** | `loop ≤ 2 re-entries total` (default N=2) — return to the first wrong decision; code gaps to Phase 6, then escalate | `ACCEPT` · `cap-reached` → user decision · `BLOCK` |

On any non-`ACCEPT` exit, the Delivery Report states which acceptance criteria remain unmet and the residual gap. The chain never ships a silent partial.

---

## Acceptance Verification (Phase 6 → Ship gate)

The driver detects **loop convergence** — the iteration stopped producing changes. Convergence is not correctness: a loop can converge on an implementation that passes its own tests and does not satisfy the spec. Ship is therefore gated on independent verification from authorized intent through Phase 4 L3 ACs to implementation; a spec that omitted or misread the requested outcome cannot certify itself.

| Pass | Role | Pass criterion |
|------|------|----------------|
| **Conformance** (`judge`) | Read original authorized intent and scope changes, then map obligation → AC → independent oracle/evidence → verdict. Check the spec interpretation as well as implementation | `unmet_required == 0` (must-have and decision-critical); no unauthorized omission/demotion; optional gaps explicit. Percentages summarize, never waive obligations |
| **Negative pass** (`judge`) | Check whether only the authorized feature was built. Walk positive scope, original intent, `non_goals` / out-of-scope and the Phase 3 scope boundary against the actual diff — new surfaces, new dependencies, new config, new persisted state, behavior outside the declared boundary | Zero non-goal violations; every out-of-boundary change is either reverted or **explicitly ratified by the user**, never silently kept |

Conformance alone is a one-sided test. An implementation can satisfy every AC **and** have grown a feature nobody asked for, a dependency nobody approved, or a table nobody specified. An autonomous loop is exactly the setting where that happens, because "add a little more" always looks like progress from inside the loop. The negative pass is what makes the scope boundary load-bearing rather than decorative.

Both passes are distinct from in-loop code quality and passing tests. The verifier receives original authorized intent, AC/scope revisions, source constraints and required evidence, not builder reasoning or the test author's conclusion as an oracle. It runs in a fresh context on `judge`, off the building engine wherever a second engine is reachable; one engine remains `context-only`. Report model, context, evidence and oracle independence separately (`reference/contracts.md` §3). Engine diversity alone proves none of the shared premises.

A private enabling change necessary for an existing AC, with no new outward behavior, permissions, data use or commitments, can stay within scope; record its rationale and verify its risk. A new external surface, dependency or persistence behavior is not implicitly authorized by calling it enabling: check the existing boundary, otherwise revert or obtain explicit ratification.

### Integration evidence (conditional third pass)

Where the workspace exposes a real integration surface — a preview environment, a staging deploy, a policy or attestation check — run the **must-have ACs against it** and record the rung reached. This is the `E5` rung of `reference/contracts.md` §3: the surface that rejects what local mocks accepted.

| Condition | Action |
|-----------|--------|
| An integration surface exists and is reachable | Run the must-have ACs against it; record `integration_evidence: E5` and any AC the real surface failed |
| No such surface exists or it is unreachable | Record `integration_evidence: unavailable`, missing required evidence and what would supply it; block readiness if the P5 requirement is unmet |

P5 owns the risk-specific evidence requirement; VERIFY checks whether the evidence actually discharges it. A missing or unreachable surface does not excuse a critical untested migration, payment/auth path or external contract. Conversely, low-risk reversible work may pass with the existing independent E3 floor when that suffices; record why E5 is not required. A local-green/real-surface-red AC blocks regardless of blame, and routes by the cause. Do not perform unauthorized production actions to obtain evidence.

**Exit gate:** `unmet_required == 0 ∧ non_goal_violations == 0 ∧ required_evidence_met`, with `integration_evidence` recorded. `required_evidence_met` means each P5 integration/recovery requirement applicable at this boundary has supporting observations and an independent oracle, not just an E-level label. Missing requirements or an unjustified low floor return to P5; missing evidence remains blocked. Reporting a completed local artifact is not declaring it safe to ship.

On failure, identify the first wrong decision, not the immediately previous phase: unsupported demand → P1; infeasible option → P2; unresolved choice → P3; missing/misinterpreted/unbuildable AC → P4/spec owner; architecture or interaction defect → the owning P5 track; implementation defect or unratified addition → P6 (revert or ask). A changed goal reopens launch authority. An unavailable required surface is `blocked-external`, not a request to rewrite correct code. Revalidate only artifacts dependent on the changed decision; retain unaffected evidence with its source. Acceptance-triggered re-entry remains bounded to **2 total**, even when it travels upstream, then escalates; no reset via scope edits. Never ship an unmet required AC or an unratified scope violation.

Evidence grading for an acceptance claim → `reference/contracts.md` §3. The chain's floor: every required AC is evidenced at **E3 with an independent oracle or above**; an AC backed only by a test the loop wrote from the same contract is `unverified`, not `verified`.
