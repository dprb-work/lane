# attach-existing-lane

Attach existing Paseo-created workspaces to `lane` state without creating a new
worktree.

## Intent

`lane attach` should make workspaces created through Paseo UI or another Paseo
entry point usable with the rest of the `lane` lifecycle. The command must treat
Paseo as the workspace owner and only add the compact lane policy state that is
missing.

## Scope

- Replace the `attach` command stub with a real command.
- Resolve existing Paseo workspaces by current directory, path, worktree name,
  branch, slug, and PR/MR selector when provider metadata is available.
- Write `.lane/state.yaml` for a selected workspace that does not already have
  lane state.
- Create the required OpenSpec change only when no active or archived record for
  the branch slug already exists.
- Preserve idempotent behavior when lane state is already present.

Out of scope:

- Creating new Paseo workspaces; that remains `lane start` or shared selector
  materialization in selector-taking commands.
- Adding non-Paseo worktree fallback behavior.

## Acceptance

- `lane attach` from inside a Paseo workspace without state writes normal lane
  state and creates the required spec.
- `lane attach <path>`, `lane attach <branch>`, and `lane attach <slug>` select
  existing Paseo-listed workspaces without materializing new worktrees.
- PR/MR selectors can attach an existing workspace for the resolved source
  branch and record provider metadata in lane state.
- Existing lane state is returned unchanged and does not recreate specs.
- Existing active or archived specs are preserved.
- Ambiguous workspace selectors fail clearly.

## Tasks

- [x] Implement the `attach` parser and handler.
- [x] Add attach workspace selection helpers.
- [x] Write lane state and create missing specs for attached workspaces.
- [x] Add CLI tests for cwd, idempotent, branch, PR, and ambiguous attach paths.
- [x] Document `lane attach` behavior.
