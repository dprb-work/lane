# pr-first-finalize-lifecycle

## Metadata

- Change id: `pr-first-finalize-lifecycle`
- Status: `archived`
- Branch: `feat/pr-first-finalize-lifecycle`
- Archive branch: `feat/doctor-opencode-tool-diagnostics`
- Archive PR: `https://github.com/dprb-work/lane/pull/29`

## Outcome

The PR-first lifecycle is implemented and documented: `lane start` creates the
early draft PR/MR surface, `lane push` refreshes metadata, `lane review` records
aggregate agent review state, and `lane finalize` gates human-review readiness on
fresh verification, archived spec state, review approval for the current `HEAD`,
pushed branch contents, and current PR/MR metadata.

## Completed Acceptance

- `lane start` creates or records a draft PR/MR and stores its URL in lane state.
- `lane start` creates an initial spec commit before pushing/opening the PR/MR.
- `lane push` updates an existing PR/MR body using current lane state without
  marking draft PRs/MRs ready for human review.
- `lane review` stores aggregate review as `none`, `approve`, `comment`, or
  `reject`, and can render a templated review-summary comment.
- `lane finalize` refuses stale verification, unapproved current `HEAD`, active
  spec state, and stale branch state before handoff.
- `lane finalize` updates non-empty PR/MR metadata and marks supported draft
  PRs/MRs ready for human review.
- README describes the draft PR/MR lifecycle, agent approval semantics, and the
  human-review boundary.

## Archive Note

Archived with the OpenCode doctor diagnostic feature to avoid an archive-only PR.
