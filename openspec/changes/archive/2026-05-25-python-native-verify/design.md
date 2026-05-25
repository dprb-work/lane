# Design: Python Native Verify

## Metadata

- Change id: `python-native-verify`
- Branch: `chore/python-native-verify`
- Worktree: `/home/d/wt/lane/python-native-verify`
- PR: `https://github.com/dprb-work/lane/pull/27`
- Related proposal: `proposal.md`

## Technical Approach

Keep npm as an external CLI installer only. Repository verification is a Python
script discovered by `lane verify`, so the repo no longer needs a root npm
manifest to run Ruff and pytest.

## Goals

- Make the checkout read as a Python project.
- Keep verification executable without npm project metadata.
- Preserve npm fallback support for downstream JavaScript target repositories.

## Non-Goals

- Replacing Paseo or OpenSpec npm distribution.
- Removing `npm run verify` discovery for target repositories.

## Proposed Changes

### Surface changes

- `lane verify` now discovers `scripts/verify.py` after `just verify` and before
  `npm run verify`.
- Root `package.json` and `package-lock.json` are removed from this repository.

### Internal changes

- `scripts/verify.py` invokes Ruff and pytest with the current Python
  interpreter.
- `scripts/install.sh` no longer runs `npm install`; it only uses npm to install
  Paseo and OpenSpec CLIs into the configured prefix.

## Alternatives Considered

- Keep `package.json` with only external CLI dependencies:
  Rejected because it still makes the repo appear to be an npm project.
- Add a `justfile` only:
  Rejected because this environment does not have `just`, and the goal is a
  Python-native verification path.

## Risks And Mitigations

- Risk: local checkouts without the dev extra installed cannot run Ruff or
  pytest.
  Mitigation: keep installer guidance on `scripts/install.sh --dev` and invoke
  checks through the repo-local `.venv` when present.

## Verification Plan

- Ruff over the full tree.
- Python verification script direct execution.
- `lane.verify.run_verify` discovery/execution path.
- Full pytest suite.
