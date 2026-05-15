# lane-sync

Add a narrow `lane sync` command that refreshes safe stored lane state from local
Git and forge reality. This builds on the read-only status health checks by
making state mutation explicit and separate from `lane status`.

## Scope

- Add `lane sync [selector]`.
- Reuse normal lane selector resolution.
- Clear stored verification freshness when the current `HEAD` no longer matches
  the recorded verification head, or when the recorded verification failed.
- Discover an existing GitHub PR or GitLab MR URL for the lane branch when
  `.lane/state.yaml` does not already record one.
- Mark a lane `merged` when the recorded or discovered PR/MR is merged.
- Print the refreshed state plus compact changes and warnings.

Out of scope:

- Cleanup, archive, branch deletion, or worktree removal.
- Review-state sync.
- Branch/base drift repair.
- Spec status mutation beyond future planning.
- Structured `--json` output.

## Acceptance

- `lane sync` writes refreshed `.lane/state.yaml` for the selected lane.
- `lane sync` clears stale verification records when `HEAD` changed.
- `lane sync` keeps verification unchanged when `HEAD` cannot be determined.
- `lane sync` records an existing PR/MR URL when one can be discovered.
- `lane sync` marks a lane `merged` when the known PR/MR is merged.
- Missing forge CLIs, missing remotes, or failed remote queries produce warnings
  instead of failing the command.

## Tasks

- [x] Add sync state-refresh logic.
- [x] Add `lane sync [selector]` CLI command.
- [x] Add unit and CLI tests for verification freshness, PR discovery, and merged
  status.
- [x] Update README and backlog notes.
