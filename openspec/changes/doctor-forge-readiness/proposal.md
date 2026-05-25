# Proposal: Doctor Forge Readiness

## Metadata

- Change id: `doctor-forge-readiness`
- Status: `active`
- Branch: `feat/doctor-forge-readiness`
- Worktree: `/home/d/wt/lane/doctor-forge-readiness`
- PR: `none yet`
- OpenSpec rationale:
  - changes user-facing doctor diagnostics
  - spans CLI behavior, tests, README, and backlog state

## Intent

Make `lane doctor` catch forge readiness problems before lifecycle commands try
to push, open PRs/MRs, or query merge state.

## Problem

Forge operations are now part of normal `lane start`, `lane push`, `lane
finalize`, and `lane cleanup` flows. The existing doctor check only confirms the
provider CLI is installed, so users can still discover missing auth or unreadable
repository access only after a lifecycle command fails.

## Scope

In scope:

- Add read-only forge auth diagnostics for the detected provider.
- For GitHub, check `gh auth status` and read access to the inferred repo.
- For GitHub, report repository ruleset readability without mutating rulesets.
- Keep GitLab coverage to CLI auth status and repo metadata readability.
- Add focused tests and README/backlog updates.

Out of scope:

- Ruleset mutation.
- New doctor flags or config.
- Broad provider abstraction changes.

## Approach

Extend the existing forge doctor path into a small set of provider-specific
read-only checks. Keep missing auth and unreadable repo metadata as failures,
and keep optional ruleset readability as a warning so normal lifecycle use is
not blocked by admin-only GitHub APIs.

## Review Notes

- Known risks:
  - Provider CLI output varies by version; tests assert command behavior and
    compact diagnostic details rather than full CLI output.
- Verification expectations:
  - `python -m pytest`
  - `python -m ruff check .`
