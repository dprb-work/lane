# Tasks

## Metadata

- Change id: `lane-lifecycle-smoke`
- Branch: `fix/lane-lifecycle-smoke`
- PR: `https://github.com/dprb-work/lane/pull/33`

## 1. Planning

- [x] 1.1 Reproduce and classify the Devbox lifecycle failures.
- [x] 1.2 Check installed and npm-latest Paseo behavior before choosing a
  Lane-side workaround.
- [x] 1.3 Record this OpenSpec change for PR review context.

## 2. Implementation

- [x] 2.1 Generate branch type guidance from `SUPPORTED_BRANCH_TYPES`.
- [x] 2.2 Improve initialized-but-not-a-lane `lane status` output.
- [x] 2.3 Preflight git author identity before `lane start` mutations.
- [x] 2.4 Add one-shot Lane git author environment override support.
- [x] 2.5 Pass repo/workspace context into Paseo archive/list handling and add a
  daemon-client fallback for the known context bug.

## 3. Validation

- [x] 3.1 Add focused tests for the lifecycle regressions.
- [x] 3.2 Run `uv run python scripts/verify.py`.

## 4. Review Handoff

- [x] 4.1 Push the PR branch.
- [x] 4.2 Open PR 33 against `main`.
- [x] 4.3 Address review finding by adding this OpenSpec record.
