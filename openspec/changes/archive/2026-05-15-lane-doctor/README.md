# lane-doctor

Add the first read-only `lane doctor` diagnostics so humans and agents can see
local environment problems before lifecycle commands fail later.

## Scope

- Add `lane doctor [path]`.
- Print compact `ok`, `warn`, and `fail` diagnostics.
- Check required local tools: `git`, `paseo`, and `openspec`.
- Check Paseo CLI version command and daemon-backed worktree listing access.
- Infer the forge provider from Git remotes and check the provider CLI (`gh` for
  GitHub, `glab` for GitLab).
- Discover the configured verification command and confirm its executable is on
  the lane command `PATH`, including shared `.venv` activation.
- Validate `.lane/state.yaml` when the selected path is inside a lane.
- Keep the command read-only.

Out of scope:

- Mutating lane state or bootstrapping tools.
- OpenCode custom-tool registration diagnostics.
- Forge authentication diagnostics beyond provider CLI presence.
- Deep semantic validation of every lane state field.
- Structured `--json` output.

## Acceptance

- `lane doctor` reports each diagnostic as `ok`, `warn`, or `fail`.
- Missing required tools fail the command.
- Missing lane state outside a lane is a warning, not a failure.
- Missing verification command is a warning, while a discovered command whose
  executable is unavailable is a failure.
- Forge diagnostics choose `gh` or `glab` from the detected remote provider.
- The command performs no writes.

## Tasks

- [x] Add read-only doctor diagnostics.
- [x] Add `lane doctor [path]` CLI command.
- [x] Add tests for success, warning, failure, and CLI output behavior.
- [x] Update README and backlog notes.
