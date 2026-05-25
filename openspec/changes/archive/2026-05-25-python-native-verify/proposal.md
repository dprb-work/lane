# Proposal: Python Native Verify

## Metadata

- Change id: `python-native-verify`
- Status: `archived`
- Branch: `chore/python-native-verify`
- Worktree: `/home/d/wt/lane/python-native-verify`
- PR: `https://github.com/dprb-work/lane/pull/27`
- OpenSpec rationale:
  - changes repo bootstrap and verification behavior
  - removes npm project metadata while retaining npm-installed external CLIs

## Intent

Keep `lane` clearly Python-native while still installing Paseo and OpenSpec as
external npm-distributed CLIs. Repo verification should run through Python dev
tools, not through a root npm project wrapper.

## Problem

The repository currently has a root `package.json` and `package-lock.json` only
to install Paseo and expose `npm run verify`. That makes the Python package look
like an npm project and causes verification wrappers to prefer npm even though
the actual checks are Ruff and pytest.

## Scope

In scope:

- Remove root npm project metadata from this repo.
- Keep npm usage limited to installing external Paseo and OpenSpec CLIs.
- Add a Python-backed repo verification command discoverable by `lane verify`.
- Update install and README guidance.

Out of scope:

- Removing npm support from `lane verify` for JavaScript target repositories.
- Changing Paseo or OpenSpec distribution channels.

## Approach

Delete the root npm manifest and lockfile, stop running `npm install` during
repo installation, and add a Python verification script that invokes Ruff and
pytest with the current interpreter.

## Review Notes

- Known risks:
  - local checkouts must run `scripts/install.sh --dev` before using repo verification
- Verification expectations:
  - `lane verify`
  - direct Ruff and pytest as needed
