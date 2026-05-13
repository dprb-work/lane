# Design: Paseo-Native Lane Tool

## Architecture

`lane` is a thin local policy CLI over three existing systems:

```text
Paseo    authoritative runtime and workspace owner
OpenSpec authoritative spec/change/archive system
Providers OpenCode, Codex, Claude Code, or another runtime behind Paseo
lane     local lifecycle glue and compact state
```

The tool must avoid becoming a second implementation of Paseo worktrees or a new
workflow framework. Its value is preserving a narrow, agent-friendly command
surface.

## Project Layout

Initial implementation can use Python for speed of iteration and because the old
`wt` codebase already demonstrates the desired CLI patterns. Starting from
scratch is preferred over an in-place refactor.

Proposed layout:

```text
lane/
├── README.md
├── AGENTS.md
├── package.json
├── scripts/
│   └── install.sh
├── openspec/
│   └── changes/
│       └── paseo-native-lane-tool/
│           ├── proposal.md
│           ├── design.md
│           └── tasks.md
├── src/lane/
│   ├── __init__.py
│   ├── cli.py
│   ├── state.py
│   ├── resolve.py
│   ├── paseo.py
│   ├── openspec.py
│   ├── verify.py
│   ├── review.py
│   ├── forge.py
│   └── cleanup.py
└── tests/
```

No compatibility guarantee with the existing `devbox-worktree` implementation is
needed.

## State Model

Lane state is stored under the Paseo workspace root:

```text
.lane/state.yaml
```

The `.lane/` directory is ignored. It is the sole lane-local state location.
There is no tracked `lane.yaml` in the repo and no split with `.agent/`.

State shape:

```yaml
schema: 1
id: fix-login-redirect
status: active
branch: fix/fix-login-redirect
base: main
path: /path/to/paseo/worktree
spec: fix-login-redirect
review: none
pr: null
```

Field meanings:

| Field | Meaning |
| --- | --- |
| `schema` | State file schema version. |
| `id` | Lane slug. Same direct name used for the OpenSpec spec unless conflict handling later requires suffixing. |
| `status` | `active`, `review`, `finalized`, `merged`, `aborted`, or `cleaned`. |
| `branch` | Actual git branch. Type is inferred from prefix before `/`. |
| `base` | Base branch/ref used for diff and PR. |
| `path` | Paseo workspace/worktree path. |
| `spec` | OpenSpec change record id. User-facing term remains `spec`. |
| `review` | Aggregate review state: `none`, `approve`, `comment`, or `reject`. |
| `pr` | PR/MR URL or `null`. |

Avoid storing data that can be cheaply re-derived from Paseo, Git, OpenSpec, or
the current directory. Add fields only when a command needs durable state.

## Command Surface

Initial commands:

```bash
lane init
lane start <branch>
lane attach <selector>
lane status [selector]
lane list
lane verify [selector]
lane review [selector]
lane finalize [selector]
lane cleanup [selector]
lane abort [selector]
```

No command accepts a public lane type or spec schema argument in the initial API.
Branch type and schema mapping are inferred internally.

### `lane init`

Responsibilities:

- Ensure `.lane/` is ignored in the target repo.
- Install the global `lane-lite` OpenSpec schema if it is not present.
- Validate required tool availability without installing or upgrading tools.
- Check the installed Paseo CLI version, fail when below the minimum supported
  version, and warn when npm reports a newer current version.

Dependency installation belongs to `scripts/install.sh`, not `lane init`.
The installer uses a user-local npm prefix for Node-distributed CLIs and a
repo-local `.venv` for Python so it does not require global npm writes or system
Python package installation.

OpenSpec schema install target:

```text
~/.local/share/openspec/schemas/lane-lite/
```

The schema should contain exactly one required artifact.

Suggested schema:

```yaml
name: lane-lite
version: 1
description: Minimal lane spec for small fixes, docs, chores, and tests

artifacts:
  - id: lane
    generates: lane.md
    description: Compact intent, acceptance, and task record
    template: lane.md
    requires: []

apply:
  requires: [lane]
  tracks: lane.md
```

Suggested `lane.md` template:

```markdown
# Lane: <change-id>

## Intent

## Scope

## Acceptance

## Tasks
- [ ]
```

### `lane start <branch>`

Responsibilities:

1. Validate branch shape is `<type>/<slug>`.
2. Infer `id` from slug.
3. Infer OpenSpec schema from branch type.
4. Ask Paseo to create the worktree/workspace.
5. Create `.lane/state.yaml` in the returned workspace path.
6. Create the OpenSpec spec record in the workspace.

`lane start` must call Paseo rather than `git worktree add`.

### `lane attach <selector>`

Attach an existing Paseo workspace to lane state. This is useful when the
workspace already exists or was created from Paseo UI/mobile.

The branch name remains the source of truth for lane id and schema inference.

### `lane status [selector]`

Show compact status:

- id
- status
- branch/base
- path
- spec id and whether active/archived
- review aggregate
- PR URL
- dirty state summary

### `lane verify [selector]`

Run the repo's verification command in the Paseo workspace.

Initial command resolution should be intentionally narrow:

1. If a `justfile` exists and has `verify`, run `just verify`.
2. Else if `package.json` has a `verify` script, run `npm run verify`.
3. Else fail with guidance to add a verification command.

Do not bake in `uv`. If a repo uses `uv`, that should appear inside its verify
command, e.g. `just verify` or `npm run verify`.

Initial verification reports the command, exit status, and a concise output
summary without mutating lane state. Freshness tracking can be added later if a
finalize policy needs durable verification timestamps.

### `lane review [selector]`

Launch configured Paseo review modes. Provider-specific definitions are not lane
config and are not tracked in this repo.

Default reviewer modes:

```text
lane-review-security
lane-review-quality
lane-review-tests
```

Review flow:

1. Start all reviewer modes with detached `paseo run --detach --json` calls.
2. Wait for each reviewer with `paseo wait <agent-id>`.
3. Collect reviewer output with `paseo logs <agent-id>`.
4. Run a foreground judge mode, defaulting to `lane-review-judge`, with the
   reviewer packets.
5. Parse the judge verdict line and store the aggregate outcome in
   `.lane/state.yaml`.

`--review-agent <name>` overrides reviewers and can be repeated.
`--review-judge <name>` overrides the judge. Names are full Paseo provider mode
names; a trailing `.md` is accepted and removed for OpenCode-style agent files.

### `lane finalize [selector]`

Responsibilities:

1. Resolve lane.
2. Run `lane verify` or require a fresh successful verification if added later.
3. Ensure OpenSpec spec is archived/synced before final handoff.
4. Push branch.
5. Create or update PR/MR.
6. Write concise PR body with summary, verification, review state, spec id, and
   lane path.
7. Update state to `finalized` and store `pr` URL.

Finalize should refuse to complete if the OpenSpec spec is active.

### `lane cleanup [selector]`

Post-merge cleanup.

Responsibilities:

- Refuse or warn if the spec is still active.
- Use Paseo archive to remove the workspace/worktree and associated agents.
- Remove local branch if safe.
- Optionally delete remote branch when merged.
- Mark state as cleaned when possible, though Paseo archive may delete the
  workspace containing the state file.

### `lane abort [selector]`

Cancel work.

Responsibilities:

- Confirm dirty/discard behavior.
- Close PR/MR if one exists and policy allows.
- Delete remote branch if policy allows.
- Use Paseo archive for workspace deletion.

## Lane Resolution

Retain the flexible selector behavior from `wt` because it is high-value for
humans and agents.

Supported selectors:

```bash
lane status                  # infer from cwd
lane status .                # path
lane status /path/to/workspace
lane status feat/foo         # branch
lane status foo              # slug if unambiguous
lane status paseo/foo        # lane id shape, if later needed
lane status '#123'           # PR number
lane status https://github.com/org/repo/pull/123
```

Resolution order:

1. Existing path.
2. PR/MR URL or `#number`.
3. Current directory containing `.lane/state.yaml`.
4. Exact branch.
5. Exact slug/id.
6. Ambiguous matches fail with candidates.

All successful resolution paths must end at a Paseo workspace path.

## Paseo Integration

`lane` bows to Paseo at these boundaries:

| Boundary | Paseo owns | `lane` behavior |
| --- | --- | --- |
| Worktree creation | path, git worktree add, setup execution | call Paseo create |
| Workspace path | hash/slug layout | store returned path |
| Setup and services | `paseo.json` setup/scripts/services | report, do not reimplement |
| Agents | provider processes, modes, lifecycle, and UI visibility | invoke through Paseo only |
| Archive | worktree deletion, associated agents/terminals/storage | call Paseo archive |

Do not parse `$PASEO_HOME` internals unless there is no CLI/API alternative.

## OpenSpec Integration

Every lane has a spec record. Use `spec` consistently as the direct name in lane
state and user output.

Archive behavior is part of finalize, not cleanup:

```text
active spec -> archive/sync -> PR-ready handoff -> cleanup later
```

Cleanup must guard against active specs because Paseo archive deletes the
workspace and could make active planning state harder to recover.

## Review Integration

Perspectives belong to Paseo-exposed provider modes. `lane` should not know
whether a mode is backed by OpenCode, Codex, Claude Code, or another provider.

For OpenCode, Paseo discovers selectable OpenCode agent files and exposes them as
modes. A file named `lane-review-tests.md` maps to mode `lane-review-tests`.
Other providers can expose equivalent modes through their own Paseo integration.

Reviewers run detached and concurrently so humans can observe them in the Paseo
UI. The judge runs in the foreground because `lane review` needs a final verdict
before updating lane state.

## Forge Integration

Initial forge support can wrap `gh` only unless GitLab is immediately needed.
Keep the abstraction small:

- infer repo from git remote
- push branch
- create or update PR
- store PR URL

No Copilot reviewer, CodeRabbit, Graphite, Git Town, or `jj` integration in the
initial design.

## Why Start From Scratch

The existing `wt` code is useful reference material, but its core assumptions are
not the new tool's assumptions:

- it owns worktree root layout
- it creates worktrees directly
- it supports local-only and non-Paseo lanes
- it stores more forge/review metadata
- it has generic verification discovery

Starting fresh avoids compatibility shims and generalization pressure.
