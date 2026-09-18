# Feature Lifecycle Run Record

**Purpose:** Where a run's analysis lives on disk — the directory, the document per phase, the artifacts that outlive their phase, the write discipline that makes a checkpoint trustworthy, and what `resume` reads.
**Read when:** Launching an admitted, authorized run (the directory is created before the first spawn, not for an unapproved read-only proposal), sealing any phase at its exit gate, resuming an aborted run, or deciding whether something belongs here, in the journal, or in the Delivery Report.

`SKILL.md` § Always requires every phase-boundary artifact to be persisted as a resumable checkpoint. This file is what that sentence resolves to. Without it, "persist the checkpoint" names a location nobody agreed on, and `resume` reads a file whose shape nothing guarantees.

## Contents
- Why a record at all
- Where it lives
- Layout
- The document envelope
- The four sections every phase document carries
- Per-phase contents
- Standalone artifacts
- Write discipline
- What `resume` reads
- Run record vs journal vs activity log vs Delivery Report
- What never goes in
- Retention

---

## Why a Record At All

The Delivery Report is a **summary emitted to the caller**. It carries the traceability percentage, the Risk-Gate verdict, and the conformance number — and it carries none of what those numbers were computed from. The persona set that produced the decision-driving needs, the actual candidate goals not selected, the FMEA rows that scored below the RPN threshold, the reuse scan's near-misses, the architecture options the ADR rejected: each is produced by an expensive phase, read once by the next phase, and then gone.

That loss is not free in three specific ways:

1. **A failed gate is unreadable after the fact.** "Risk Gate: No-Go, returned to Phase 4" says nothing about which axis failed on what, so the re-entry re-derives the finding it already paid for.
2. **`resume` has nothing to bind.** A run that aborts at the Phase 5 boundary must re-bind the Phase 4 spec and the Phase 5 design artifacts. If they exist only in a finished conversation, the resume guarantee of `reference/delivery-report.md` is a claim with no mechanism under it — and loop precondition #4 (`reference/contracts.md` §2), *state lives outside the conversation*, is unmet at the phase level even while the loop satisfies it internally.
3. **The next Phase 0 cannot see this run.** Autonomous mode scans project state for candidate goals. A run that left a rejected alternative with a real rationale has left the next scan a candidate; a run that left only a Delivery Report has left it a title.

The run record is the fix, and it is narrow on purpose: **analysis, not a log.** It holds what the run decided and what it decided that against. It does not hold transcripts.

## Where It Lives

```
.agents/feature-lifecycle/runs/<run-id>/
```

Alongside the existing `.agents/PROJECT.md` activity log and `.agents/feature-lifecycle.md` journal (`reference/contracts.md` §8), and **committed with the change it describes**. A record that only exists on the machine that ran the chain cannot be reviewed in the PR that ships the feature, cannot be resumed by anyone else, and answers "why is this table here?" for exactly one person.

**Run id:** `YYYY-MM-DD-<goal-slug>`, where the slug is the kebab-cased goal title truncated to 40 characters. A second run the same day against the same goal appends `-2`, `-3`.

The directory is created, and `RUN.md` written, **before the first spawn** — the same bound `reference/engine-roster.md` places on recording the roster, and for the same reason: a roster written after the fact is a roster nobody could have objected to.

**In autonomous mode those two rules collide, and the id is therefore two-stage.** Phase 0's `0a SCAN` rows spawn on `breadth` (`reference/engine-roster.md` § Phase → Role Map), so the first spawn happens *before* a goal exists to name the directory after — and 0a's own findings, which signal sources were and were not reachable, need somewhere to land as they are produced.

| Stage | Id | When |
|-------|----|------|
| Provisional | `YYYY-MM-DD-bootstrap-<n>`, `<n>` counting that day's bootstrap runs from 1 | At launch, before the first spawn. `00-bootstrap.md` opens under it |
| Final | `YYYY-MM-DD-<goal-slug>` from `auto_selected_goal.title` | At the Phase 0 boundary confirm (0e), on approval — **rename the directory once, before Phase 1 opens** |

Rules on the rename:

- It happens **at most once per run**, and only on an approved boundary confirm. Every later phase opens under the final id, so nothing downstream ever sees the provisional one.
- `RUN.md` records both (`id:` and `id_provisional:`), because the Phase 0 document was written under the old name and a reader tracing it back needs the mapping.
- A **rejected** boundary confirm keeps the provisional id. The run stops, and its `00-bootstrap.md` is worth keeping — the scored candidates and the objection are exactly what the next `bootstrap` scan should not re-derive.
- The directory has not been committed at this point — the run record is committed at Ship — so the rename is a filesystem move with no history to rewrite.

Goal-supplied mode has no such stage: the title is the invocation argument, so the final id is known at launch.

## Layout

The file number is the phase number. There is no phase without a document and no document without a phase.

```
.agents/feature-lifecycle/runs/2026-08-22-checkout-guest-flow/
├── RUN.md                    index · roster · budget ledger · phase status · resume pointer
├── 00-bootstrap.md           P0  (autonomous runs only)
├── 01-discovery.md           P1
├── 02-ideate.md              P2
├── 03-verdict.md             P3
├── 04-spec.md                P4
├── 05-design.md              P5 — both tracks and the Risk Gate, which is P5's exit
├── 06-loop.md                P6
├── 07-verification.md        VERIFY
├── 08-ship.md                SHIP
├── 90-delivery-report.md     the emitted report, verbatim
└── artifacts/
    ├── acceptance-criteria.md
    ├── scope-boundary.md
    ├── measurement-contract.md
    ├── loop-contract.md
    ├── acceptance-matrix.md
    └── ADR-001-<slug>.md      (0..n)
```

A phase that did not run has no document. A conditional row that did not run is a line in its phase's document, not a missing file — "the UX track did not run because there is no UI surface" is a finding; a gap in the numbering is a puzzle.

## The Document Envelope

Every phase document opens with the same frontmatter. It exists so a reader — and `resume` — can classify the document without parsing prose.

```yaml
---
run: 2026-08-22-checkout-guest-flow
phase: P4_SPEC
status: open | sealed | abandoned
gate: pass | fail | n/a
engines: [{ role: hub, cli: claude-code }]   # a list: P3 is tri-engine,
                                             # P5 spans hub/breadth/judge, P6 is mixed
spawns: 3
opened: 2026-08-22T09:14Z
sealed: 2026-08-22T09:41Z
consumes: [03-verdict.md]
produces: [artifacts/acceptance-criteria.md, artifacts/scope-boundary.md,
           artifacts/measurement-contract.md]
---
```

- `engines` is a **list**, never a scalar. Four of the nine documents cover a phase whose rows run on more than one role — P3's three voices, P5's two tracks plus its gate axes, P6's mixed in-loop roster — and a scalar field silently records one of them as though it were all (`reference/engine-roster.md` § Phase → Role Map).
- `status: open` — the phase started and has not reached its gate. An `open` document at rest means the run stopped inside that phase.
- `status: sealed` — the gate fired and its verdict is recorded below. Sealed documents are append-only (§ Write discipline).
- `status: abandoned` — the phase was entered and then made moot, e.g. Phase 3 skipped after a Spec Handoff Packet arrived mid-run. Carries a one-line reason; never deleted.
- `gate: fail` is a **normal** value, not an error state. A run reaches Ship with failed gates in its history whenever a No-Go or an acceptance gap was caught and fixed — which is the chain working.

## The Four Sections Every Phase Document Carries

One shape, learned once, applied to all nine.

### `## Outcome`
The typed artifact the phase emitted, or a link to it under `artifacts/` where it is one. This is the part the next phase consumes and the Delivery Report summarises.

### `## Findings`
**What the phase learned that its own artifact does not carry.** The artifact is the decision; the findings are what the decision was made against and then dropped — the evidence that did not make the selected needs, the near-miss the reuse scan surfaced, the persona whose demand contradicted the others, the axis that passed at the edge of its threshold.

This is the section the chain exists to produce and the only one nothing else records. An empty `## Findings` on P0, P1 or P5 means either the phase did no work or the work was lost — and on exactly those phases, losing it is the whole cost of the phase.

### `## Rejected`
Every option considered and dropped, each with the reason. Phase 0's `rejected_alternatives`, Phase 2's subtracted candidates, Phase 3's losing voices, Phase 5's rejected architectures. Where a phase genuinely had no alternatives, write `none — <why the shape was forced>`. An empty Rejected section on a phase that had choices is itself a finding: it means the first idea shipped unexamined.

### `## Gate`
The exit criterion **verbatim** from `reference/phase-contracts.md`, the measured value for each of its terms, and the verdict. On `gate: fail`, also: which phase it returned to, and what has to change before re-entry.

Quoting the criterion rather than paraphrasing it is what makes the record auditable. A gate recorded as "traceability OK" cannot be checked against a threshold that was 85%.

## Per-Phase Contents

What each phase's `## Findings` and `## Outcome` are expected to carry beyond the common shape. The exit criteria themselves stay canonical in `reference/phase-contracts.md` — this table names what is *written down*, not what is *required to pass*.

| Document | Outcome carries | Findings worth keeping |
|----------|-----------------|------------------------|
| `00-bootstrap.md` | `auto_selected_goal` with its evidence refs and supported comparison, including unknown inputs | Every signal source that was and was not reachable; the scoring framework chosen and why; each comparison's sourced inputs, missing inputs and bias, not just the winner; `confidence: low` flags and their cause |
| `01-discovery.md` | Decision-driving needs with provenance, source, supported scope and hypothesis/observation status | Where synthetic scenarios were useful, their hypothesis status and limits; the reuse scan's near-misses — a module that *almost* covers the need is the finding that changes the design; the friction baseline's measured values |
| `02-ideate.md` | ≥2 comparable decision candidates | What Expand produced before Subtract cut it, and the cut criterion. The subtracted set is the part that never survives to the report |
| `03-verdict.md` | The verdict: option, AC seed, scope boundary, failure conditions | **Each voice's position separately**, the premise/evidence/oracle it challenged, and shared inputs. Disagreement or distinct engines alone does not establish independence. `simulated_voices` named here too |
| `04-spec.md` | Links to `acceptance-criteria.md`, `scope-boundary.md`, `measurement-contract.md`; the obligation-to-AC traceability matrix and its summary percentage | Requirements that resisted a measurable AC and how they were resolved; what `scope-cutting` removed; where the measurement contract is weak or unmeasurable, and what would have to exist |
| `05-design.md` | ADR link(s), API/schema deltas, UX direction and token summary; the four-axis Risk-Gate result | The full FMEA table including rows below the RPN threshold; the blast-radius map; the friction walkthrough's measured values; the security review's `no-surface` claims **with their evidence**; any Conditional-Go condition and who owns it |
| `06-loop.md` | Convergence reason, iteration count, cost per task, circuit-breaker status | Per cycle: what changed, what `code-review` flagged, and Δ. A loop that hit its cap is unreadable later without this; the loop-precondition verdict and the runner it was scored against |
| `07-verification.md` | Link to `acceptance-matrix.md`; obligation/AC/oracle evidence, percentage summary, `unmet_must_haves`, `unmet_required`, `non_goal_violations`, required evidence status | Every AC whose evidence sits below the E3-with-independent-oracle floor and is therefore `unverified` rather than verified; each out-of-boundary change found, and whether it was reverted or ratified — **by whom** |
| `08-ship.md` | PR link, release plan, `rollback_verified` | What rollback actually exercised, or its impossible reason, verified compensating controls and explicit residual-risk acceptance; missing evidence blocks readiness; the open `hypothesis-open` residual and where its number will be read |

## Standalone Artifacts

A thing gets its own file under `artifacts/` when **something outside the phase that wrote it reads it on its own**. That is the whole test — not size, not importance.

| Artifact | Written by | Read on its own by |
|----------|-----------|--------------------|
| `acceptance-criteria.md` | P4 | The loop contract, the acceptance verification, the Delivery Report |
| `scope-boundary.md` | P3 seeds it, P4 finalises it | Every spawn's scope bound, and the verification's negative pass |
| `measurement-contract.md` | P4 | Ship, and whoever reads the metric after the run has ended |
| `loop-contract.md` | The P5 → P6 handoff | The loop driver — it is the only thing that crosses the engine boundary, and the answer to "what was the loop actually told to do?" |
| `acceptance-matrix.md` | VERIFY | The Ship gate, and anyone auditing the claim later |
| `ADR-NNN-<slug>.md` | P5 Tech | The codebase, later features, and anyone asking why this shape |

**Adding a seventh requires naming its outside reader.** Without that test the directory drifts into a second copy of the phase documents, and then two places disagree about the same fact — which is the failure mode `reference/phase-contracts.md` avoids by refusing to restate a roster.

The four Risk-Gate axes deliberately stay inside `05-design.md`. They are one gate with one conjunctive verdict; splitting them into four files buries the `∧` that *is* the gate.

## Write Discipline

How the prose inside these documents is written — zero ambiguity, zero redundancy, and the floor compression never crosses — is `reference/contracts.md` §9. This section governs *when* a document is created, sealed and rewritten.

**Create before spawning.** The directory and `RUN.md` exist before the first spawn, carrying the resolved engine roster, the budget ceiling, and the run's mode and scope. In autonomous mode that directory carries the provisional id and is renamed once at the boundary confirm (§ Where it lives).

**Open at entry, seal at the gate.** A phase document is created with `status: open` when the phase opens. It is sealed **in the same step that records the gate verdict** — a gate verdict recorded against an unsealed document is not recorded.

**Write before the verdict is acted on, not after the work is judged good.** A phase that fails its gate is exactly the phase whose record matters most, and it is precisely the one a write-on-success habit loses.

**Sealed documents are append-only.** A phase re-entered after a failed gate does not rewrite its document; it appends:

```markdown
## Re-entry 1 — 2026-08-22T14:02Z
**Returned from:** Risk Gate (`security.unmitigated_high == 2`)
**Changed:** [what the re-entry altered]
**Gate:** [re-measured terms and the new verdict]
```

Rewriting instead of appending produces a run whose history contains no failed gate — a record that reads as though the chain got it right first time, which is both false and the opposite of what the record is for.

**Write atomically.** Write `<name>.md.tmp`, then rename into place. A run killed mid-write must not leave a truncated document that `resume` reads as a checkpoint — a half-written spec is worse than a missing one, because the missing one is detected. A run that opens or resumes a record **deletes any stale `*.md.tmp` in it first**: the record is committed, so a leftover temp file from a killed run is a truncated document entering the repository on the next `git add`.

**One writer per document.** The hub writes the run record. A spawned agent returns its work product to the hub through the declared output envelope; it does not write into the run directory. Concurrent phase rows would otherwise interleave into the same file, and `reference/contracts.md` §5 already routes every return through the hub.

## What `resume` Reads

`RUN.md` is the entry point, not the phase documents. It carries:

```markdown
# Run 2026-08-22-checkout-guest-flow
**Goal:** [title]  ·  **Mode:** bootstrap  ·  **Scope:** Standard  ·  **Status:** aborted-at-P5
**id_provisional:** 2026-08-22-bootstrap-1 (renamed at the 0e boundary confirm; omit in goal-supplied mode)

## Resume
**Last sealed:** 04-spec.md (gate: pass)
**Next phase:** P5_DESIGN
**Re-bind:** artifacts/acceptance-criteria.md, artifacts/scope-boundary.md,
             artifacts/measurement-contract.md
**Stopped because:** budget ceiling reached at 05-design.md (open)

## Authorization
[source of explicit user grant; goal or constrained goal-selection delegation; scope; action limits; approved budget ceiling]

## Engine roster
[the engine_roster block of reference/engine-roster.md]

## Budget
ceiling: [n]  ·  spent: [n]  ·  per-engine: { claude-code: n, codex: n, agy: n }

## Phases
| Phase | Document | Status | Gate | Agents |
|-------|----------|--------|------|--------|
| P1 | 01-discovery.md | sealed | pass | 4 |
| ... |
```

`feature-lifecycle resume` reads `RUN.md`, re-binds the artifacts it names, and continues from `Next phase`. It never infers the resume point by scanning the directory — a directory listing cannot distinguish a sealed phase from one killed a second before its gate.

An `open` document means that phase did not finish. Resume **re-enters that phase from its start** and appends a `## Re-entry` block; it does not delete the partial document, and it does not treat partial work as a checkpoint.

`RUN.md` is the one document that is rewritten rather than appended to — it is an index of state, not a record of events. Everything it says is derivable from the phase documents, which is what makes rewriting it safe.

## Run Record vs Journal vs Activity Log vs Delivery Report

Four surfaces, four jobs. Writing a fact into the wrong one is how each of them becomes unreadable.

| Surface | Holds | Grows with | Lifetime |
|---------|-------|-----------|----------|
| **Run record** `.agents/feature-lifecycle/runs/<id>/` | What *this run* decided, and what it decided that against | Every run | The run, plus however long its analysis is useful (§ Retention) |
| **Journal** `.agents/feature-lifecycle.md` | Learnings about **the chain itself** — which gate caught what, where an estimate diverged from actual cost, which packet collapsed which phases | Only runs that taught something reusable | Permanent |
| **Activity log** `.agents/PROJECT.md` | One line per run | Every run | Permanent |
| **Delivery Report** | The run's summary, emitted to the caller — and written to `90-delivery-report.md` | Every run | The conversation, plus the run record |

The journal stays a journal: `reference/contracts.md` §8 already says it is not a run log, and the run record is what made that restriction affordable. Before this file existed, a run with something to preserve had nowhere to put it except the journal, which is how a learnings file becomes a diary nobody reads.

The Delivery Report names the run-record path, and the run record holds the report. Either one alone leaves a dangling reference.

## What Never Goes In

- **Secrets, tokens, credentials, or customer data.** A Phase 0 `user-signal` row may read support tickets or reviews; what lands in the record is the aggregated finding, never the raw rows. The record is committed — treat every line as published to the repository, because it is.
- **Raw spawn transcripts.** The store is analysis. A transcript dump is precisely what turns a run record into something nobody opens, and the reasoning trace of a producer is `E0` on the evidence ladder (`reference/contracts.md` §3) — it is not evidence for anything the record claims.
- **The diff.** Git holds the diff. The record names the files and the reason.
- **A number with no source.** A conformance percentage, an RPN, a friction score, or a spend figure is written with what produced it. A metric whose derivation is not recoverable is decoration, and the run record is not the place to add confidence the run did not earn.

## Retention

- **Keep** the record of any run that shipped, and of any aborted run whose checkpoint is still resumable.
- **Prune** a superseded record — an aborted run whose goal a later run shipped — once the later run ships. What survives the prune is the journal entry and the activity-log line.
- **Pruning is a commit, reviewed like any other.** Deleting a run record silently is how a repository ends up with a Delivery Report referencing a run nobody can open.
- A repository that wants records out of version control sets its own `.gitignore` rule; the chain does not write one on its behalf. It does record `run_record_committed: true | false` in the Delivery Report, because a resume guarantee means something different on each side of that line.
