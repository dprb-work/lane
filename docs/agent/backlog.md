# Lane Backlog

This file tracks useful deferred ideas that are not yet scoped as active
OpenSpec changes.

## Deferred Features

- Extend `lane status` health checks with optional machine-readable output and
  any additional fields discovered while designing `lane sync`.
- `lane doctor` for read-only diagnostics of Paseo, OpenSpec, OpenCode tool
  registration, forge CLI auth, verification discovery, and lane state validity.
- Structured `--json` output for status/list/verify/review/push/finalize where
  it fits the command semantics.
- Review artifact capture under ignored lane-local storage, with reviewer and
  judge outputs preserved for audit/debugging.
- PR/MR body enrichment from the archived spec, including summary, acceptance,
  and completed tasks.
- Extend `lane sync` to refresh additional external reality such as review state,
  branch/base drift, and spec status after those sources have stable APIs.
- Durable cleanup/archive summary before Paseo archive removes the workspace,
  preserving lane id, branch, PR URL, merge status, archived spec id, and removed
  agents.
- Review readiness gate for finalize, optionally refusing PR/MR handoff unless
  review is `approve` or explicitly allowed.
- `lane list` filtering, such as status, review outcome, base branch, and stale
  lanes.
- Spec archive helper that delegates to OpenSpec if the native OpenSpec archive
  flow remains too cumbersome in normal use.

## Notes

- Keep deferred ideas here until they are ready to become active
  `openspec/changes/<id>/` records.
- Do not expand an active spec with unrelated backlog items just because they are
  nearby in the lifecycle.
