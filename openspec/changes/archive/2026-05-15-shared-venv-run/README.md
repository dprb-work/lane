# shared-venv-run

Archived for PR 12: https://github.com/dprb-work/lane/pull/12

Add a lane-aware command runner and shared venv setup convention so Paseo-created
worktrees can reuse the source checkout's Python environment without requiring a
per-lane dependency install.

## Intent

Paseo owns workspace and worktree creation, including `worktree.setup` from
`paseo.json`. That setup hook can link each new worktree's `.venv` to the source
checkout's shared `.venv`, but Paseo does not currently activate that environment
for arbitrary agent commands. `lane` should fill that policy gap with a narrow
execution wrapper that agents and humans can use consistently.

The feature should also remove drift between ad hoc command execution and
verification by making `lane verify` use the same lane command execution path as
`lane run`.

## Scope

- Add shared lane command execution code that runs argv in a resolved lane
  workspace.
- Activate `<workspace>/.venv` for commands when it exists.
- Add `lane run [selector] -- <command...>`.
- Refactor `lane verify` so discovery stays in `verify.py` but execution goes
  through the shared runner.
- Teach `lane init` to create or update `paseo.json` with an idempotent
  shared-venv setup command.
- Preserve unrelated `paseo.json` fields and existing setup commands.
- Document the shared venv workflow for agents and humans.

Out of scope:

- Creating or installing the shared `.venv`.
- Dependency manager integration beyond running user commands.
- Non-Paseo worktree or checkout fallback behavior.
- Agent/provider environment propagation inside Paseo.
- `lane run --json`.
- Applying venv activation to forge, cleanup, abort, finalize, or review
  commands.
- General-purpose task runner abstractions.

## API

Preferred command shape:

```bash
lane run [selector] -- <command...>
lane run -- python -m pytest
lane run fix/foo -- ruff check .
lane run . -- just verify
```

Default behavior:

- `lane run` resolves the optional selector with the existing lane resolution
  path.
- `lane run` runs in the selected lane workspace path from `.lane/state.yaml`.
- The command after `--` is passed as argv without shell interpolation.
- Child stdout and stderr stream directly to the terminal.
- The `lane run` process exits with the child command's exit code.
- Missing command argv fails with a clear usage error.

Rejected or deferred API:

- Do not accept command argv before `--`; the separator avoids ambiguity with
  lane flags and selectors.
- Do not add `--json` in this slice; streaming command output and structured
  output need a separate design.
- Do not add dependency-install flags; Paseo setup or repo-local commands own
  dependency installation.

## Venv Activation

The shared command execution helper should inspect the lane workspace before
running the child command.

When `<workspace>/.venv` exists and `<workspace>/.venv/bin` is a directory:

- Set `VIRTUAL_ENV=<workspace>/.venv`.
- Prepend `<workspace>/.venv/bin` to `PATH`.
- Remove `PYTHONHOME` from the child environment when present.

When `.venv` does not exist, or `.venv/bin` is missing, run with the normal
environment. This keeps non-Python lanes usable and makes activation an available
convention rather than a hard requirement.

The helper should be reusable by `lane verify` and other future lane-scoped
commands that intentionally execute project commands. `verify.py` should still
own verification command discovery; the shared execution helper owns how the
discovered command is run.

## Paseo Setup Integration

`lane init` should install or validate a managed `paseo.json` setup command that
links a worktree-local `.venv` to the source checkout shared `.venv`.

The managed setup command should be idempotent and carry a stable marker, for
example:

```bash
# lane:shared-venv
if [ -d "$PASEO_SOURCE_CHECKOUT_PATH/.venv" ]; then
  if [ -e "$PASEO_WORKTREE_PATH/.venv" ] && [ ! -L "$PASEO_WORKTREE_PATH/.venv" ]; then
    printf 'lane shared venv target exists and is not a symlink: %s\n' "$PASEO_WORKTREE_PATH/.venv" >&2
  else
    ln -sfn "$PASEO_SOURCE_CHECKOUT_PATH/.venv" "$PASEO_WORKTREE_PATH/.venv"
  fi
else
  printf 'lane shared venv missing: %s\n' "$PASEO_SOURCE_CHECKOUT_PATH/.venv" >&2
fi
```

Policy:

- If `paseo.json` does not exist, create a minimal config containing this setup
  command.
- If `paseo.json` exists, preserve unrelated fields.
- Preserve existing `worktree.setup` commands.
- Normalize managed `worktree.setup` to an array so command boundaries remain
  explicit and idempotent.
- Do not duplicate the managed command on repeated `lane init` runs.
- Do not fail setup when the source `.venv` is missing; warn instead so
  non-Python or not-yet-bootstrapped repos can still create lanes.
- Do not overwrite an existing real worktree `.venv` directory; warn instead.

## Code Quality Rules

- Keep the execution helper narrow: command argv, cwd, env activation, streaming,
  and return code.
- Do not build a broad subprocess framework.
- Prefer a new reusable execution module over putting runner behavior inside
  `verify.py`.
- Keep `lane verify` discovery and freshness-recording behavior unchanged except
  for the shared execution path.
- Keep parser changes local and minimal.

## Acceptance

- `lane run -- <command>` runs the command in the current lane workspace.
- `lane run <selector> -- <command>` runs the command in the selected lane
  workspace.
- `lane run` streams stdout and stderr and returns the child exit code.
- `lane run` applies `VIRTUAL_ENV`, prepends `.venv/bin` to `PATH`, and removes
  `PYTHONHOME` when `.venv/bin` exists.
- `lane run` runs normally without activation when `.venv/bin` is absent.
- `lane verify` executes through the same command execution helper as `lane run`.
- Existing verification freshness behavior remains intact.
- `lane init` creates minimal `paseo.json` with the managed setup command when
  missing.
- `lane init` appends the managed setup command to existing `paseo.json` without
  deleting unrelated fields.
- Re-running `lane init` does not duplicate the shared venv setup command.
- Existing setup commands remain ordered before the managed shared venv command
  unless implementation discovers a concrete reason to place it first.
- README documents the shared venv setup and `lane run` workflow.

## Tasks

- [x] Add shared lane command execution helper with optional `.venv` activation.
- [x] Add `lane run [selector] -- <command...>` parser and handler.
- [x] Refactor `lane verify` to execute through the shared helper.
- [x] Add `paseo.json` read/write support for `lane init`.
- [x] Make `lane init` install an idempotent shared-venv worktree setup command.
- [x] Preserve existing `paseo.json` fields and setup commands.
- [x] Add tests for `lane run` cwd, argv, exit code, output, and venv env.
- [x] Add tests proving `lane verify` uses the same execution helper.
- [x] Add tests for `lane init` creating/updating `paseo.json` idempotently.
- [x] Update README with the shared venv and `lane run` workflow.
