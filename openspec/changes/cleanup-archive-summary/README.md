# cleanup-archive-summary

Persist a compact cleanup archive summary before `lane cleanup` asks Paseo to
remove the lane workspace.

## Metadata

- Change id: `cleanup-archive-summary`
- Branch: `task/cleanup-archive-summary`
- Status: `active`
- OpenSpec rationale:
  - changes cleanup lifecycle behavior
  - spans CLI behavior, tests, README, and backlog state

## Intent

Keep enough durable local evidence after cleanup to know which lane was removed,
which PR was merged, which spec was archived, and which Paseo agents were
removed.

## Scope

In scope:

- Write an ignored JSON summary after cleanup gates pass and before `lane cleanup`
  asks Paseo to archive the workspace.
- Preserve lane id, branch, PR URL, merge status, archived spec id, source path,
  archive status, and removed Paseo agents.
- Leave a `pending` summary behind when Paseo archive fails after cleanup gates
  pass, then update it to `archived` on successful archive.
- Keep existing cleanup gates unchanged.

Out of scope:

- New cleanup flags.
- Cleanup/abort JSON output.
- Remote branch deletion policy changes.

## Tasks

- [x] Confirm scope still matches the backlog item.
- [x] Implement archive summary capture.
- [x] Add focused success-path test.
- [x] Add focused archive-failure pending-summary test.
- [x] Update README and backlog notes.
- [x] Run verification.
