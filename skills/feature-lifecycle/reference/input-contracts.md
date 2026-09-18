# Feature Lifecycle Input Contracts

**Purpose:** What an upstream handoff packet collapses, what it never relaxes, and what a bare invocation must derive for itself.
**Read when:** A packet arrived with the invocation, or you are deciding how much discovery a bare `feature-lifecycle <goal>` owes.

## Contents
- The contract rule
- Spec Handoff Packet
- Clone Handoff Packet
- Charter roster
- No packet supplied
- Downstream handoffs

---

## The Contract Rule

First apply `SKILL.md` § Trigger Guidance; a packet is not a reason to launch a heavyweight run. For an admitted run, consuming a packet does **not** relax any chain gate. The Risk Gate, the acceptance verification, and the budget envelope run unchanged. What upstream removes is **re-derivation**, never **verification**.

The corollary binds in the other direction too: the chain does not re-litigate a settled direction. If it discovers a **must-have AC that is unbuildable as written**, it returns to the spec owner rather than reinterpreting the AC locally.

Record which packet was consumed and which phases it collapsed in the Delivery Report, so the run's phase count reads correctly against its cost.

---

## Spec Handoff Packet

Emitted by an upstream specification dialogue that locked a spec — whichever skill or human produced it. Fields the chain consumes:

| Field | Effect on the chain |
|-------|----------------|
| `acceptance_criteria` | Becomes the Phase 4 AC set directly. `spec-authoring` **validates** traceability rather than authoring it |
| `non_goals` | Becomes the scope bound on every spawn, and the input to the acceptance verification's negative pass |
| `assumption_ledger` + `refutation_flags` | Phase 5 Risk-Gate inputs — `failure-mode-analysis` starts from the known assumptions, not a blank pre-mortem |
| `reuse_findings` | Seeds Phase 1 so the reuse scan is not re-run |

**Net effect: Phases 1-4 collapse to validation.** Phase 3's verdict is **skipped** — the direction was already picked and refuted upstream.

What still runs at full strength: Phase 5 design and the four-axis Risk Gate, Phase 6, the acceptance-verification passes, and the Ship rollback rehearsal. An upstream packet does not carry a measurement contract; Phase 4 authors one either way.

---

## Clone Handoff Packet

Emitted by an upstream faithful-reproduction run — whichever skill or human produced it. Fields the chain consumes:

| Field | Effect on the chain |
|-------|----------------|
| `sdr` (stack decision record) | **Constrains Phase 5 design** — the stack is locked, not re-decided |
| `parity_ceilings` | Declared constraints. A ceiling-bound behavior is **never** filed as a defect and never "fixed" by the loop |
| `parity_harness` | Joins the Phase 6 verification set, so a new feature that breaks the clone's parity fails the loop |
| `coverage_gaps` | Candidate goals in autonomous mode |

The parity-ceiling row is the one that fails silently without this contract: a loop handed a parity harness will happily repair a stack-imposed limit and move the product off its baseline, and every test still passes.

---

## Charter Roster

A multi-package charter is **not** this skill's shape — it ships **one** feature. Prefer a charter-execution path. A charter is consumed only when the user scopes it to a single package, and then only its slice of the roster.

---

## No Packet Supplied

Without a packet, apply admission and launch authorization first. An admitted run derives only the unresolved inputs; existing evidence is validated and reused, not silently re-researched.

Two rules still bind:

- **On an existing repo, Phase 1 always includes a reuse scan before design.** Building a second implementation of something the repo already ships is a Phase 1 failure discovered for the cost of a scan, or a Phase 6 failure discovered for the cost of the whole loop.
- **The Phase 3 scope boundary is authored, not implied.** Without an upstream `non_goals` list, the verdict's scope boundary is the *only* input the acceptance verification's negative pass has. A boundary written as "keep it focused" makes scope creep unprovable.

---

## Downstream Handoffs

| Destination | When | Payload |
|-------------|------|---------|
| A performance-tuning capability | A perf AC could not be met inside the envelope | The target number and the remaining budget |
| A diagnosis capability | The loop is stuck and the circuit breaker tripped | Iteration history, the failing contract item, the last good checkpoint |
| Spec owner | A must-have AC is unbuildable as written | The AC, what makes it unbuildable, and what was attempted |
| Backlog | Coverage gaps the run did not close | The gap list with a class per item |
| Whoever reads the metric | The Phase 4 measurement contract is still open at ship | The metric, the observation window, and where the number is read — reported `hypothesis-open`, never closed by the run that opened it |

Each is a typed residual in the Delivery Report, never a free-text "recommended follow-up". Where nothing is installed to receive one, it is still **reported** — the chain having no downstream is a fact about the workspace, not a reason to drop the finding (`reference/delegation-map.md` § Outward Routes).
