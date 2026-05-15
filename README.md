# lane

`lane` is a Paseo-native lane lifecycle CLI for agent-driven development.

It is not a generic worktree manager. Paseo owns workspaces, worktrees, agents,
setup, services, terminals, and archive deletion. `lane` owns the small policy
surface around one coherent line of work: state, OpenSpec change creation,
verification, review orchestration, finalize, and cleanup.

## Shape

```text
Paseo    -> runtime and workspace ownership
OpenSpec -> required change record, including lightweight lanes
Providers -> OpenCode, Codex, Claude Code, or another Paseo-backed runtime
lane     -> glue and lifecycle policy
```

## State

Each attached workspace stores ignored lane-local state under `.lane/state.yaml`:

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

The `branch` type is inferred from the branch name prefix before `/`. That type
selects the OpenSpec schema. There is no public command argument for lane type or
spec schema in the initial API.

## Workflow

Install required local dependencies:

```bash
scripts/install.sh
```

For non-interactive or development installs:

```bash
scripts/install.sh --yes
scripts/install.sh --yes --dev
```

The installer owns dependency installation. It installs system tools, installs
Paseo and OpenSpec CLIs into a user-local npm prefix, installs npm dependencies,
creates a repo-local `.venv`, and installs the editable Python package there.
It links `paseo`, `openspec`, and `lane` into `~/.local/bin`; ensure that
directory is on `PATH`. `lane init` is repo bootstrap and validation.

Register the OpenCode custom tool definition from this checkout when you want
OpenCode's typed `functions.lane` surface:

```bash
python3 scripts/register_opencode_tool.py
```

The registration script renders this checkout path into `opencode/tools/lane.ts`
and recreates `~/.config/opencode/tools/lane.ts` every time. Restart OpenCode or
reload its config after registration so the tool definition refreshes.

Initialize repo support once:

```bash
lane init
```

`lane init` ensures `.lane/` is ignored, creates or updates the repo-local
`AGENTS.md` with a managed Paseo-native workflow block, installs the lightweight
OpenSpec schema if missing, reports missing tools, reports OpenCode tool
registration status, and prints Paseo version information. When the managed
`AGENTS.md` block already exists, `lane init` replaces it with the current
instructions. It errors when the installed Paseo CLI is below the minimum
supported version and warns when a newer package is available online. It does not
install or upgrade tools.

Start a new Paseo-backed lane:

```bash
lane start feat/workspace-status --base main
```

`lane start` asks Paseo to create the workspace, writes `.lane/state.yaml`, and
creates the required OpenSpec change with the schema inferred from the branch
prefix.

Attach an existing Paseo workspace to lane state:

```bash
lane attach [selector]
```

`lane attach` is for workspaces created outside `lane`, such as through Paseo UI
or another Paseo entry point. The selector can be omitted to attach the current
Paseo workspace, or it can name a workspace path, Paseo worktree name, branch,
slug, or PR/MR selector. Attach writes `.lane/state.yaml`, creates the required
OpenSpec change when no active or archived record already exists, and is
idempotent when lane state is already present.

Work from inside the Paseo workspace, then use:

```bash
lane status
lane list
lane verify
lane review
lane finalize
lane cleanup
```

`lane verify` runs `just verify` when a `justfile` defines `verify`; otherwise it
runs `npm run verify` when `package.json` has a `verify` script. Verification
reports the command, exit status, and a concise output summary without mutating
lane state.

`lane list` shows known lane state discovered from Paseo-listed worktrees. It
prints an aligned table with lane id, status, branch, review, PR, and path.

`lane review` launches Paseo-managed agents using review modes named by
convention:

```text
lane-review-security
lane-review-quality
lane-review-tests
```

Pass `--review-agent <name>` one or more times to override that list. Names are
passed through as full Paseo provider mode names; a trailing `.md` is accepted
and removed for OpenCode-style agent file names. For the OpenCode provider, a
file such as `lane-review-tests.md` is exposed to Paseo as mode
`lane-review-tests`.

Review agents run through detached `paseo run` calls, so the configured Paseo
provider owns the underlying runtime and reviewers can run concurrently. After
reviewers finish, `lane review` runs a foreground judge phase with the
`lane-review-judge` mode. Pass `--review-judge <name>` to use a different full
Paseo provider mode name. The aggregate result is stored as `none`, `approve`,
`comment`, or `reject`.

`lane finalize` refuses to proceed while `openspec/changes/<spec>` still exists,
runs verification, pushes the branch, creates or updates the GitHub PR or GitLab
MR, stores the PR/MR URL, and marks the lane `finalized`.

`lane cleanup` refuses active specs and unmerged PRs before calling Paseo archive.
Remote branch deletion requires `--delete-remote-branch` and a merged PR.

`lane abort` refuses dirty worktrees unless `--discard` is passed. Closing the PR
and deleting the remote branch require explicit `--close-pr` and
`--delete-remote-branch` flags.

## Selectors

Selectors resolve in this order as support is available:

```bash
lane status                  # infer from cwd
lane status .                # path
lane status /path/to/lane    # path
lane status feat/foo         # exact branch from known lanes
lane status foo              # slug or spec id from known lanes
lane status '#123'           # PR number from known lanes
lane status https://github.com/org/repo/pull/123
lane status https://gitlab.com/org/repo/-/merge_requests/123
```

Ambiguous known-lane matches fail with candidate branches. Non-path selectors are
resolved through the shared lane-target resolver. Existing local lane state is
preferred; when a branch or PR/MR selector resolves to an existing remote branch
without local lane state, `lane` asks Paseo to check out that branch and writes
normal lane state before running the requested command. Missing local and remote
targets fail without creating a new branch.

## Branch Schemas

Branch prefix selects the OpenSpec schema internally:

| Branch prefix | Schema |
| --- | --- |
| `feat/` | `spec-driven` |
| `fix/` | `lane-lite` |
| `docs/` | `lane-lite` |
| `chore/` | `lane-lite` |
| `test/` | `lane-lite` |

Unsupported prefixes fail with guidance. The initial command surface has no
`--type`, `--lane-type`, or `--schema` flag.

## Tools

Required external tools:

| Tool | Used for |
| --- | --- |
| Paseo | Workspace/worktree create, list, archive |
| OpenSpec | Required lane spec creation and archive workflow |
| OpenCode/Codex/Claude Code/etc. | Optional provider runtime behind Paseo |
| `just` or `npm` | Repo-defined verification command |
| `git`, `gh`, and `glab` | Forge operations and local branch state |

`gh` and `glab` are provider-specific. GitHub repos need `gh`; GitLab repos need
`glab`; one repo does not need both provider CLIs for normal finalize and cleanup
work. `lane init` reports all expected tools so missing optional capabilities are
visible early, while individual commands still fail only when the missing tool
blocks the selected provider path.

Forge provider inference is intentionally local-policy driven: remotes on
`github.com` are treated as GitHub, and any other parseable Git remote is treated
as GitLab-compatible, including self-hosted GitLab instances. Use GitHub remotes
for GitHub repos and GitLab-style remotes for everything else.

`lane` is a Python package. Paseo and OpenSpec are installed through npm as
`@getpaseo/cli` and `@fission-ai/openspec` because those CLIs are distributed as
Node packages.

`lane` does not implement non-Paseo worktree fallback behavior.

## Migration From `wt`

Treat `lane` as a new Paseo-native policy surface, not a compatibility wrapper
for `devbox-worktree` or `wt`. Paseo owns workspace paths, setup, services,
terminals, agents, and archive behavior. `lane` keeps only compact lane state,
OpenSpec obligation, verification, review aggregation, finalize, and cleanup
policy.

## Initial Change

The first comprehensive design record is archived in:

```text
openspec/changes/archive/2026-05-13-paseo-native-lane-tool/
```
