# finalize-push-verification-policy

Add explicit push lifecycle policy around verification freshness, safe branch
publication, and safe history rewrites.

## Intent

`lane finalize` currently runs verification and pushes as one implicit handoff
step. That is safe but too coarse: users need durable evidence that verification
was fresh for the branch being published, an explicit push step between verify
and finalize, and an explicit way to push rewritten branch history without
leaving the `lane` workflow. These behaviors are one feature because they answer
the same lifecycle gate: is this lane safe to publish or hand off?

The API should keep common paths low-friction while making destructive or risky
behavior explicit. Normal push/finalize should remain a safe push. Rewrite pushes
must use `--force-with-lease`, never raw `--force`.

## Scope

- Record successful verification freshness in lane state.
- Make `lane verify` update that freshness when verification succeeds.
- Add `lane push [selector]` as the explicit branch publication step between
  verify and finalize.
- Make `lane push` run verification by default before publication.
- Make `lane finalize` use the same push lifecycle rather than duplicating push
  policy.
- Support safe history rewrite pushes on `lane push` and `lane finalize` with an
  explicit `--force-with-lease` flag.
- Keep normal pushes safe by default with no repeated remote/upstream flags.
- Infer the forge remote from local Git remotes as today.

Out of scope:

- Raw `--force` support.
- User-facing provider or upstream flags unless inference proves insufficient.
- Non-Paseo worktree fallback behavior.
- Broad refactors unrelated to finalize, push, verification state, or command
  execution dedupe needed for this feature.

## API

Preferred command shape:

```bash
lane verify [selector]
lane push [selector] [--no-verify] [--force-with-lease]
lane finalize [selector] [--no-verify] [--force-with-lease]
```

Default behavior:

- `lane verify` runs the discovered verification command in the lane workspace.
- On success, `lane verify` records the command, success status, and enough
  freshness data to decide whether the result still applies to the current lane
  branch state.
- `lane push` runs verification by default before publishing and records
  freshness when verification succeeds.
- `lane push --no-verify` skips inline verification, but still refuses to publish
  unless the lane already has a fresh successful verification for the current
  branch state.
- Normal `lane push` uses the inferred forge remote, sets upstream when needed,
  and stays equivalent to `git push -u <remote> <branch>` for a new lane branch.
- `lane finalize` uses the same push path as `lane push`, then continues to the
  existing PR/MR create-or-update handoff.
- `--force-with-lease` changes only the push mode; it does not skip verification,
  spec archive checks, review state, PR/MR creation, or any other guardrail.

Rejected or deferred API:

- Do not add `--force`; it is too easy to misuse and weaker than the desired
  operational primitive.
- Do not require repeated `--upstream origin` or provider flags on normal use;
  remote inference remains the local policy.
- Defer `--push-mode force-with-lease` unless additional push modes appear.
- Do not add `--verify`; verification is the default for publication commands,
  and `--no-verify` is the explicit opt-out.

## State Model

The state model needs an explicit verification freshness record in
`.lane/state.yaml`. The final field names can change during implementation, but
they should capture:

- verification command label
- verification exit status
- verification time or durable freshness marker
- Git identity the verification applies to, preferably `HEAD` commit

Use optional schema `1` fields for the freshness record. Existing lane state
without `verification` remains valid; publication commands that need freshness
must either run verification by default or reject `--no-verify` when the optional
record is absent or stale.

## Code Quality Follow-Ups

Handle only the dedupe that materially helps this feature:

- Share push command construction between GitHub and GitLab finalize paths.
- Prefer one internal push path used by both `lane push` and provider finalize
  flows so verification gating, upstream setup, and push mode do not drift.
- Share command execution/error formatting if it is needed to avoid new
  finalize/verify duplication, but do not create a broad subprocess framework as
  part of this feature.
- Keep parser changes local to `verify` and `finalize`; introduce tiny
  command-builder helpers only if the new flags make the existing parser block
  harder to scan.

Leave broader cleanup for later:

- `src/lane/cli.py` lane resolution and attach resolution overlap, but attach has
  separate worktree matching. Do not dedupe it in this feature unless a very
  small helper naturally falls out.
- `src/lane/verify.py`, `src/lane/review.py`, `src/lane/forge.py`,
  `src/lane/cleanup.py`, and `src/lane/lane_target.py` repeat subprocess runner
  patterns. A shared internal helper may be worthwhile later, but normalize type
  differences in a separate cleanup.
- `tests/test_cli.py` setup duplication is accumulating. Add fixture helpers only
  when the new policy tests would otherwise repeat substantial setup.
- `start --base main` is hardcoded while remote branch selector base defaults can
  infer remote `HEAD`. Leave that API consistency issue for a separate feature.
- Full `cli.py` command-builder extraction.
- Full provider abstraction for PR/MR create/update.
- Global subprocess runner module unless repetition grows further and the helper
  can stay narrow.

## API Cohesion Rules

- Lane-scoped commands should continue to accept an optional selector.
- `push` should sit between `verify` and `finalize`: verify proves freshness,
  push publishes the branch safely, and finalize performs review handoff after
  publication.
- `push` should run verification by default before branch publication.
- `push --no-verify` exists for users who intentionally want to reuse an already
  fresh verification result without rerunning verification.
- `finalize` should call through the same push lifecycle instead of carrying a
  separate verification/push implementation.
- `finalize --no-verify` forwards the explicit verification opt-out into the
  shared push lifecycle before review handoff.
- Remote selection remains implicit from local Git remotes. Do not add global
  `--provider`, `--remote`, or `--upstream` flags unless inference fails in real
  use.
- Destructive or history-rewriting operations remain explicit, matching cleanup
  flags such as `--delete-remote-branch`, `--discard`, and `--close-pr`.

## Acceptance

- `lane verify` records a successful verification freshness marker in lane state.
- Failed verification does not mark the lane as freshly verified.
- `lane push` runs verification by default, records success, then continues when
  it passes.
- `lane push --no-verify` fails clearly when no fresh successful verification
  applies.
- Normal `lane push` pushes the selected lane branch to the inferred remote,
  setting upstream when needed.
- `lane push --force-with-lease` uses `git push --force-with-lease`, not
  `--force`.
- `lane finalize` uses the same verification freshness and push behavior as
  `lane push` before PR/MR create-or-update.
- `lane finalize --no-verify` and `lane finalize --force-with-lease` flow through
  the same shared push lifecycle.
- GitHub and GitLab finalize flows both honor the selected push mode.
- PR/MR body continues to report verification and review state.
- Documentation describes verification freshness and rewrite push behavior.

## Tasks

- [x] Choose and document the verification freshness state shape.
- [x] Update state validation, read/write, and tests for verification freshness.
- [x] Make `lane verify` persist successful verification freshness only on exit
  status `0`.
- [x] Add `lane push [selector]` with default inline verification and freshness
  validation.
- [x] Add `lane push --no-verify` to reuse an already fresh verification result.
- [x] Keep normal `lane push` safe with inferred remote and upstream
  setup when needed.
- [x] Add `--force-with-lease` to `lane push`.
- [x] Make `lane finalize` use the shared push lifecycle.
- [x] Add `lane finalize --no-verify` and `lane finalize --force-with-lease` as
  pass-throughs to that lifecycle.
- [x] Share push construction between standalone push and provider finalize
  paths.
- [x] Add focused CLI and forge tests for freshness, finalize push, and
  force-with-lease.
- [x] Update README workflow and tool/API documentation.
