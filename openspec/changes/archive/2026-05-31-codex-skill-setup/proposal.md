# Proposal: Codex Skill Setup

## Metadata

- Change id: `codex-skill-setup`
- Status: `archived`
- Branch: `feat/codex-skill-setup`
- Worktree: `/home/d/wt/lane/codex-skill-setup`
- OpenSpec rationale:
  - changes repo bootstrap behavior surfaced by `lane init`
  - changes read-only environment diagnostics surfaced by `lane doctor`

## Intent

Make Codex CLI usable with `lane` through a global user skill rather than a
custom tool server.

## Problem

`lane` has a typed OpenCode tool setup, but Codex users currently only get
generic `AGENTS.md` guidance. Codex supports user skills, which are a lighter fit
than MCP for teaching Codex the lane workflow. Users also need `lane doctor` to
show whether that skill setup is present when Codex is installed.

## Scope

In scope:

- Add a managed global Codex skill under `~/.agents/skills/lane/SKILL.md` from
  `lane init` when `codex` is installed.
- Report the Codex skill path/action from `lane init`.
- Add a non-blocking `lane doctor` diagnostic for missing, managed, or custom
  Codex skill setup when `codex` is installed.
- Register the OpenCode tool from `lane init` when `opencode` is installed.
- Update README and focused tests.

Out of scope:

- MCP server support.
- Codex plugin packaging.
- Installing OpenCode or Codex themselves.
- Provider-specific Codex runtime assumptions beyond the global user skill file.

## Approach

Keep the skill instruction-only and user-global. Use a managed marker so `lane
init` can update generated skills while avoiding overwrites of user-owned skill
files. Keep `lane doctor` non-blocking because Codex support is useful for agents
but not required for every lane user. Gate OpenCode and Codex registration on the
corresponding CLI being present on `PATH`.

## Review Notes

- Known risks:
  - existing user-owned `~/.agents/skills/lane/SKILL.md` files will be left in
    place and reported as custom rather than overwritten
- Verification expectations:
  - focused init and doctor tests
  - full repo verification

## Archive Note

Implemented and merged in PR 32. Follow-up PR 35 moved user-level asset
installation from `lane init` to `lane install`.
