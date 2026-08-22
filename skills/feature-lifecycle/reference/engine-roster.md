# Feature Lifecycle Engine Roster

**Purpose:** The three engine roles the chain runs against, how they bind to real CLIs, how a run probes for them, how each is invoked from the hub, and what changes when fewer than three are reachable.
**Read when:** Before the first spawn of any run, at the Phase 3 verdict, at the Phase 5 → 6 handoff, or before the acceptance verification. Who performs a row — an installed specialist, or the chain itself — is `reference/delegation-map.md`; it never changes which engine the row runs on.

## Contents
- Roles, not preferences
- Hub versus role
- Availability probe
- Role resolution
- Invocation contract
- Hard rules
- Phase → role map
- Degradation
- Cost and recording

---

## Roles, Not Preferences

The chain names three **roles**. A role is a property of the work, not a brand loyalty: it says what the work needs, and the roster says which CLI currently supplies it.

| Role | The work it is chosen for | Default CLI | Why that default |
|------|---------------------------|-------------|------------------|
| `build` | Code generation under a tool-heavy edit loop — write, run, read the failure, write again | **Codex CLI** | Highest edit-loop throughput per unit of budget; the in-loop roster is the bulk of any run's spend |
| `judge` | Adversarial reading against a stated contract — conformance, refutation, scope violation, risk | **Claude Code** | The gate work is meaning-level judgment, where the failure mode is a plausible-but-wrong pass, not a slow one |
| `breadth` | Wide sweeps and long context — whole-repo scans, blast radius, multimodal UX, research synthesis | **agy** (Gemini) | Long-context and multimodal branches are where a wide read beats a deep one |

The defaults are bindings, not identities. A probe that cannot reach the default rebinds the role and **records** it; nothing downstream reads the CLI name, everything reads the role.

## Hub Versus Role

The **hub engine** is whichever CLI the chain was invoked in. It is detected once (`reference/contracts.md` §5) and it never changes mid-run.

The hub owns what cannot be delegated: phase sequencing, every gate verdict, the checkpoint writes, the budget ledger, and the Delivery Report. Role work is dispatched outward.

| Situation | Dispatch |
|-----------|----------|
| The role's CLI **is** the hub | Native spawn API — `Agent(...)` / `spawn_agent` / `/agent` |
| The role's CLI **is not** the hub | Headless shell-out per the invocation contract below, one process per spawn |

A cross-engine spawn is a subprocess, not an agent-to-agent handoff. It carries the same spawn prompt non-negotiables, returns through a file or a declared stdout format, and is merged by the hub — the hub-and-spoke rule of `SKILL.md` § Core Contract holds across engines exactly as it holds within one.

## Availability Probe

Run **once, before the first spawn**, and cache the result for the run.

| CLI | Probe | Reachable when |
|-----|-------|----------------|
| Claude Code | `command -v claude && claude --version` | Exit 0 and a version string on stdout |
| Codex CLI | `command -v codex && codex --version` | Exit 0 and a version string; a PATH-alias warning on stderr is **not** a failure |
| agy | `command -v agy && agy --version` | Exit 0 and a version string |

Two probe results are not the same thing and must not be collapsed:

- **Absent** — the binary is not on PATH. Rebind the role.
- **Present but unusable** — the binary answers, but a role spawn fails on auth, quota, or config. This is a *transient* blocker; it is surfaced through the degradation protocol (`reference/loop-engine.md`) with its abort-and-resume option, not silently rebound.

An empty capture from a reachable CLI is a **capture failure** first — one typed repair retry — never a task failure (`reference/contracts.md` §5).

## Role Resolution

1. Probe → the reachable set.
2. Bind each role to its default CLI where reachable.
3. Where the default is absent, walk the role's fallback order:

   | Role | Fallback order |
   |------|----------------|
   | `build` | codex → claude → agy |
   | `judge` | claude → codex → agy |
   | `breadth` | agy → claude → codex |

4. Apply the hard rules below. A rule that cannot be satisfied triggers the matching degradation row, recorded — never worked around.
5. **Write the resolved roster into the Delivery Report before the first spawn.** A roster reported after the fact is a roster nobody could have objected to.

## Invocation Contract

Verified against Claude Code 2.1.x, Codex CLI (`codex exec`), and agy 1.1.x. Every non-hub spawn runs with an absolute working directory and an absolute artifact path.

| CLI | Headless invocation | Authoritative output | Trap |
|-----|--------------------|----------------------|------|
| Claude Code | `claude -p '<prompt>' --output-format json --model <model> --add-dir <abs ws> --permission-mode <mode>` | stdout, parsed as JSON | Bare `-p` prints prose; without `--output-format json` there is nothing to parse deterministically |
| Codex CLI | `codex exec '<prompt>' -o <abs artifact> --cd <abs ws> [-m <model>] [-s workspace-write]` | The `-o` file | Reading the transcript instead of the artifact. `--output-schema <file>` pins the response shape when the role returns structured data |
| agy | `agy -p '<prompt>' --output-format json` **inside a real pty** (e.g. `python3 -c 'import pty,sys; pty.spawn(sys.argv[1:])' agy -p ...`) | An artifact file or a sentinel the prompt instructs the agent to write | Bare `agy -p` and `script -q /dev/null` **fail silently** — `exit 0` with empty stdout also describes a successful run, so the exit code cannot classify it. `--json-schema` enforces structured output |

Concurrency: cross-engine spawns run as background processes and are joined by the hub. The `≤11` concurrent cap of `SKILL.md` § Sub-Orchestration counts every spawn, hub-native and subprocess alike.

## Hard Rules

1. **`acceptance-verification.engine != build.engine` wherever a second engine is reachable.** The acceptance verification never runs on the engine that built. Independence at this gate is *model* independence, not merely context independence — a fresh context on the same model reproduces the same blind spot, and the negative pass exists precisely to catch what the builder could not see. When only one engine is reachable, the verification still runs, and the Delivery Report records `engine_independence: context-only` rather than claiming a guarantee the run did not have.
2. **Phase 3's `deliberation` runs one voice per distinct engine** when three are reachable: `logic` on `judge`, `human-impact` on `breadth`, `precedent` on `build`. Three voices from one model is one model's disagreement with itself; the verdict is only worth its cost when the engines are actually three.
3. **No silent rebinding.** A role bound to something other than its default is recorded at bind time and named in the Delivery Report. The cost and convergence model is scored against a named roster.
4. **The hub never delegates orchestration.** Gates, checkpoints, the budget ledger, and the Delivery Report stay on the hub whatever the roster resolves to.
5. **Degradation changes who runs a gate, never whether it passes.** No threshold moves because an engine was missing.

## Phase → Role Map

| Phase | Work | Role | Note |
|-------|------|------|------|
| P0 · 0a SCAN | `project-scan`, `user-signal`, `metric-signal`, `competitor-gap`, `session-replay` | `breadth` | A repo-wide sweep plus external signals is the long-context case |
| P0 · 0b-0d | `goal-proposal`, `goal-scoring`, `advisory-check` | hub | Synthesis and scoring over an already-gathered corpus |
| P1 | `demand-modeling`, `evidence-validation`, `friction-baseline`, `reuse-scan` | `breadth` | The reuse scan reads the whole repository; a narrow read is how a duplicate implementation survives to Phase 6 |
| P2 | `option-generation` | hub | Four bounded turns over a fixed input |
| P3 | `deliberation` | tri-engine | `logic`=`judge` ‖ `human-impact`=`breadth` ‖ `precedent`=`build` — hard rule 2 |
| P4 | `spec-authoring`, `formal-spec`, `measurement-contract` | hub | The spec is the hub's own contract with everything downstream |
| P4 | `scope-cutting` | `judge` | YAGNI cutting is adversarial reading of a spec |
| P5 · Tech | `architecture-decision`, `api-design`, `schema-design` | hub | Architecture decisions bind the hub's own artifact chain |
| P5 · UX | `ux-direction` and its sub-roster | `breadth` | Multimodal, and the widest roster in the run |
| P5 · Gate | `failure-mode-analysis` | `judge` | FMEA is adversarial by construction |
| P5 · Gate | `blast-radius-analysis` | `breadth` | Blast radius is a whole-repo read |
| P5 · Gate | `friction-walkthrough` | `breadth` | Cognitive walkthrough and WCAG simulation |
| P5 · Gate | `security-review` | `judge` | Attack surface, authz, data class, and regulatory exposure — adversarial reading of what the change now exposes |
| P6 | — → `reference/loop-engine.md` § In-Loop Roster | mixed | That file owns the per-row assignment because it also owns the spawn sequence the roles appear in; splitting them would put the same rows in two files |
| VERIFY | `acceptance-verification` — conformance, negative pass, and the conditional integration-evidence pass | `judge` | Hard rule 1 |
| SHIP | `commit-and-pr`, `release-plan`, `rollback-rehearsal` | hub | Commits, PR, release plan, and proving the reverse path are the hub's to own |

A conditional row that does not run has no engine. This map is the **only** place a Phase 0-5, Verify or Ship row is assigned an engine — `reference/phase-contracts.md` carries no role annotations, so there is nothing to drift against. Phase 6 is the one exception, and it is delegated wholesale rather than copied. `reference/phase-contracts.md` remains canonical for *whether* a row runs at all, and `reference/delegation-map.md` for who performs it. **The role binds the work, not the performer** — a row the chain executes itself runs on the same engine a delegated specialist would have.

## Degradation

| Reachable | Roster | What changes |
|-----------|--------|--------------|
| **3** | Full — `build`, `judge`, `breadth` each on a distinct CLI | Nothing. This is the model the cost profile is written against |
| **2** | The missing role folds into the nearer CLI by fallback order | `deliberation` runs two real voices plus one hub-simulated voice, recorded as `simulated_voices: [<name>]`. The envelope is recomputed at the new `build` engine's rates before cycle 1; its iteration ceiling is whatever `reference/loop-engine.md` § Termination Bounds gives that engine — this file never restates it. Hard rule 1 still binds — `judge` and `build` must remain distinct, which is what the two-engine case buys |
| **1** | Every role on the hub | `deliberation` is fully simulated (`simulated_voices` lists all three). The acceptance verification runs with context isolation only: `engine_independence: context-only`. The loop ceiling is whatever `reference/loop-engine.md` § Termination Bounds gives the hub engine. Every gate and threshold is unchanged — the Phase 5 → 6 availability check reports the collapsed separation rather than blocking on it (`reference/loop-engine.md` § Engine Degradation Protocol) |

**A degraded roster is a reported condition, not a quiet one.** The single-engine run is a legitimate run — the chain is standalone by design — but a run that had one engine and reports numbers formatted like a three-engine run has misrepresented its own evidence.

When two engines are reachable and the third is *present but unusable* (auth, quota, config), prefer the degradation protocol's **abort-and-resume** over folding the role: a transient blocker resolved in ten minutes is cheaper than a run scored against the wrong roster.

## Cost and Recording

Cross-engine spawns are not fungible units. The run-level budget envelope carries a **per-engine sub-ledger**; a single total that mixes three pricing models cannot be read against any of them.

Emitted in the Delivery Report before the first spawn, and again at exit with the actuals:

```yaml
engine_roster:
  hub: claude-code | codex | agy
  probe: { claude: ok | absent | unusable, codex: ..., agy: ... }
  roles:
    build: codex
    judge: claude-code
    breadth: agy
  rebindings: []              # [(role, from, to, reason)] — empty on the full roster
  engine_independence: model | context-only
  simulated_voices: []        # Phase 3 voices with no distinct engine behind them
  spend: { claude-code: <n>, codex: <n>, agy: <n> }
```

The `runner` field of the loop-iterations row (`reference/delivery-report.md`) names the CLI that resolved to `build`, so a run's iteration and cost figures are never read against the wrong model.
