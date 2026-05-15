# status-health-checks

Add read-only health facts to `lane status` so humans can see whether stored lane
state matches local and forge reality before a later `lane sync` command mutates
state.

## Scope

- Keep the existing stored lane state output.
- Append health fields for worktree cleanliness, current `HEAD`, upstream branch,
  verification freshness, spec record state, and PR/MR state.
- Report unknown facts without failing status when optional forge tools or remote
  queries are unavailable.
- Do not mutate `.lane/state.yaml`; this slice is observational only.

Out of scope:

- Structured `--json` status output.
- Writing refreshed state back to disk.
- Creating the future `lane sync` command.

## Acceptance

- `lane status` reports clean vs dirty worktree state.
- `lane status` reports current `HEAD` and upstream branch when available.
- `lane status` reports verification as missing, fresh, stale, or unknown.
- `lane status` reports whether the lane spec is active, archived, or missing.
- `lane status` reports PR/MR state when a PR URL is recorded, including merged
  state for GitHub PRs.
- Missing forge CLIs or failed remote queries produce `unknown` health values
  rather than failing the command.

## Tasks

- [x] Add a read-only status health collector.
- [x] Print status health fields from `lane status`.
- [x] Add tests for local health facts and PR merge state.
- [x] Update README and backlog notes.
