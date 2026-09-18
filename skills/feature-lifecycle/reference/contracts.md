# Feature Lifecycle Operating Contracts

**Purpose:** The shared rules the chain depends on, carried inside the skill so it runs with no external contract directory. Everything a phase, gate, or spawn needs is here.
**Read when:** Entering the loop gate, grading evidence, selecting the loop driver, spawning across an engine boundary, or emitting the run's self-assessment. Role-to-CLI binding and the headless invocation contract live in `reference/engine-roster.md`.

**Provenance:** distilled from the `_common/` protocol set of the `agent-skills` repository (`LOOP_PRECONDITIONS`, `EVIDENCE_LADDER`, `PROJECT_LOCAL_SKILLS`, `SUBAGENT` / `CLI_COMPATIBILITY`, `WORK_GATE`, `HANDOFF`, `GIT_GUIDELINES`, `OPERATIONAL`). The chain carries its own copy on purpose: a standalone skill that names a contract it cannot open has no contract. When the chain runs *inside* that repository, its `_common/` originals are authoritative and this file defers to them.

## Contents
- 1. Precedence
- 2. Loop Precondition Gate
- 3. Evidence Ladder
- 4. Loop Driver Availability Gate
- 5. Engine and Spawn Contract
- 6. Work Gate
- 7. Handoff Envelopes
- 8. Run Record, Journal and Activity Log
- 9. Document Contract
- 10. Git Conventions

---

## 1. Precedence

When two rules disagree, resolve in this order rather than averaging them:

1. **The user's own words in this session** — nothing here outranks them.
2. **The host repository's instruction files** (`CLAUDE.md` / `AGENTS.md`) — they describe *this* repo; the chain describes every repo.
3. **`SKILL.md`** — the chain's Core Contract and Boundaries bind for work inside its domain.
4. **This file** — in effect on every run.

Two rules on top of the order:

- **Specific beats general at the same rank.** A rule scoped to the situation at hand outranks one scoped to all situations. Safety floors are the exception in the other direction — an **Ask First** gate is never narrowed by a more specific rule, only widened.
- **An unresolvable conflict is surfaced, not split.** Name both sources and ask, rather than inventing a midpoint neither endorses.

---

## 2. Loop Precondition Gate

**Contract-level checkpoint; AUTORUN cannot skip.** Run before entering the Phase 6 implementation loop. Report the verdict in the Delivery Report. A loop that fails a precondition fails *silently and expensively* — it surfaces as burned budget, not as an error.

| # | Precondition | Failed → anti-pattern | The chain's resolution |
|---|---|---|---|
| 1 | **Verifiable completion oracle** — a command or predicate where exit 0 ⟺ done | **loopmaxxing**: no exit condition, unbounded spend | The Phase 4 L3 acceptance criteria *are* the oracle. If an AC is not checkable, it failed the Phase 4 exit gate and the loop does not start |
| 2 | **Hard-stop bound** — an iteration cap / budget / timeout enforced **externally**, never by agent self-assessment | **overbaking / runaway**: drift and scope creep | `loop ≤ 6 cycles` by default, keyed to the `build` engine (`reference/loop-engine.md` § Termination Bounds), plus the run-level budget ceiling |
| 3 | **maker ≠ checker** — the generator does not grade its own work | **nodding loop**: self-approval, the most common failure | In-loop: `code-review` and `test-authoring` are neither the implementer nor its engine. At the gate: the acceptance verification runs on the `judge` engine, which is never the engine that built — wherever a second engine is reachable. On a single-engine workspace the separation is context-only and is **recorded as such**: degraded, never waived (`reference/engine-roster.md`) |
| 4 | **Persistent memory** — state lives outside the conversation (files / git), not in context | **amnesiac loop**: no cumulative progress | The run record's sealed phase documents (`reference/run-record.md`) plus the driver's in-loop state files. The loop satisfying this internally says nothing about the phases around it |
| 5 | **Drift awareness** — quality can decay across iterations *even while tests keep passing* | silent structural erosion | Bound the loop (#2), read a sample of the diff each cycle, and surface erosion as a run risk — never assert convergence as quality |

**The obligations are frozen before cycle 1.** Keep the original authorized intent, obligation IDs, AC set, non-goals and scope revision. Splitting or relabeling ACs does not change required coverage. A scope change is explicit and user-authorized; it never silently resets cumulative spend or the acceptance re-entry count. Private enabling changes inside the existing behavior boundary are not new scope; new surfaces, permissions, data use or commitments are.

**When a goal resists every checkable substitution**, do not loop on it and do not merely refuse: lower the action tier — build the throwaway version, run the dry run, produce the one sample — and re-enter the gate carrying the evidence that was missing. That exit is typed, not a failure.

---

## 3. Evidence Ladder

What rises with each rung is not effort — it is **distance from the implementation's own hypothesis**. Verification is not raising confidence; it is adding independent observations capable of finding the error.

| Level | Evidence | Mechanism | Independent of the implementer's assumptions? |
|-------|----------|-----------|-----------------------------------------------|
| `E0` | Model assertion | change explanation, self-review, reasoning trace | **No.** Useful to start, never to ship |
| `E1` | Static evidence | types, compiler, lint, SAST, dependency rules | Partially — an external rule engine, but only over syntax and declared contracts |
| `E2` | Local execution | build, reproduce, smoke | Partially — the runtime disagrees, but only on paths actually run |
| `E3` | Automated tests | unit, integration, contract | **Only if the oracle is independent.** A test written from the same context as the code is E0 wearing a green check |
| `E4` | Independent test | property, metamorphic, mutation, fuzz, differential | **Yes** — the expectation comes from a source other than the implementation |
| `E5` | Integration evidence | preview env, policy check, attestation, canary | Yes — the real integration surface rejects what local mocks accepted |
| `E6` | Production observation | SLO, trace, incident, user outcome | Yes — the only rung measuring the real input distribution |

**The chain's floor:** every required AC (must-have or decision-critical) must be evidenced at **E3 with an independent oracle or above**. An AC whose only evidence is a test the loop wrote from the same contract that produced the code is `unverified`, not `verified` — record it that way rather than counting it toward conformance.

**The chain's ceiling is not its floor.** Where the workspace exposes a real integration surface — a preview environment, a staging deploy, a policy or attestation check — the acceptance verification takes the `E5` rung against it and records the result; where none exists, it records `integration_evidence: unavailable`, and blocks readiness when risk-specific required evidence remains missing rather than letting an `E3` ceiling read as an integration test (`reference/loop-engine.md` § Integration evidence).

**Independence has four dimensions:** model identity/version, context isolation, evidence provenance, and oracle provenance. Distinct CLIs or models do not establish independent premises or expected results. Record what could falsify each critical claim and its source, separately from who ran the check. Reusing one observation or generated interpretation does not multiply evidence. A final verifier gets the original authorized intent and source constraints, not the builder's reasoning or a test author's conclusion as its oracle.

**A human saying so is not a rung.** An unverified human assertion sits at E0 and is more likely to be waved through because it arrives with a name attached. Authority is scoped per domain: a product owner is authoritative for intent, not for runtime behavior.

---

## 4. Loop Driver Availability Gate

The chain prefers a project-local loop runner when the workspace ships one, and falls back to driving the loop itself otherwise.

| Step | Check | Outcome |
|------|-------|---------|
| 1 | Does the workspace expose a loop-runner skill (under `.claude/skills/`, `.agents/skills/`, or the CLI's own skills root)? | No → fallback path |
| 2 | Does it declare the contracts the chain hands it — L3 ACs, mitigations, friction signals, a declared cap? | No → fallback path |
| 3 | Is its runner reachable from this session? | No → fallback path |

**Fallback path:** the chain drives the same bounded loop directly and owns the contract, convergence detection, cost tracking, and circuit-breaker duties itself. Record `project_local_fallback: true` in the Delivery Report. No repository-specific runner is generated.

**The duties never change with the path** — only who discharges them. A fallback that quietly drops the circuit breaker is not a fallback.

---

## 5. Engine and Spawn Contract

**Detect the hub engine once, before the first spawn**, then bind the spawn API and model map:

| Signal | Engine | Spawn API |
|--------|--------|-----------|
| `Agent` tool present | Claude Code | `Agent(...)`, `run_in_background` for concurrency |
| `spawn_agent` present | Codex CLI | `spawn_agent` / `wait_agent` / `send_input` / `resume_agent` / `close_agent` |
| `/agent` in a TUI main session | agy | `/agent`, or headless `agy -p` |

Detection settles **one** question: which spawn API the hub calls natively. It does not settle which engine does the work. The chain runs against three roles — `build`, `judge`, `breadth` — probed and bound once per run in `reference/engine-roster.md`; a role whose CLI is not the hub is dispatched as a headless subprocess by the invocation contract there. The rules in this section apply identically to both dispatch paths.

### Spawn prompt non-negotiables

Front-load, in this order: the phase's acceptance criteria · the output envelope · the scope bound (the spec's `non_goals`, verbatim) · the completion bound · prohibited outcomes · least-authority `Authority` with `redelegation: false`.

**Never ask a producer to verify its own output.** Verification is a separate spawn with no shared context — that is precondition #3, not a style preference.

### Silent-output regressions (read before spawning codex or agy)

- **agy headless MUST allocate a real pty** (e.g. `python3 pty.spawn`). Bare `agy -p` and `script -q /dev/null` **fail silently**: `exit 0` with empty stdout also describes a *successful* run, so the exit code cannot classify it. Capture via an artifact file or a sentinel, never stdout.
- **codex `-o <absolute path>`** writes the authoritative artifact. Read the artifact, not the transcript.
- Classify an empty capture as a **capture failure** first, with one typed repair retry — never as a task failure escalated through the normal retry ladder.

### Cross-engine dispatch

A subprocess spawn is still a spawn. It carries the same non-negotiables, counts against the same concurrency cap, and returns through a declared artifact — never a scraped transcript. Two rules are specific to it:

- **The hub merges; the subprocess never re-delegates.** `redelegation: false` is not weaker across a process boundary.
- **The role, not the CLI name, is what downstream reads.** A rebound role changes which binary ran and nothing else about the contract.

### Depth

Crossing into a sub-orchestrator requires `agents.max_depth ≥ 2`. The chain's Phase 6 spawns are depth 2; a runner capped at depth 1 fails the availability check and enters the degradation protocol (`reference/loop-engine.md`).

---

## 6. Work Gate

A per-deliverable self-assessment emitted alongside the Delivery Report. It answers two questions for the reader: *what did this work have to go on*, and *which part of it should I not trust yet.*

```
WORK_GATE:
  IN  ★★★☆☆ — <what was and was not given at intake>
  FIT ★★★★★ — <scope delta, or "as requested">
  EVD ★★★★☆ — <what backs the load-bearing claims>
  OUT ★★★☆☆ — <E-rung reached, and by which check>
  RSK pass   — <exposure; `risk` blocks completion — never starred>
  CLR ★★★★★ — <named consumer, and what they get>
```

Rules:

- **Stars are per-axis and are never added, averaged, or weighted into an overall rating.** A composite is exactly what lets a bad axis be offset by good ones. There is no overall ★.
- **Assign the highest band whose complete description is true.** Bands are coarse on purpose; pseudo-precision is not evidence.
- **`n/a` replaces the stars entirely** and carries a reason. Never rendered as ★1, never counted as ★5.
- **`RSK` is `pass` or `risk`, never starred.** A floor is not a gradient. `RSK: risk` **blocks completion** — fix it, or stop and put it to the user.
- Every cell at ★★★☆☆ or below gets one line naming the reason.

For the chain specifically, `OUT` names the evidence rung the *acceptance verification* reached, not the rung the loop's own tests reached.

---

## 7. Handoff Envelopes

The chain emits `## FEATURE_LIFECYCLE_COMPLETE` when invoked directly (schema → `reference/delivery-report.md`).

When invoked by an orchestrator, it returns a handoff instead of calling other top-level skills:

```text
## FEATURE_LIFECYCLE_HANDOFF
- Step: [X/Y]
- Agent: Feature Lifecycle
- Summary: [1-3 lines]
- Key findings / decisions:
  - [phases run, Risk-Gate verdict, runner + envelope, conformance + negative pass]
- Artifacts: [file paths or "none"]
- Risks: [identified risks]
- Open questions (blocking/non-blocking):
  - [blocking: yes/no] [question]
- Pending Confirmations:
  - Trigger: [gate name if any]
  - Question: [question for the user]
  - Options: [available options]
  - Recommended: [recommended option]
- User Confirmations:
  - Q: [previous question] → A: [answer]
- Suggested next agent: [name] (reason)
- Next action: CONTINUE | VERIFY | DONE
```

A host that expects its own envelope name (`NEXUS_HANDOFF`) gets the same fields under that heading — the wrapper changes, the content does not.

**Handoff admission:** a downstream specialist may refuse a handoff that is missing a named required item, once per edge. A silently re-run step reports a smaller cost than it paid, so a bounce is recorded in the Delivery Report rather than absorbed.

---

## 8. Run Record, Journal and Activity Log

Three surfaces under `.agents/`, three jobs. The full split — including the Delivery Report as a fourth — is in `reference/run-record.md`.

**Run record** (`.agents/feature-lifecycle/runs/<run-id>/`): *this run's* analysis — one sealed document per phase carrying its outcome, findings, rejected options and the gate's measured terms, plus the artifacts that outlive their phase. Opened before the first spawn; each document sealed in the same step that records its gate verdict. Schema and write discipline → `reference/run-record.md`.

**Journal** (`.agents/feature-lifecycle.md`): record lifecycle-chain learnings only — which gate caught what, where a phase's estimate diverged from its actual cost, which upstream packet collapsed which phases. Not a run log, not a narrative diary; this run's material belongs in the run record.

```markdown
## YYYY-MM-DD - [Title]
**Phase / gate:** [where it happened]
**Insight:** [what was learned]
**Apply when:** [the future scenario this changes]
```

- **Before starting**: read `.agents/feature-lifecycle.md` and `.agents/PROJECT.md` to load prior context. Create them if missing. Also scan `.agents/feature-lifecycle/runs/*/RUN.md` for a run whose `Status` is not `shipped` — that is the resumable checkpoint `SKILL.md` § Subcommand Dispatch requires a bare invocation to surface rather than pick past.
- **Before declaring complete**: append at least one entry if the run produced a reusable insight. If it produced none, say so explicitly in the activity log and skip the write.
- **Activity log**: append `| YYYY-MM-DD | Feature Lifecycle | (action) | (files) | (outcome) |` to `.agents/PROJECT.md`.

---

## 9. Document Contract

Binds every document the chain writes: phase documents and artifacts (`reference/run-record.md`), spawn prompts (§5), handoff envelopes (§7), and the Delivery Report. It binds hardest at a boundary a reader cannot ask across — a spawn prompt, a loop contract, an AC — where an ambiguity is not resolved later, it is resolved wrongly and silently.

**Two tests; a document passes only both.**

| Test | Question | What failing it costs |
|------|----------|-----------------------|
| **Unambiguous** | Can the named reader act on this without asking a question? | A second reading exists, and nothing stops the wrong one being picked |
| **Minimal** | Delete the line — does anything become ambiguous, unrecoverable, or unverifiable? | It was restatement, and it buried the lines that carried the run |

**Disambiguate first, compress second.** Compressing an ambiguous sentence yields a shorter ambiguous sentence, and its brevity then reads as precision.

### Zero ambiguity

- **Name the actor and the object.** No bare passive where more than one agent could be the subject; no `this` / `it` with two available antecedents.
- **Every quantity is a number, a unit, and its source.** `significant`, `soon`, `large`, `most` are unwritten measurements — measure, or record `unmeasured (<why>)`.
- **Every conditional carries its else branch.** A rule whose negative case is unstated is a rule the reader completes by guessing.
- **Every claim carries its status** — `verified` with its evidence rung (§3), `unverified`, or `assumed`. An unlabeled claim is read as verified.
- **One meaning per term, fixed at first use.** A synonym introduced later reads as a second thing.
- **An uncheckable statement is made checkable or marked as an assumption** — the gate Phase 4 applies to an AC, applied to prose.

### Zero redundancy

- **One fact, one home**; everything else links to it. Two copies drift, and the reader cannot tell which is stale.
- **Cut process narration.** What was learned stays; the order it was learned in goes, unless that order produced the finding.
- **No preamble, no closing summary, no restating the request.** The artifact, the measured gate terms, and the number with its source are the document.
- **No `N/A` padding.** A row that did not run is absent, or is one line naming why (`reference/run-record.md`).

### The floor compression never crosses

Kept even where a reader "would infer" them, because inferring them wrong is the failure the chain exists to prevent: the **scope bound and non-goals** · a **number's source** · a **claim's status label** · the **reason under a rejected option**.

**The one licensed duplication:** §5 restates the spec's `non_goals` verbatim in every spawn prompt. A spawn cannot follow a link out of its own context, so there the copy *is* the single home. Duplication is licensed exactly where the reader cannot reach the original — nowhere else.

---

## 10. Git Conventions

Apply to anything the chain commits through the Ship phase.

- **Conventional Commits**: `<type>(<scope>): <description>`. Types: `feat` `fix` `docs` `style` `refactor` `perf` `test` `chore` `ci` `security`.
- Subject line under 50 characters, imperative mood ("add", not "added"/"adds").
- The body explains **why**; the diff already shows what.
- **No agent names** in commit messages, PR titles, or PR bodies. The commit records the change, not the tool that made it.
- **No session or tool metadata trailers** — no session URL, run ID, or "Generated with …" footer. This overrides harness and CLI defaults. Real Git trailers (`Fixes #123`, a human `Co-Authored-By:`) are fine.
- Commit or push only when asked. If on the default branch, branch first.
