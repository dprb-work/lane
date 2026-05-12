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
OpenCode -> reviewer perspectives as agents/prompts
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

## Initial Change

The first comprehensive design record is in:

```text
openspec/changes/paseo-native-lane-tool/
```
