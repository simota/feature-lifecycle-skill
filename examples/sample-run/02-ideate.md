---
run: 2026-08-22-checkout-guest-flow
phase: P2_IDEATE
status: sealed
gate: pass
engines: [{ role: hub, cli: claude-code }]
spawns: 1
opened: 2026-08-22T09:41Z
sealed: 2026-08-22T10:05Z
consumes: [01-discovery.md]
produces: [artifacts/visuals.json]
---

## Outcome
Two comparable candidates, drawn as mocks `M-01` and `M-02`: **A** e-mail-only guest checkout, **B** account created silently after payment.

## Findings
Expand produced five shapes; Subtract cut three that need a new identity provider.

## Rejected
- Magic-link sign-in before the basket — adds a step at the point of highest drop-off.

## Gate
≥2 comparable decision candidates — **pass** (A, B).
