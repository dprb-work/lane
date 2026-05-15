# Design: Lifecycle JSON Output

## Metadata

- Change id: `status-json`
- Branch: `feat/status-json`
- Worktree: `/home/d/wt/lane/status-json`
- PR: `https://github.com/dprb-work/lane/pull/17`
- Related proposal: `proposal.md`

## Technical Approach

JSON-enabled commands resolve lanes and execute side effects exactly like their
human-output equivalents, then serialize the same result data as compact JSON.
`lane status --json` collects the same health facts and serializes a two-key
object:

```json
{
  "state": {},
  "health": {}
}
```

Other commands use similarly direct shapes, such as `{"lanes": [...]}`,
`{"diagnostics": [...]}`, or lane-scoped `{"state": ..., "verification": ...}`
objects. This is the smallest viable path because it avoids a parallel output
model and generic JSON framework.

## Goals

- Make common lane lifecycle outcomes machine-readable on request.
- Keep the existing human text output byte-for-byte compatible apart from help
  text.

## Non-Goals

- Add structured output to cleanup/abort/run streaming flows.
- Introduce schema versioning for CLI JSON output.
- Mutate lane state from status.

## Proposed Changes

### Surface changes

- Add `--json` to status/list/doctor/verify/sync/review/push/finalize.
- Output stored state under `state` using the existing state serialization shape.
- Output status health under `health` using the existing `StatusHealth` fields.

### Internal changes

- Add CLI-only JSON printers that reuse `state_to_dict`, `asdict`, and existing
  result dataclasses.
- Keep command execution paths unchanged except for output formatting.

## Alternatives Considered

- Alternative: add a generic JSON framework for every command now.
  Why it was not chosen: command semantics still differ enough that direct shapes
  are clearer and smaller.

## Risks And Mitigations

- Risk: consumers may treat the output as a long-term versioned schema.
  Mitigation: keep the shape obvious and derived from existing lane state and
  health fields; defer broad structured-output policy to later slices.

## Verification Plan

- `pytest tests/test_cli.py -k json`
- `npm run verify`
