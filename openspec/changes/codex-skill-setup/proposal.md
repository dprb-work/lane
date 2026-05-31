# Proposal: Codex Skill Setup

## Metadata

- Change id: `codex-skill-setup`
- Status: `active`
- Branch: `feat/codex-skill-setup`
- Worktree: `/home/d/wt/lane/codex-skill-setup`
- OpenSpec rationale:
  - changes repo bootstrap behavior surfaced by `lane init`
  - changes read-only environment diagnostics surfaced by `lane doctor`

## Intent

Make Codex CLI usable with `lane` through a repo-local skill rather than a
custom tool server.

## Problem

`lane` has a typed OpenCode tool setup, but Codex users currently only get
generic `AGENTS.md` guidance. Codex supports repo-local skills, which are a
lighter fit than MCP for teaching Codex the lane workflow. Users also need
`lane doctor` to show whether that skill setup is present.

## Scope

In scope:

- Add a managed repo-local Codex skill under `.agents/skills/lane/SKILL.md` from
  `lane init`.
- Report the Codex skill path/action from `lane init`.
- Add a non-blocking `lane doctor` diagnostic for missing, managed, or custom
  Codex skill setup.
- Update README and focused tests.

Out of scope:

- MCP server support.
- Codex plugin packaging.
- Provider-specific Codex runtime assumptions beyond the local skill file.

## Approach

Keep the skill instruction-only and repo-local. Use a managed marker so `lane
init` can update generated skills while avoiding overwrites of user-owned skill
files. Keep `lane doctor` non-blocking because Codex support is useful for agents
but not required for every lane user.

## Review Notes

- Known risks:
  - existing user-owned `.agents/skills/lane/SKILL.md` files will be left in
    place and reported as custom rather than overwritten
- Verification expectations:
  - focused init and doctor tests
  - full repo verification
