# init-agent-opencode

Align `lane init` with the repo-local agent workflow and OpenCode tool setup.

## Acceptance

- `lane init` creates, appends, or replaces the managed `AGENTS.md` workflow
  block using current Paseo-native instructions.
- `lane init` reports OpenCode custom-tool registration status with a launcher
  that works in this repository environment.
- The OpenCode registration script recreates the installed `lane.ts` tool
  definition so stale definitions are not retained.
- Unit and lint verification pass.

## Tasks

- [x] Add managed `AGENTS.md` injection and replacement to `lane init`.
- [x] Add a typed OpenCode `lane` tool definition and registration script.
- [x] Use `python3` for documented and emitted tool-registration commands.
- [x] Cover init instruction management and tool registration with tests.
