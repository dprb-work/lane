# init-agent-opencode

Align `lane init` with the repo-local agent workflow, OpenCode tool setup, and
provider-aware forge tooling.

## Acceptance

- `lane init` creates, appends, or replaces the managed `AGENTS.md` workflow
  block using current Paseo-native instructions.
- `lane init` reports OpenCode custom-tool registration status with a launcher
  that works in this repository environment.
- The OpenCode registration script recreates the installed `lane.ts` tool
  definition so stale definitions are not retained.
- `lane init` reports all expected tools while clarifying that `gh` is only
  needed for GitHub repos and `glab` is only needed for GitLab repos.
- Forge operations infer the provider from Git remotes or PR/MR URLs without a
  user-facing provider flag.
- GitHub remotes use `gh`; GitLab and self-hosted GitLab-compatible remotes use
  `glab`.
- Unit and lint verification pass.

## Tasks

- [x] Add managed `AGENTS.md` injection and replacement to `lane init`.
- [x] Add a typed OpenCode `lane` tool definition and registration script.
- [x] Use `python3` for documented and emitted tool-registration commands.
- [x] Cover init instruction management and tool registration with tests.
- [x] Report expected tools during init with provider-specific `gh`/`glab`
  guidance.
- [x] Infer GitHub versus GitLab-compatible forge operations from remotes and
  PR/MR URLs.
- [x] Cover GitHub, GitLab, and self-hosted GitLab-compatible forge paths with
  tests.
