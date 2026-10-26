# Feature Lifecycle Visuals

**Purpose:** What the run draws — screen mocks, design diagrams and the candidate designs they group into, in `artifacts/visuals.json` — the rules they follow, how Design Select is recorded, and the one page that renders the whole run record for a reviewer.
**Read when:** Phase 2 has candidates that change what a person sees, Phase 5 draws candidate designs or records Design Select, the loop contract is being written, or a run exits and its record is to be reviewed.

## Contents
- Why draw at all
- What is drawn, and by which phase
- visuals.json
- Mocks
- Diagrams
- Designs and Design Select
- The run view
- What a visual never does

---

## Why Draw At All

Three decisions in the chain are made by people who did not do the work: choosing between Phase 2 candidates, choosing between Phase 5 candidate designs at Design Select, and accepting the selected design at the Risk Gate. Both are decided faster and argued about more precisely when the reader **sees** the change — the screen as it is today beside the proposed one, the component that is new beside the table that is no longer read. Prose alone hides the disagreement until the loop builds it.

The record already holds every number the Delivery Report quotes (`reference/run-record.md`). What it lacks is a way to read the run at a glance: which gate failed and was re-entered, which artifact fed which phase, what the screens look like. The run view is that reading surface; it is rendered from the record and adds no fact of its own.

## What Is Drawn, and by Which Phase

| Phase | Row | Draws | When |
|-------|-----|-------|------|
| P2 | `option-generation` | One mock per candidate that changes a screen (`option` names the candidate), so the Phase 3 voices compare the same pictures | A candidate changes what a person sees |
| P5 Tech | `architecture-decision` | A diagram of each candidate design's architecture, marking what is `new`, `changed` and `removed`; `api-design` and `schema-design` add a `data` or `flow` diagram when they run | Always for the architecture; conditional rows when they run |
| P5 UX | `prototype` | Each candidate design's screens: today, the recommended after, and per-screen alternatives | There is a UI surface |
| P5 Select | `design-selection` | Nothing new: it groups the P5 visuals into `designs`, compares them, and records the user's choice | The tracks drew ≥2 candidate designs |

Rows return their visuals to the hub in their output envelope; **the hub writes `visuals.json`** (one writer per document, `reference/run-record.md` § Write Discipline). A row that needs no visual draws none — a P2 candidate with no UI, a P5 change with one obvious component, a copy-only tweak. A missing diagram is never a gate failure; a wrong one is a finding.

## visuals.json

`artifacts/visuals.json` is the one structured artifact in the record. Its outside readers are the loop driver (the loop contract names the P5 mock and diagram ids it builds against), the acceptance verification (intent evidence for the negative pass), and the reviewer of the PR the record ships with.

```json
{
  "version": 1,
  "mocks":    [ { "id": "M-01", "phase": "P2|P5", "title": "…", "option": "A", "acs": ["AC-01"],
                  "intent": "…", "guardrails": "…", "viewport": "mobile|desktop", "height": 560,
                  "css": "…", "before": { "caption": "…", "source": "path:line", "html": "…" },
                  "after": { "caption": "…", "html": "…" },
                  "alternatives": [ { "caption": "How it differs", "html": "…" } ] } ],
  "diagrams": [ { "id": "D-01", "phase": "P2|P5", "kind": "architecture|flow|state|data", "title": "…",
                  "intent": "…", "acs": ["AC-02"], "direction": "LR|TB",
                  "nodes": [ { "id": "orders", "label": "Order service",
                               "type": "actor|component|store|external|step|state",
                               "change": "existing|new|changed|removed", "source": "path:line" } ],
                  "edges": [ { "from": "orders", "to": "db", "label": "…", "change": "new" } ] } ],
  "designs":  [ { "id": "DS-A", "title": "…", "summary": "…", "mocks": ["M-03", "M-04"], "diagrams": ["D-01"],
                  "status": "candidate|selected|rejected", "selected_by": "user|delegated", "reason": "…" } ]
}
```

Ids are `M-01`… and `D-01`…, unique across the file and never reused. A phase re-entered after a failed gate adds or replaces its own entries; the phase document's `## Re-entry` block names which. `title`, `id`, `phase`, `after` (mocks) and `kind`, `nodes` (diagrams) are required; `acs` names the ACs a P5 visual illustrates, each an id `artifacts/acceptance-criteria.md` defines, and stays empty in P2, before ACs exist. A visual's `phase` must have a document in the run.

## Mocks

A mock illustrates one decision; it is not the design file. It draws the **state that carries the idea** — the empty list, the failed payment — not every state of the flow.

- **Before** redraws the screen as the repository renders it today: copy verbatim from the locale files, the colours and type the code uses. `source` is the `path:line` it is drawn from. Omit `before` for a screen that does not exist yet.
- **After** draws the candidate (P2) or the chosen design (P5) and nothing more: the same viewport and chrome, only what changes, in the product's tokens and the user's language. It passes its own `guardrails` — a guest-checkout mock with a pre-ticked opt-in is off-scope however good it looks. Placeholder data is fictional.
- **Alternatives** (P5 only in practice) are one to four further answers to the same design question, each moving the recommended design along a different axis — placement, emphasis, density, interaction. Two that differ only in colour are one. Each `caption` names how it differs; the ones not chosen are also listed in `05-design.md` `## Rejected` with the reason.

**Markup.** Static HTML and CSS only; `css` is shared by every screen of the mock.

- No scripts, `on…` handlers, frames, objects, forms, `<link>`, `<meta>`, `<base>`, SVG animation elements, or raw-text elements (`<title>`, `<textarea>`, `<xmp>`, `<noscript>`, `<noembed>`, `<noframes>`, `<plaintext>`) — inside SVG a browser parses their content as markup.
- References in `href`, `src`, `poster` and the like, and every CSS `url()` / `image-set()` candidate, point only at `#fragments` or `data:` URIs; no `srcset`, no `@import` or `@font-face`: system fonts only.
- No HTML comments, CDATA or declarations, no unterminated tag, and no `<` inside `css` or a `<style>` element.
- At most 64 KiB of `html` and `css` per mock, alternatives included.

Screens render at their real width — `mobile` 390 px (height 844), `desktop` 1280 px shown at 40 % (height 800); `height` overrides it (120–4000) — each in a sandboxed frame under a content security policy that loads nothing. The frame and the policy are the boundary; `visuals.py check` refuses markup outside these rules and names what it found, so a mock that could not render, or would carry an outside reference into the markup handed to the loop, is caught when it is recorded.

## Diagrams

A diagram is nodes and edges; the renderer lays it out (longest-path ranks, `LR` or `TB`), so the record holds structure, not coordinates, and two diagrams of one run look alike. At most 40 nodes — a diagram that needs more is two decisions.

- `type` sets the shape: `actor` (pill), `component`, `store` (lidded), `external` (dashed), `step`, `state`.
- `change` is the point of the diagram: `new` and `changed` nodes and edges are what the loop will build, `removed` is what it will stop doing, `existing` is context. The `new` + `changed` set is the blast radius drawn; it must agree with `blast-radius-analysis` in `05-design.md`.
- `source` anchors an existing node at the `path:line` it lives at.

## Designs and Design Select

A **design** is one whole answer to the P4 ACs: every screen it changes (its mocks) and the architecture behind it (its diagrams). Alternatives inside a mock vary one screen of one design; designs differ in kind — the number of steps, a new store or a token, a new surface or an existing one. `DS-A` … `DS-D`: two to four candidates, or one with the reason no alternative existed.

- Once `designs` is recorded, every P5 mock and diagram belongs to exactly one design; P2 visuals never do.
- Before the choice every design is `candidate`. After it, exactly one is `selected` with `selected_by` — `user`, or `delegated` only when the grant explicitly delegates design choice (`reference/phase-contracts.md` § Design Select (after both tracks, before the Risk Gate)) — and every other is `rejected` with the `reason` it lost.
- `05-design.md` sealed means Design Select ran: `check` refuses a sealed P5 document whose designs are all still candidates.
- Only the selected design is handed on: its mocks keep their Copy for LLM buttons and the design gets one of its own; a rejected design's screens stay visible, marked, and are never copied for the build.

## The Run View

```sh
python3 scripts/visuals.py check  .agents/feature-lifecycle/runs/<run-id>
python3 scripts/visuals.py render .agents/feature-lifecycle/runs/<run-id> --out <dir> [--lang en|ja]
python3 scripts/visuals.py check  .agents/feature-lifecycle/runs/<run-id> --view <dir>/run.html
```

`check` reads `RUN.md`, every phase document's envelope (`reference/run-record.md` § The Document Envelope) and `visuals.json`, and refuses a `RUN.md` status, a document status or gate value outside the record's vocabulary, a `phase` that disagrees with the file number, a malformed `engines`/`consumes`/`produces` list, an unclosed flow value, a sealed document with no `## Gate`, a design rule above, two documents for one phase, and any visual rule above. `render` checks first, then writes `<dir>/run.html`, one self-contained page:

- **Header** — `RUN.md`'s goal, mode, scope and status, the resume point and the budget line.
- **Phases** — one card per phase P0 → Ship: status, gate, spawns, engines and re-entry count; phases that did not run are shown as not run, never omitted.
- **Artifact flow** — the `consumes` / `produces` envelope fields drawn as a diagram, each document toned by its gate.
- **Design Select** — one card per candidate design, side by side: its status, its screens as thumbnails, and facts computed from the record rather than written by hand — the number of screens, which ACs of `artifacts/acceptance-criteria.md` its visuals draw and which they do not, and the `new` / `changed` / `removed` count over its diagrams' nodes and edges — then who selected it or why it was rejected. Before the choice it reads "Awaiting selection"; this is the page the user chooses from.
- **Design** — every diagram: P2, then P5 grouped by design, the selected one first.
- **Screens** — every mock: P2 candidates, then P5 grouped by design, the selected one first. Each mock has a **Copy for LLM** button (and one for all): Markdown with the run id, the option, the ACs, the intent, the guardrails and every screen's markup, ready for the `frontend-implementation` spawn. It is the page's only script, allowed by hash; without script the buttons stay hidden.
- **Documents** — every phase document's sections, a failed gate opened by default, then the Delivery Report and the `artifacts/*.md` files.

The page is stamped with the SHA-256 over every source it read; `check --view` refuses a page rendered from different sources. `<dir>` must be outside the run directory: the record's layout is closed, and the page is derived, so it is regenerated rather than committed. The Delivery Report names where it was written (`reference/delivery-report.md` § Output Envelope).

Render at every exit — including aborts, where the phase cards show where the run stopped. A record `check` refuses is a record `resume` cannot trust either: fix the record, do not skip the view.

## What a Visual Never Does

- **It is not an oracle.** The acceptance verification checks ACs against independent oracles (`reference/loop-engine.md` § Acceptance Verification). A built screen that differs from the mock but meets every AC passes; one that matches the mock and misses an AC fails. In the negative pass, a built surface that appears in neither the ACs nor the recommended `after` is a candidate out-of-boundary change to examine — not proof of one.
- **It does not relax a gate.** A persuasive mock is not demand evidence (Phase 1) and not a friction result (Phase 5); synthetic pictures are hypotheses exactly as synthetic scenarios are.
- **It carries no customer data and no secrets** — the record is committed (`reference/run-record.md` § What Never Goes In).
