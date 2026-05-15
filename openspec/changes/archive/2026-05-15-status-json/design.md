# Design: Status JSON

## Metadata

- Change id: `status-json`
- Branch: `feat/status-json`
- Worktree: `/home/d/wt/lane/status-json`
- PR: `https://github.com/dprb-work/lane/pull/17`
- Related proposal: `proposal.md`

## Technical Approach

`lane status --json` resolves the lane exactly like human `lane status`, collects
the same health facts, and serializes a two-key object:

```json
{
  "state": {},
  "health": {}
}
```

This is the smallest viable path because it avoids a parallel status model and
does not widen structured-output policy for other commands in this slice.

## Goals

- Make `lane status` machine-readable on request.
- Keep the existing human text output byte-for-byte compatible apart from help
  text.

## Non-Goals

- Add structured output to other commands.
- Introduce schema versioning for CLI JSON output.
- Mutate lane state from status.

## Proposed Changes

### Surface changes

- Add `lane status --json`.
- Output stored state under `state` using the existing state serialization shape.
- Output status health under `health` using the existing `StatusHealth` fields.

### Internal changes

- Add a CLI-only JSON printer that reuses `state_to_dict` and `asdict`.
- Keep `collect_status_health` unchanged.

## Alternatives Considered

- Alternative: add a generic JSON framework for every command now.
  Why it was not chosen: the backlog still needs command-by-command semantics;
  this slice only needs status.

## Risks And Mitigations

- Risk: consumers may treat the output as a long-term versioned schema.
  Mitigation: keep the shape obvious and derived from existing lane state and
  health fields; defer broad structured-output policy to later slices.

## Verification Plan

- `pytest tests/test_cli.py -k status_json`
- `npm run verify`
