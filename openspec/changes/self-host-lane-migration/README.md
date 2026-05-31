# self-host-lane-migration

## Metadata

- Change id: `self-host-lane-migration`
- Status: `active`
- Branch: `chore/self-host-lane-migration`
- PR: `https://github.com/dprb-work/lane/pull/38`

## Intent

Move this repository's own development guidance to the self-hosted `lane`
workflow, and align global agent guidance so it follows a repo's declared
lifecycle tool instead of naming a superseded helper.

## Scope

- Document that new work in this repo starts with `scripts/dev-lane.sh start` and
  continues through `scripts/dev-lane.sh` lifecycle commands.
- Clarify that archived legacy workspace paths are historical metadata only.
- Update global brain instructions to prefer repo-declared lifecycle policy,
  including `lane` when a repo declares or initializes it, without making `lane`
  a universal default.

## Acceptance

- Repo-local docs tell agents to use `lane` for new repo work.
- Global guidance no longer names the superseded helper.
- Verification passes with the repo's normal check command.
