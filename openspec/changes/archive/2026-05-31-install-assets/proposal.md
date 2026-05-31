# Proposal: Install Assets

## Metadata

- Change id: `install-assets`
- Status: `archived`
- Branch: `feat/install-assets`
- PR: `https://github.com/dprb-work/lane/pull/35`
- OpenSpec rationale:
  - changes public CLI behavior by adding `lane install`
  - changes repo bootstrap behavior by moving user-level assets out of `lane init`
  - packages runtime assets that must be available from installed Lane distributions

## Intent

Separate machine/user-level Lane asset installation from target-repository
initialization.

## Problem

`lane init` currently mixes repo-local bootstrap with user-level asset setup. That
makes per-repo initialization mutate global OpenSpec, OpenCode, and Codex state,
and makes installed distributions depend on source-checkout files for runtime
assets.

## Scope

In scope:

- Add `lane install` for user-level assets.
- Keep `lane init` focused on repo-local `.lane/`, `AGENTS.md`, and `paseo.json`
  bootstrap plus tool diagnostics.
- Package the lane-lite OpenSpec schema, OpenCode tool, and Codex skill under the
  Python package.
- Update installer and README guidance to run `lane install` for user assets.
- Update focused tests for the split behavior.

Out of scope:

- Installing OpenCode or Codex themselves.
- Adding provider-specific runtime configuration beyond existing managed assets.
- Changing lane start/spec selection behavior.

## Acceptance

- `lane init` no longer installs global user assets.
- `lane install` installs or refreshes the lane-lite schema and managed runtime
  integrations when their CLIs are present.
- Packaged assets are read from the installed Python package instead of source
  checkout helper scripts.
- Full repository verification passes.

## Review Notes

- Known risks:
  - wheel packaging of `assets/**/*` should be verified in an environment with
    build tooling available
- Verification expectations:
  - `PYTHONPATH=src .venv/bin/python scripts/verify.py`
  - smoke `lane install` with default and explicit target paths

## Archive Note

Implemented in PR 35.
