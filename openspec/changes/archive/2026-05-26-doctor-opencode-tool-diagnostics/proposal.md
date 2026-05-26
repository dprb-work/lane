# Proposal: Doctor Opencode Tool Diagnostics

## Metadata

- Change id: `doctor-opencode-tool-diagnostics`
- Status: `archived`
- Branch: `feat/doctor-opencode-tool-diagnostics`
- Worktree: `/home/d/wt/lane/doctor-opencode-tool-diagnostics`
- PR: `https://github.com/dprb-work/lane/pull/29`
- OpenSpec rationale:
  - changes read-only environment diagnostics surfaced by `lane doctor`
  - updates backlog/spec state while avoiding an archive-only PR

## Intent

Make `lane doctor` report whether the OpenCode custom `lane` tool is registered
for the current checkout. Fold the completed PR-first lifecycle spec archive into
this feature branch so archive maintenance is not shipped alone.

## Problem

`lane init` tells users how to register the OpenCode tool, but `lane doctor` does
not diagnose that registration later. That leaves agents with a stale or missing
typed tool surface and no read-only health check explaining the fix.

## Scope

In scope:

- Add an OpenCode tool registration diagnostic to `lane doctor`.
- Warn for missing, unrendered, unreadable, or other-checkout registrations.
- Report ok when the installed tool points at this checkout.
- Archive the completed `pr-first-finalize-lifecycle` spec in this branch.
- Update README and backlog state.

Out of scope:

- Changing OpenCode registration behavior.
- Adding provider-specific OpenCode runtime assumptions beyond the local tool file.
- Reworking the doctor diagnostic model.

## Approach

Reuse the existing `lane.init` OpenCode registration path helpers from a new
read-only doctor check. Keep the diagnostic non-blocking because OpenCode support
is useful for agents but not required for every lane user.

## Review Notes

- Known risks:
  - installed package layouts may not contain a checkout-style path; report stale
    registrations as warnings rather than failures
- Verification expectations:
  - focused doctor tests
  - full repo verification

## Archive Note

Implemented and merged in PR 29.
