# Design: Doctor Opencode Tool Diagnostics

## Metadata

- Change id: `doctor-opencode-tool-diagnostics`
- Branch: `feat/doctor-opencode-tool-diagnostics`
- Worktree: `/home/d/wt/lane/doctor-opencode-tool-diagnostics`
- PR: `https://github.com/dprb-work/lane/pull/29`
- Related proposal: `proposal.md`

## Technical Approach

Add one read-only doctor diagnostic that reuses the existing OpenCode tool path
and registration-note helpers from `lane.init`. The diagnostic checks the global
tool file directly and returns `warn` rather than `fail` for registration issues.

## Goals

- Make stale or missing OpenCode typed-tool setup visible in `lane doctor`.
- Keep OpenCode support optional for users who only need the CLI.
- Avoid a separate archive-only PR for completed spec maintenance.

## Non-Goals

- Automatically registering or rewriting OpenCode config from `lane doctor`.
- Validating every OpenCode plugin API detail.
- Changing the existing `lane init` registration note.

## Proposed Changes

### Surface changes

- `lane doctor` emits an `opencode tool` diagnostic.
- Missing registrations warn with the same compact registration guidance used by
  `lane init`.

### Internal changes

- `lane.doctor` reads `~/.config/opencode/tools/lane.ts` via `lane.init` helpers.
- It warns when the file is absent, unreadable, still contains the source
  placeholder, or does not mention this checkout root.
- It reports ok when the file exists and points at this checkout.

## Alternatives Considered

- Make `lane doctor` run the registration script automatically:
  rejected because doctor is a read-only diagnostic command.
- Only check that the file exists:
  rejected because stale registrations are the failure mode this check should
  surface.

## Risks And Mitigations

- Risk: installed package layouts may not look like source checkouts.
  Mitigation: report mismatches as warnings, not failures.

## Verification Plan

- Focused doctor tests for missing, registered, and stale OpenCode tool states.
- Full repo verification through `lane verify`.
