# Feature Lifecycle

A standalone Agent Skill that runs **one high-stakes feature end to end** across Claude Code, Codex CLI and agy: autonomous goal discovery, demand research, verdict, a spec with traceable acceptance criteria, parallel tech/UX design, a four-axis risk gate, a bounded implementation loop, an independent two-sided acceptance verification, and ship.

Feature Lifecycle is the heavyweight path. It is for the case where an upstream gap — a missed user need, a weak spec, a hidden architecture risk, UX friction — is materially costly to discover *after* implementation. When that is not true, a lighter chain is the correct chain.

## Install

The skill lives at `skills/feature-lifecycle/`; link that directory into each CLI's skills root.

```sh
make link     # symlink into ~/.claude, ~/.codex and ~/.gemini — skips a root that does not exist
make status   # show where it is currently linked
make unlink   # remove only the links pointing at this repo
```

`make link` never overwrites a real path already sitting at the target; it reports and stops. By hand, if you prefer:

```sh
ln -s "$PWD/skills/feature-lifecycle" ~/.claude/skills/feature-lifecycle    # Claude Code
ln -s "$PWD/skills/feature-lifecycle" ~/.codex/skills/feature-lifecycle     # Codex CLI
ln -s "$PWD/skills/feature-lifecycle" ~/.gemini/skills/feature-lifecycle    # agy
```

Then invoke it:

```
feature-lifecycle <feature description>   # goal supplied — starts at Phase 1
feature-lifecycle                         # autonomous — discovers the goal first, confirms once
feature-lifecycle bootstrap               # explicit autonomous form (aliases: auto, goal=auto)
feature-lifecycle resume                  # continue an aborted run from its last checkpoint
```

Optional arguments: `scope=Lite|Standard|Full`, `ui=`, `api_change=`, `db_change=`, `budget=`.

## Layout

`docs/index.html` is the GitHub Pages site (§ Docs site); everything else below is
relative to `skills/feature-lifecycle/`.

| File | What it holds |
|------|---------------|
| `SKILL.md` | Trigger conditions, contract, modes, subcommands, workflow, execution model, gates, output requirements |
| `reference/phase-contracts.md` | Phase 0-5 + Ship rosters, conditional agents, exit gates, chain template, topology |
| `reference/delegation-map.md` | The one table naming skills this skill does not own: which specialist each roster row prefers if installed, what it does otherwise, and the five outward routes |
| `reference/engine-roster.md` | The three engine roles (`build`/`judge`/`breadth`), their CLI bindings, the availability probe, the headless invocation contract, and what degrades when fewer than three are reachable |
| `reference/loop-engine.md` | Phase 6 driver selection, engine boundary, spawn sequence, degradation protocol, acceptance verification |
| `reference/input-contracts.md` | Upstream handoff packets and what a bare invocation must derive itself |
| `reference/delivery-report.md` | Output envelope, Delivery Report, cost profile, budget envelope, checkpoint-resume, failure escalation |
| `reference/run-record.md` | Where a run's analysis is written — the run directory, the sealed document per phase, the artifacts that outlive their phase, the write discipline, and what `resume` reads |
| `reference/contracts.md` | The operating rules the chain carries with it — precedence, loop preconditions, evidence ladder, driver availability, spawn contract, Work Gate, handoffs, run record and journal, the Document Contract every document is written to, Git |

## What a run leaves behind

Each run writes a **run record** to `.agents/feature-lifecycle/runs/<run-id>/`, committed
with the change it describes:

```
RUN.md                 index · engine roster · budget ledger · phase status · resume pointer
00-bootstrap.md …      one sealed document per phase, numbered by phase
08-ship.md
90-delivery-report.md  the emitted report, verbatim
artifacts/             acceptance-criteria · scope-boundary · measurement-contract
                       loop-contract · acceptance-matrix · ADR-NNN-<slug>
```

Every phase document carries the same four sections: `## Outcome` (the typed artifact),
`## Findings` (what the phase learned that the artifact does not carry), `## Rejected`
(options dropped, each with the reason), and `## Gate` (the exit criterion verbatim, its
measured terms, and the verdict).

The point is the middle two. The Delivery Report quotes a traceability percentage, a
Risk-Gate verdict and a conformance number, and carries none of what they were computed
from — the personas that produced no usable demand, the FMEA rows below the threshold,
the architecture the ADR rejected, the reuse scan's near-misses. Each is produced by an
expensive phase, read once, and otherwise gone. A failed gate is the clearest case:
"No-Go, returned to Phase 4" tells the re-entry nothing, so it re-derives a finding
already paid for.

Documents are sealed at the gate — failures included — and a re-entry **appends** rather
than rewrites, so the record cannot end up describing a run in which no gate ever failed.
Writes are atomic, because a truncated document that `resume` reads as a checkpoint is
worse than a missing one. Full contract → `skills/feature-lifecycle/reference/run-record.md`.

## Docs site

`docs/index.html` is a single self-contained page that visualises the chain — the
phase-by-phase rosters and exit gates, the four-axis Risk Gate, the Phase 6 spawn
sequence across the three engine lanes, the gate index, and every path that sends
work back upstream. No build step, no dependencies, one file.

```sh
make pages   # serve docs/ at http://localhost:8000 to preview
```

To publish it: **Settings → Pages → Source: Deploy from a branch → `main` / `/docs`**.
The site then lives at `https://<owner>.github.io/<repo>/`.

The page is explanatory only. `skills/feature-lifecycle/SKILL.md` and its
`reference/` files stay canonical for contracts, gates, rosters and budgets — when
one of them changes, `docs/index.html` is edited by hand to match. Nothing
generates it, so nothing silently drifts without a diff to review.

## Checks

```sh
make lint        # block on P1/P2 findings
make lint-strict # also block on advisory size findings
make selftest    # prove each check blocks, and names itself, when broken
make check       # both — the full gate
make hooks       # install the pre-commit hook — lints the staged content
                 # (lint always; selftest when tools/ changed)
```

`tools/lint.py` checks frontmatter, the capability markers, the required section
headings, size tiers, and — the one that matters for a repository like this —
**the standalone invariant (L1)**: no file may reference a `_common/` contract
path. The chain was extracted from a repository where that directory sat beside every
skill; here there is none, so such a path renders fine to a human browsing the
repo and resolves to nothing for the agent reading the skill.

`make selftest` breaks one check at a time in a scratch copy and requires the
linter to block **and to name the rule that caught it**. A checker nobody has
watched fail is indistinguishable from one that returns zero unconditionally —
and a check that only ever passes behind a neighbour's finding is no better
guarded than one nobody ran.

## Dependencies

**None.** Every roster row is work this skill owns, written in its own vocabulary — `reuse-scan`, `failure-mode-analysis`, `acceptance-verification`, and so on. The canonical rosters are `skills/feature-lifecycle/reference/phase-contracts.md` and `skills/feature-lifecycle/reference/loop-engine.md`.

`skills/feature-lifecycle/reference/delegation-map.md` is the **single** place a skill it does not own is named. It maps each row to the specialist that would be preferred if installed, and states what the chain does otherwise. It is an optimization, not a manifest: nothing downstream reads a skill name, so a stale entry cannot break a run — at worst the chain fails to find a specialist and does the work itself, against the identical exit gate. A missing specialist changes *who* does the work, never *whether* the gate is passed.

The same holds outward. The chain hands off at five points — an unmet performance AC, a stuck loop, an unbuildable must-have AC, coverage gaps, and the measurement contract still open at ship — and each is addressed to a capability rather than a skill. Where nothing is installed to receive one, it is still reported as a typed residual.

### Engines

The chain runs against three **roles**, probed once per run and bound to whichever CLIs are reachable:

| Role | Chosen for | Default CLI |
|------|-----------|-------------|
| `build` | Tool-heavy edit loops | Codex CLI |
| `judge` | Adversarial reading against a stated contract | Claude Code |
| `breadth` | Wide sweeps, long context, multimodal | agy |

The hub is whichever CLI the chain was invoked in; it owns gates, checkpoints and the report, and dispatches role work either natively or as a headless subprocess (`claude -p … --output-format json`, `codex exec … -o <file>`, pty-wrapped `agy -p`).

**None of the three is required.** A single reachable CLI is a legitimate run — roles fold by a declared fallback order, and the run records the rebinding, any simulated deliberation voice, and `engine_independence: context-only`. Two rules survive every degradation: the acceptance verification never runs on the engine that built wherever a second engine is reachable — with one CLI its independence is context-only and the report says so — and no gate threshold moves because an engine was missing. The chain never swaps an engine silently; it presents the choice with a restated cost model, or checkpoints and stops.

Full model → `skills/feature-lifecycle/reference/engine-roster.md`.

## What it guarantees

- Every phase boundary emits a typed artifact and passes a named gate.
- Design work runs parallel and reconverges at **one** risk gate before any code is written.
- The implementation loop is bounded — `≤ 6` cycles by default, `≤ 4` when Claude Code is the `build` engine — and the run carries a hard budget ceiling that checkpoints rather than overruns.
- Ship is gated on an **independent** acceptance verification: conformance (every must-have AC met) *and* a negative pass (nothing outside the declared scope was built), plus an integration-evidence pass where a real surface exists. The verifier shares neither context nor engine with the builder — and where only one engine was reachable, the report says so rather than implying otherwise.
- Every phase writes a sealed document — outcome, findings, rejected options, and the gate's measured terms — to a committed run record, so the numbers in the report can be gone behind and a failed gate is readable after the fact.
- A run that aborts resumes from its last good phase instead of restarting.
- The rollback is rehearsed, not just written — or recorded as `declared-impossible` with the reason.
- The demand the feature came from leaves as an open, stated measurement contract. The chain never marks a hypothesis closed; it refuses to ship one with no way to settle it.
- On every exit — including aborts — a Delivery Report names what is unmet and where to resume. Never a silent partial.

## Provenance

Extracted from the `apex` recipe of [`agent-skills`](https://github.com/simota/agent-skills) — renamed here for legibility — and made self-contained: the `_common/` protocol dependencies it relied on are distilled into `reference/contracts.md`. When the chain runs inside a repository that ships its own `_common/` protocol set, those originals are authoritative.
