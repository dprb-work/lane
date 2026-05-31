# self-host-lane-migration

## Metadata

- Change id: `self-host-lane-migration`
- Status: `active`
- Branch: `chore/self-host-lane-migration`
- PR: `https://github.com/dprb-work/lane/pull/38`

## Intent

Move this repository's own development guidance to the self-hosted `lane`
workflow.

## Scope

- Document that new work in this repo starts with `scripts/dev-lane.sh start` and
  continues through `scripts/dev-lane.sh` lifecycle commands.
- Clarify that archived legacy workspace paths are historical metadata only.
- Note that global agent guidance was updated separately outside this repository;
  this PR only owns repo-tracked documentation.

## Acceptance

- Repo-local docs tell agents to use `lane` for new repo work.
- The active spec does not require non-repo files to merge the repo PR.
- Verification passes with the repo's normal check command.
