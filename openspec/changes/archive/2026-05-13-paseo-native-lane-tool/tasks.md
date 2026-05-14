# Tasks: Paseo-Native Lane Tool

## 1. Project Scaffold

- [x] 1.1 Initialize Python package structure under `src/lane/`.
- [x] 1.2 Add CLI entrypoint named `lane`.
- [x] 1.3 Add minimal test runner and formatting/linting choices.
- [x] 1.4 Add `.lane/` to project `.gitignore`.
- [x] 1.5 Document non-goals: no non-Paseo support, no raw worktree ownership.
- [x] 1.6 Add `scripts/install.sh` for required dependency installation.

## 2. State Model

- [x] 2.1 Implement `.lane/state.yaml` read/write.
- [x] 2.2 Validate compact schema fields: `schema`, `id`, `status`, `branch`, `base`, `path`, `spec`, `review`, `pr`.
- [x] 2.3 Implement branch validation for `<type>/<slug>`.
- [x] 2.4 Infer branch type and slug from branch name.
- [x] 2.5 Add state tests for minimal valid state and invalid values.

## 3. Lane Resolution

- [x] 3.1 Resolve current directory by walking up to `.lane/state.yaml`.
- [x] 3.2 Resolve explicit filesystem paths.
- [x] 3.3 Resolve exact branch names from known lanes.
- [x] 3.4 Resolve slugs from known lanes.
- [x] 3.5 Resolve PR selectors using `#123` and PR URLs.
- [x] 3.6 Fail with candidate list on ambiguity.
- [x] 3.7 Implement `lane list` for known Paseo-backed lane states.

## 4. Paseo Integration

- [x] 4.1 Add thin wrapper for `paseo worktree create`.
- [x] 4.2 Add thin wrapper for `paseo worktree ls`.
- [x] 4.3 Add thin wrapper for `paseo worktree archive`.
- [x] 4.4 Make `lane start` use Paseo create and never `git worktree add`.
- [x] 4.5 Make `lane cleanup` and `lane abort` use Paseo archive.
- [x] 4.6 Add clear errors when Paseo CLI is unavailable or daemon is unreachable.

## 5. OpenSpec Integration

- [x] 5.1 Implement `lane init` installation of global `lane-lite` schema under `~/.local/share/openspec/schemas/lane-lite/` when missing.
- [x] 5.2 Define `lane-lite` schema with one artifact, `lane.md`.
- [x] 5.3 Map branch prefixes to OpenSpec schemas internally.
- [x] 5.4 Make `lane start` create the OpenSpec spec record for every lane.
- [x] 5.5 Make `lane finalize` require spec archive/sync before PR-ready handoff.
- [x] 5.6 Make `lane cleanup` refuse or warn on active specs.

## 6. Verification

- [x] 6.1 Implement `lane verify` command discovery: `just verify`, then `npm run verify`, then fail with guidance.
- [x] 6.2 Run verification in the Paseo workspace path from state.
- [x] 6.3 Report command, exit status, and concise output summary.
- [x] 6.4 Decide whether successful verification should update lane state now or later.

## 7. Review Orchestration

- [x] 7.1 Define expected Paseo review mode names by convention.
- [x] 7.2 Implement `lane review` to launch reviewer modes through Paseo.
- [x] 7.3 Record aggregate review result as `none`, `approve`, `comment`, or `reject`.
- [x] 7.4 Start reviewer agents detached so they can run concurrently and surface in Paseo.
- [x] 7.5 Add a foreground judge phase for the final verdict.
- [x] 7.6 Allow reviewer and judge mode names to be configured with full Paseo mode names.

## 8. Forge Finalize

- [x] 8.1 Implement GitHub remote/repo inference.
- [x] 8.2 Push branch with `gh`/git as appropriate.
- [x] 8.3 Create or update PR.
- [x] 8.4 Generate concise PR body with summary, verification, review, spec, and lane path.
- [x] 8.5 Store PR URL in state.
- [x] 8.6 Set status to `finalized` after successful handoff.

## 9. Cleanup And Abort

- [x] 9.1 Implement post-merge cleanup guardrails.
- [x] 9.2 Implement abort dirty-state guardrails.
- [x] 9.3 Close PR on abort only when explicitly safe or confirmed.
- [x] 9.4 Delete remote branch only when safe.
- [x] 9.5 Call Paseo archive as the authoritative workspace deletion path.

## 10. Documentation

- [x] 10.1 Write end-to-end workflow examples.
- [x] 10.2 Document selector resolution.
- [x] 10.3 Document branch-prefix schema mapping.
- [x] 10.4 Document required external tools: Paseo, OpenSpec, git, gh, glab, just, npm, and Python.
- [x] 10.5 Document migration guidance from old `wt` conceptually, without adding compatibility support.
- [x] 10.6 Document the install/init split and Paseo-provider-backed review flow.
