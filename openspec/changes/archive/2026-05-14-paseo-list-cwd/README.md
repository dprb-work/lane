# paseo-list-cwd

Pass the current repo path to Paseo when listing known lanes.

## Acceptance

- `lane list` works against Paseo CLI 0.1.75 even though `paseo worktree ls`
  sends an empty daemon request.
- Known-lane discovery still uses Paseo as the authoritative worktree source.
- Unit verification passes.

## Tasks

- [x] Pass the current repo path into known-lane discovery.
- [x] Fall back to Paseo's daemon client API for the CLI worktree-list cwd bug.
- [x] Cover the fallback with tests.
