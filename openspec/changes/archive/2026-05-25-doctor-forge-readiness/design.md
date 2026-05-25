# Design: Doctor Forge Readiness

## Metadata

- Change id: `doctor-forge-readiness`
- Branch: `feat/doctor-forge-readiness`
- Worktree: `/home/d/wt/lane/doctor-forge-readiness`
- PR: `https://github.com/dprb-work/lane/pull/22`
- Related proposal: `proposal.md`

## Technical Approach

Keep `lane doctor` as a read-only diagnostic command and expand only the forge
check. The simplest path is to infer the existing forge remote once, confirm the
provider CLI is available, then run a few provider-native read-only commands.

## Goals

- Detect missing or broken forge CLI auth before push/finalize/cleanup paths.
- Detect unreadable repository metadata for the inferred remote.
- Surface GitHub ruleset readability as a non-blocking diagnostic.

## Non-Goals

- Mutating repository rulesets.
- Adding provider config or new command flags.
- Reworking forge remote inference.

## Proposed Changes

### Surface changes

- `lane doctor` prints additional forge diagnostics.
- Missing forge auth or unreadable repo metadata fails doctor.
- GitHub ruleset readability issues warn, because rulesets can require admin
  permissions that are not needed for normal lane lifecycle commands.

### Internal changes

- Split the existing single forge check into remote, auth, repo access, and
  ruleset-access diagnostics.
- Use `gh auth status`, `gh repo view`, and `gh api repos/<repo>/rulesets` for
  GitHub checks.
- Use `glab auth status` and `glab repo view <repo>` for GitLab checks.

## Alternatives Considered

- Add a new `lane doctor --forge` mode:
  Rejected because the current doctor output is already compact and users need
  the readiness signal by default.
- Treat GitHub ruleset unreadability as a failure:
  Rejected because ruleset administration can be unavailable while normal PR
  lifecycle operations still work.

## Risks And Mitigations

- Risk: Provider CLIs change output formatting.
  Mitigation: rely on exit status and preserve concise stderr/stdout summaries.
- Risk: Ruleset API permissions vary.
  Mitigation: report ruleset access as warning-level only.

## Verification Plan

- `python -m pytest tests/test_doctor.py`
- `python -m pytest`
- `python -m ruff check .`
