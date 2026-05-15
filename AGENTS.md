# Lane Agent Instructions

This repository defines `lane`, a Paseo-native lane lifecycle CLI. Treat Paseo as
the authoritative owner of worktrees and workspaces. Do not add generic non-Paseo
fallback workflows unless explicitly requested.

## Principles

- Keep the command surface minimal.
- Infer branch type from `<type>/<slug>`; do not add user-facing lane type or
  spec type flags in the initial design.
- Store lane-local runtime state under ignored `.lane/` directories.
- Use `spec` as the user-facing term for the OpenSpec change record.
- OpenSpec is obligatory for every lane. Small lanes use the global lightweight
  schema installed by `lane init`.
- Review perspectives live in Paseo-exposed provider modes, not in `lane` repo
  config or provider-specific assumptions.
- Prefer clear local policy over generalization.

## GitHub Setup

- Repository: `dprb-work/lane`.
- Remote: `upstream` at `https://github.com/dprb-work/lane.git`.
- Default branch: `main`; this repo uses direct feature PRs into `main`, not a
  `feature -> release -> main` promotion model.
- Merge policy: squash merge only; merge commits and GitHub rebase merges are
  disabled; delete branch on merge is enabled.
- Rulesets are active for conventional branch names on non-`main` branches and
  Conventional Commit messages on `main`.
- Branches must use `<type>/<slug>` with one of `build`, `chore`, `ci`, `docs`,
  `feat`, `fix`, `hotfix`, `perf`, `refactor`, `revert`, `style`, `task`, or
  `test`.
