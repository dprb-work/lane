# Proposal: Paseo-Native Lane Tool

## Intent

Build a new `lane` CLI for the Paseo adoption workflow. The tool should preserve
the useful "one hand" experience of the existing `wt` helper while removing its
general-purpose worktree-manager responsibilities.

The new tool is for one environment and one workflow: Paseo-managed workspaces,
OpenSpec-backed lanes, and OpenCode-driven review perspectives.

## Problem

The existing `wt` helper bundles several concerns:

- git worktree creation and path layout
- lane identity and metadata
- shared environment setup
- command execution
- verification discovery
- PR/MR handoff
- review artifact assembly
- OpenSpec creation/archive
- cleanup and abort policy

Paseo now owns the runtime layer better than `wt` should. Keeping `wt` as the
worktree owner would create two competing sources of truth for workspace paths,
setup, services, agents, and archive behavior.

At the same time, Paseo does not replace the lane policy layer: it does not define
the local task identity, OpenSpec obligation, verification policy, multi-reviewer
review rhythm, finalize semantics, or cleanup/abort policy we want.

## Scope

In scope:

- New `lane` project from scratch under `~/workspace/lane`.
- Paseo-only workspace lifecycle integration.
- Minimal lane-local state under `.lane/state.yaml`.
- Required OpenSpec change record for every lane.
- `lane init` installs the global lightweight OpenSpec schema if missing.
- Branch prefix drives schema selection.
- Multi-route lane resolution: current directory, path, branch, slug, lane id,
  PR number, and PR URL.
- Verification wrapper around repo-defined commands.
- Review orchestration that invokes OpenCode reviewer agents/prompts by
  convention while leaving their definitions outside this project.
- Finalize flow that verifies, archives/syncs OpenSpec, creates/updates the PR,
  and records final lane state.
- Cleanup/abort flow that bows to Paseo archive behavior.

Out of scope:

- Non-Paseo worktree support.
- Generic `git worktree add` fallback.
- Copilot or CodeRabbit integration.
- Graphite, Git Town, or `jj` integration.
- Tracked per-repo `lane.yaml` policy files.
- User-facing arguments for lane type or spec schema.
- Owning OpenCode reviewer perspective definitions.

## User Model

A lane is one coherent line of work in a Paseo workspace. It has a branch, base,
path, OpenSpec spec record, review state, and optional PR.

`lane` should feel like a single command surface for agents:

```bash
lane start feat/add-workspace-status
lane status
lane verify
lane review
lane finalize
lane cleanup
```

The tool should infer aggressively and fail explicitly when resolution is
ambiguous.

## Naming

Use `lane`, not `wt` or `ft`.

Rationale:

- `lane` names the stable abstraction, not the implementation detail.
- `ft` is opaque and feature-biased.
- Lanes include fixes, chores, docs, refactors, and research, not just features.

Use `spec` as the direct user-facing term for the OpenSpec change record.

## OpenSpec Policy

Every lane has a spec record.

For larger lanes, use OpenSpec's default `spec-driven` schema. For small lanes
that were previously exempt, install and use a lightweight global schema with one
artifact.

The branch type is inferred from the branch prefix:

| Branch prefix | Schema |
| --- | --- |
| `feat/` | `spec-driven` |
| `fix/` | `lane-lite` |
| `docs/` | `lane-lite` |
| `chore/` | `lane-lite` |
| `test/` | `lane-lite` |
| other | fail with guidance or default to `spec-driven` after an explicit future policy decision |

The initial API intentionally has no `--type`, `--lane-type`, or `--schema` flag.

## Review Policy

Review perspectives should live in OpenCode agents or custom prompts. `lane` only
invokes them by convention and records the aggregate outcome.

The initial perspectives are expected to be defined outside this project, for
example:

- security
- code quality
- tests/coverage

Reviewer output may be written under `.lane/` by the invoking command or agent,
but that format is not part of the initial lane contract.

## Success Criteria

- `lane` can start a Paseo-backed lane without calling `git worktree add`.
- Every lane gets an OpenSpec spec record.
- Small fixes/docs/chores get a one-file spec artifact rather than exemption.
- `.lane/state.yaml` stays compact and sufficient.
- `lane finalize` refuses to complete while the OpenSpec spec is still active.
- `lane cleanup` uses Paseo archive and guards against losing active spec work.
- Agents can use the tool through a small command surface without understanding
  Paseo internals.
