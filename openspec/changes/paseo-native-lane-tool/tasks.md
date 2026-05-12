# Tasks: Paseo-Native Lane Tool

## 1. Project Scaffold

- [x] 1.1 Initialize Python package structure under `src/lane/`.
- [x] 1.2 Add CLI entrypoint named `lane`.
- [x] 1.3 Add minimal test runner and formatting/linting choices.
- [x] 1.4 Add `.lane/` to project `.gitignore`.
- [x] 1.5 Document non-goals: no non-Paseo support, no raw worktree ownership.

## 2. State Model

- [x] 2.1 Implement `.lane/state.yaml` read/write.
- [x] 2.2 Validate compact schema fields: `schema`, `id`, `status`, `branch`, `base`, `path`, `spec`, `review`, `pr`.
- [x] 2.3 Implement branch validation for `<type>/<slug>`.
- [x] 2.4 Infer branch type and slug from branch name.
- [x] 2.5 Add state tests for minimal valid state and invalid values.

## 3. Lane Resolution

- [x] 3.1 Resolve current directory by walking up to `.lane/state.yaml`.
- [ ] 3.2 Resolve explicit filesystem paths.
- [ ] 3.3 Resolve exact branch names from known lanes.
- [ ] 3.4 Resolve slugs from known lanes.
- [ ] 3.5 Resolve PR selectors using `#123` and PR URLs.
- [ ] 3.6 Fail with candidate list on ambiguity.

## 4. Paseo Integration

- [ ] 4.1 Add thin wrapper for `paseo worktree create`.
- [ ] 4.2 Add thin wrapper for `paseo worktree ls`.
- [ ] 4.3 Add thin wrapper for `paseo worktree archive`.
- [ ] 4.4 Make `lane start` use Paseo create and never `git worktree add`.
- [ ] 4.5 Make `lane cleanup` and `lane abort` use Paseo archive.
- [ ] 4.6 Add clear errors when Paseo CLI is unavailable or daemon is unreachable.

## 5. OpenSpec Integration

- [ ] 5.1 Implement `lane init` installation of global `lane-lite` schema under `~/.local/share/openspec/schemas/lane-lite/` when missing.
- [ ] 5.2 Define `lane-lite` schema with one artifact, `lane.md`.
- [ ] 5.3 Map branch prefixes to OpenSpec schemas internally.
- [ ] 5.4 Make `lane start` create the OpenSpec spec record for every lane.
- [ ] 5.5 Make `lane finalize` require spec archive/sync before PR-ready handoff.
- [ ] 5.6 Make `lane cleanup` refuse or warn on active specs.

## 6. Verification

- [ ] 6.1 Implement `lane verify` command discovery: `just verify`, then `npm run verify`, then fail with guidance.
- [ ] 6.2 Run verification in the Paseo workspace path from state.
- [ ] 6.3 Report command, exit status, and concise output summary.
- [ ] 6.4 Decide whether successful verification should update lane state now or later.

## 7. Review Orchestration

- [ ] 7.1 Define expected OpenCode agent names by convention.
- [ ] 7.2 Implement `lane review` to invoke available review perspectives or report missing definitions.
- [ ] 7.3 Record aggregate review result as `none`, `approve`, `comment`, or `reject`.
- [ ] 7.4 Allow reviewer outputs to land in `.lane/` without treating them as stable API.

## 8. Forge Finalize

- [ ] 8.1 Implement GitHub remote/repo inference.
- [ ] 8.2 Push branch with `gh`/git as appropriate.
- [ ] 8.3 Create or update PR.
- [ ] 8.4 Generate concise PR body with summary, verification, review, spec, and lane path.
- [ ] 8.5 Store PR URL in state.
- [ ] 8.6 Set status to `finalized` after successful handoff.

## 9. Cleanup And Abort

- [ ] 9.1 Implement post-merge cleanup guardrails.
- [ ] 9.2 Implement abort dirty-state guardrails.
- [ ] 9.3 Close PR on abort only when explicitly safe or confirmed.
- [ ] 9.4 Delete remote branch only when safe.
- [ ] 9.5 Call Paseo archive as the authoritative workspace deletion path.

## 10. Documentation

- [ ] 10.1 Write end-to-end workflow examples.
- [ ] 10.2 Document selector resolution.
- [ ] 10.3 Document branch-prefix schema mapping.
- [ ] 10.4 Document required external tools: Paseo, OpenSpec, OpenCode, and optionally `just`/`gh`.
- [ ] 10.5 Document migration guidance from old `wt` conceptually, without adding compatibility support.
