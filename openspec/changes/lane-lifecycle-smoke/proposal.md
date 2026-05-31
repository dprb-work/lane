# Proposal: Lane Lifecycle Smoke

## Metadata

- Change id: `lane-lifecycle-smoke`
- Status: `active`
- Branch: `fix/lane-lifecycle-smoke`
- PR: `https://github.com/dprb-work/lane/pull/33`
- OpenSpec rationale:
  - changes lane lifecycle behavior before and during `lane start`
  - spans CLI guidance, git commit preflight, status UX, Paseo archive/list
    handling, and tests

## Intent

Make the default Lane lifecycle resilient when exercised from Devbox with Lane
installed in the image. The workflow should fail before mutation when git author
identity is absent, guide users toward supported branch types, clearly report an
initialized source checkout that is not a lane, and avoid relying on contextless
Paseo archive/list calls.

## Problem

The Devbox smoke flow exposed multiple lifecycle breaks before verify/review:
unsupported branch type guidance was not discoverable enough, `lane status .`
after init produced only a missing state-file error, `lane start` created a
worktree/spec before discovering git could not commit, and rollback/abort could
fail because Paseo `worktree ls/archive` did not pass repo context.

## Scope

In scope:

- List supported branch types in generated Lane agent guidance and `lane start`
  help from `SUPPORTED_BRANCH_TYPES`.
- Keep `lane init` from creating `.lane/state.yaml` while making `lane status .`
  in an initialized source checkout report that the checkout is not a lane.
- Preflight git author name/email before `lane start` creates a worktree or spec.
- Support `LANE_GIT_AUTHOR_NAME` and `LANE_GIT_AUTHOR_EMAIL` as one-shot commit
  identity overrides without writing git config.
- Pass context into Lane archive/list interactions and fall back to Paseo's daemon
  client when the installed Paseo CLI returns `cwd or repoRoot is required`.
- Add focused regression tests and run full verification.

Out of scope:

- Writing global or repo-local git config from Lane.
- Requiring a newer Paseo version when npm latest still reproduces the context
  error.
- Adding generic non-Paseo worktree fallbacks.

## Acceptance

- With no git author identity configured, `lane start chore/lane-flow-smoke
  --base main` fails before creating a worktree.
- With git author identity configured, `lane start chore/lane-flow-smoke --base
  main` reaches the initial state/spec commit or reports a later clear
  draft-PR/auth failure.
- `lane abort lane-flow-smoke --discard` archives the Paseo worktree through a
  context-aware path.
- `lane status .` after `lane init` but outside a lane reports that the repo is
  initialized but the current checkout is not a lane.

## Review Notes

- Paseo npm latest and installed version are both `0.1.87`; `paseo worktree ls
  --json` still returns `WORKTREE_LIST_FAILED: cwd or repoRoot is required`.
- Verification expectation: `uv run python scripts/verify.py`.
