---
run: 2026-08-22-checkout-guest-flow
phase: P5_DESIGN
status: sealed
gate: pass
engines: [{ role: hub, cli: claude-code }, { role: breadth, cli: agy }, { role: judge, cli: claude-code }]
spawns: 12
opened: 2026-08-22T11:03Z
sealed: 2026-08-22T13:58Z
consumes: [artifacts/acceptance-criteria.md, artifacts/scope-boundary.md]
produces: [artifacts/visuals.json, artifacts/ADR-001-guest-order-token.md]
---

## Outcome
Design Select: **DS-A** selected by the user from DS-A and DS-B (`artifacts/visuals.json`). ADR-001 (signed order token, no account row); diagram `D-01`; screens `M-03` (one alternative) and `M-04`.

| Axis | Result |
|------|--------|
| blast_radius | Conditional-Go (receipt e-mail template shared with sign-up) |
| high_rpn_count | 0 |
| friction.gate_pass | true |
| security.unmitigated_high | 0 |

## Findings
- Design Select comparison (judge, before the user chose):

| Design | Screens | ACs drawn | New / changed / removed | Scope boundary |
|--------|---------|-----------|-------------------------|----------------|
| DS-A | 2 | AC-01, AC-02, AC-03, AC-04 | 3 / 4 / 1 | inside |
| DS-B | 1 | AC-01, AC-02 | 4 / 3 / 0 | adds persisted state |

- RPN threshold 120, declared before scoring. FM-4 (token replay) scored 96 after expiry was added.

## Rejected
- DS-B, dedicated guest step — a `guest_sessions` table outside the scope boundary and a second form before payment.
- Storing guest orders under a placeholder user row — a table nobody specified.

## Gate
`blast_radius.verdict ∈ {Go, Conditional-Go} ∧ failure_modes.high_rpn_count == 0 ∧ friction.gate_pass ∧ security.unmitigated_high == 0` — first pass **fail** (`security.unmitigated_high == 1`: order token without expiry).

## Re-entry 1 — 2026-08-22T13:20Z
**Returned from:** Risk Gate (`security.unmitigated_high == 1`)
**Changed:** order token expires after 30 days; receipt link re-issues it
**Gate:** all four terms met — **pass**
