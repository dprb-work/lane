# Lane: reviewer-dir-routing

## Intent

Consolidate `lane review` around a provider-neutral reviewer prompt workflow.
Lane should have a built-in single-reviewer fallback, optionally read reviewer
prompt files from a user-provided directory, route among known reviewer prompts
when multiple are present, and run a built-in judge only when more than one
reviewer ran.

## Scope

- Add a built-in default reviewer prompt asset used when no reviewer directory is
  configured or no applicable reviewer prompt is available.
- Add a built-in judge prompt asset used only to filter multiple reviewer outputs.
- Support an explicit reviewer directory setting, likely `LANE_REVIEWERS_DIR`,
  whose markdown files are reviewer prompts rather than provider-specific agent
  definitions.
- Route known reviewer prompt names such as `quality`, `tests`, `llm-smells`,
  and `security` with deterministic Lane-side rules.
- Document the optional reviewer directory in install/readme guidance without
  adding a global default path.

## Acceptance

- Without `LANE_REVIEWERS_DIR`, `lane review` uses the built-in fallback reviewer
  and does not require provider-defined review agents.
- With a reviewer directory containing one prompt file, `lane review` runs that
  reviewer and skips the judge.
- With multiple known prompt files, `lane review` selects applicable reviewers
  using Lane-side rules and runs the built-in judge only when two or more
  reviewers ran.
- If no configured prompt applies, Lane falls back to the built-in reviewer
  rather than selecting an arbitrary file.
- README/install guidance mentions the optional reviewer directory and makes clear
  that no global directory is assumed.

## Tasks

- [x] Add built-in fallback reviewer and judge prompt assets.
- [x] Add reviewer directory loading from explicit config/env.
- [x] Add deterministic routing for known reviewer prompt names.
- [x] Update `lane review` orchestration and JSON/text output as needed.
- [x] Add tests for fallback, single configured reviewer, multi-reviewer routing,
  judge gating, and no-applicable-reviewer fallback.
- [x] Update README/install guidance.
- [x] Run full verification.
