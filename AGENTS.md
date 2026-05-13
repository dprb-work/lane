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
