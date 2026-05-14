# shared-lane-selector-materialization

Resolve lane selectors through one shared path and materialize existing remote
targets into Paseo-owned lanes when local lane state is missing.

## Intent

Every command that accepts a lane selector should accept the same interchangeable
forms: local path, lane slug, branch, PR/MR number, and PR/MR URL. `lane review`
is the first painful case, but the resolver must be command-wide shared code, not
a review-only implementation.

The behavior should fix the predecessor failure mode where preparation assumed a
branch such as `thesis/pr-94` existed locally. Missing local state is a normal
condition; missing remote state is the error.

## Scope

- Preserve the existing selector resolution order for local lanes across all
  commands that accept a selector.
- Resolve PR/MR selectors such as `#3` or provider URLs to their source branch
  and base branch before materialization.
- When the resolved source branch already has a Paseo-listed lane with state,
  attach to that lane and run the requested command there.
- When no local lane state exists but the source branch exists remotely, ask
  Paseo to create or attach a workspace for that existing branch, then write the
  lane state needed for subsequent commands.
- When neither local lane state nor a remote source branch exists, fail clearly
  without creating a new empty branch.

Out of scope:

- Creating new task branches from selector materialization.
- Raw `git worktree` fallback behavior.
- Provider-specific review agent configuration.

## Acceptance

- `lane review #3`, `lane status #3`, and future selector-taking commands resolve
  `#3` through the same shared lane-target resolver.
- PR/MR URLs follow the same shared source-branch materialization path as `#3`.
- Branch selectors first prefer existing local lane state, then materialize the
  existing remote branch if no local lane state exists.
- Missing branch selectors fail with a precise message when no matching local
  lane and no matching remote branch exist.
- Materialized lanes use Paseo as the authoritative workspace owner and
  do not call `git worktree add` directly.
- Materialized lanes get normal `.lane/state.yaml` state and preserve the
  branch's existing OpenSpec state, whether active or archived.
- Materialized lane state stores the Paseo worktree name as `id` for later
  archive operations and keeps `spec` tied to the branch slug.
- Ambiguous local or provider selector matches fail before materialization.

## Design Notes

- Treat the branch or PR/MR source branch as the canonical lane target after
  selector resolution. The user-facing selector can be lossy; lane state should
  store the concrete branch and optional PR/MR URL.
- The selector-to-target resolver must be shared code. `lane status`, `lane
  verify`, `lane review`, `lane finalize`, cleanup/abort, future
  attach/materialize commands, and any provider-specific lookup path must call
  the same resolver instead of carrying separate PR/MR/branch implementations.
- Use provider CLIs only to resolve PR/MR metadata and remote branch existence;
  Paseo remains responsible for workspace creation and attachment.
- Prefer explicit failure over implicit branch creation during selector
  resolution. New work still starts with `lane start <branch>`.
- If Paseo does not yet expose an existing-branch materialization primitive,
  implementation should stop at the Paseo boundary and add the primitive there
  rather than adding a non-Paseo fallback in `lane`.

## Tasks

- [x] Define the shared lane-target resolution model for branches, PR/MR
  numbers, and PR/MR URLs.
- [x] Implement the lane-target model as one shared module used by all commands
  that accept lane selectors.
- [x] Add provider metadata lookup for PR/MR source branch, base branch, URL, and
  remote branch existence.
- [x] Add a Paseo wrapper for creating or attaching a workspace from an existing
  branch.
- [x] Create lane state without recreating OpenSpec records when materializing a
  remote lane target.
- [x] Make command handlers use materialized lanes only after local selector
  resolution fails.
- [x] Add tests for local lane preference, PR number resolution, remote branch
  materialization, missing remote failure, and ambiguous selector failure.
- [x] Document the shared selector materialization behavior.
