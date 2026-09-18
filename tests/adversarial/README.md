# Adversarial evaluation — not a runtime guarantee

Baseline: `b7383dc25ac99edcf88faa80039e7bb1ea228853`.

`requests.jsonl` contains 80 authored requests, 70 boundary cases. `predictions.md` and both input corpora were frozen before canonical source edits; SHA-256 manifests detect later input changes. Their timestamps are review logs, not an independent timestamp attestation. `selection.md` explains the five selected changes. `scenarios.jsonl` adds 180 adversarial cases covering demand, independence, acceptance, root-cause return edges, resume, authorization, forced alternatives, risk, rollback, budget, specialists and measurement.

`after-policy-review.jsonl` records the reviewer's reading of the changed contract. **It is not output from Codex, Claude, agy, or a live agent run.** The exact agreement with authored routes is not an empirical classifier accuracy claim. Eight underspecified requests remain `clarify`; heavy eligibility does not authorize launch. R76 remains unchanged-correct because the existing user-precedence rule already honors its explicit no-build request, despite the more pessimistic frozen risk annotation.

```sh
python3 tests/adversarial/evaluate.py --selftest
python3 tests/adversarial/evaluate.py --responses tests/adversarial/after-policy-review.jsonl
python3 tests/adversarial/evaluate.py --export-prompts /tmp/feature-requests.jsonl
```

For an actual selection evaluation, give the exported request-only prompts and a combined skill listing to a separately configured runner, **not** the golden labels, predicted paths or response file. Preserve the real engine/model/version, input listing order and action/artifact traces; score those observations with `--responses`. An `engine-execution` observation requires engine, model, version and run_artifact metadata. The grader cannot authenticate those fields or decide whether a cited observation actually supports a claim: review the artifacts independently. Do not invoke real destructive/external actions while testing routing.

Each response is a JSON object with `id`, `method` (`manual-policy-review` or `engine-execution`), `heavy_eligible` (boolean), `path`, `launch` and `extra_routine_approvals`. The supplied response file is the example schema. A route mismatch or unauthorized bare launch is named `EVAL_ROUTE` / `EVAL_AUTH`. This is a structured-output grader, not a text linter that guarantees semantics. Its nine mutation tests verify the grader, not agent behavior.

`make lint`, `make selftest`, and `make check` retain their existing static scope. No semantic safety guarantee is added to `tools/lint.py`, no new lifecycle phase/gate/role is installed, and these evaluation files are not per-feature runtime artifacts. Real outcome measurement, specialist competence, engine calibration, resume freshness and budget enforcement require evidence beyond this fixture set.
