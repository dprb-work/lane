# pr-first-finalize-lifecycle

Define a PR-first lane lifecycle where `lane finalize` means the lane is ready
for human review.

## Metadata

- Change id: `pr-first-finalize-lifecycle`
- Branch: `feat/pr-first-finalize-lifecycle`
- Status: `active`
- OpenSpec rationale:
  - changes public lifecycle semantics across start, push, review, and finalize
  - prevents empty PR/MR descriptions and unarchived specs from reaching human
    review
  - likely spans CLI behavior, forge providers, README, tests, and lane state

## Intent

Make the PR/MR the visible collaboration surface from the beginning of a lane,
while preserving `lane review` and `lane finalize` as separate lifecycle steps.
Draft PRs/MRs can exist while work is in progress; finalized PRs/MRs must have
fresh verification, agent review approval, archived spec state, pushed branch
contents, and current metadata.

## Problem

The current lifecycle treats `lane finalize` as the step that creates or updates
the PR/MR after the spec has already been archived. That avoids handing off
active specs, but it also delays the PR/MR collaboration surface and makes PR
metadata freshness depend on a late handoff step. Earlier workflows have produced
empty descriptions or separate archive-only PRs. The intended workflow should
make those states hard to reach.

## Golden Path

1. `lane start feat/foo` creates the worktree, branch, active spec, lane state,
   and a draft PR/MR with non-empty initial metadata.
2. The developer or dev agent implements the lane.
3. `lane push` verifies by default, publishes the branch, and updates PR/MR
   metadata when the lane already has a PR/MR.
4. `lane review` runs agent reviewers and judge, then records aggregate review
   metadata in lane state and optionally posts or refreshes a templated review
   comment.
5. The dev agent archives the spec into the same branch before handoff.
6. `lane finalize` verifies freshness, pushes the final branch, requires agent
   review `approve`, requires the active spec to be archived, updates PR/MR
   metadata, and marks the draft PR/MR ready for human review.
7. Human review and merge happen on the finalized PR/MR.
8. `lane cleanup` runs only after merge and remains responsible for post-merge
   teardown and archive evidence.

## Terms

- Agent review approval means the aggregate `lane review` result stored in lane
  state is `approve`. It does not mean human GitHub/GitLab approval.
- Human review starts after `lane finalize` marks the PR/MR ready.
- Draft means visible but not ready for human review.
- Finalized means ready for human review, not merged.

## Scope

In scope:

- Update lifecycle semantics so `lane start` creates or attaches a draft PR/MR
  early.
- Ensure `lane start` writes useful initial PR/MR metadata rather than an empty
  description.
- Ensure `lane push` updates PR/MR metadata when a PR/MR exists for the lane.
- Keep `lane review` as the producer of aggregate agent verdict metadata.
- Make `lane finalize` the readiness gate for human review.
- Make `lane finalize` require fresh verification, archived spec state, aggregate
  agent review `approve`, pushed branch contents, and current PR/MR metadata.
- Make `lane finalize` create or update PR/MR metadata if needed, then mark the
  PR/MR ready for review when the provider supports draft/ready state.
- Use templates for PR/MR bodies and optional review-summary comments so metadata
  shape stays stable without requiring a fully versioned schema.
- Document provider behavior for GitHub draft PRs and GitLab draft/WIP MRs.

Out of scope:

- Cleanup archive summary behavior.
- Detecting or requiring human approval.
- Automatically running `lane review` from `lane finalize`.
- Automatically archiving the spec from reviewer or judge approval.
- A fully versioned PR/MR body schema.
- Broad provider abstraction refactors beyond what the lifecycle needs.

## Design Direction

`lane review` should own agent review execution and verdict metadata. `lane
finalize` should own side effects that transition a lane into human-review state.
Finalize may consume the review verdict, but it should not run reviewers itself.
Reviewers and judges should not archive specs, push branches, or change PR/MR
draft state as a side effect of approval.

Keep `review` and `finalize` separate in the external API. A collapsed command is
tempting because it offers a single "make ready" action, but it mixes expensive
or flaky review execution with provider mutations and makes partial failure hard
to interpret. The stable boundary is: review produces evidence, finalize consumes
evidence and performs handoff. A future convenience flag may run review before
finalize, but the default lifecycle should remain explicit.

PR/MR body generation should be shared between `start`, `push`, and `finalize` so
metadata cannot drift by command. Initial metadata may be incomplete while the
lane is draft, but it must be non-empty and identify the lane, branch, spec, and
current lifecycle status. Finalize metadata must reflect the final archived spec,
verification result, aggregate review verdict, and lane path.

Review comments, when supported, should use a separate stable template from the
PR/MR body. The comment should summarize the aggregate verdict, reviewer agents,
judge result, and any follow-up pointers without becoming the source of truth for
lane state.

## Acceptance

- `lane start` creates or records a draft PR/MR and stores its URL in lane state.
- `lane start` refuses or reports clearly when required forge setup prevents PR/MR
  creation.
- `lane push` updates an existing PR/MR body using current lane state.
- `lane push` does not mark draft PRs/MRs ready for human review.
- `lane review` continues to store aggregate review as `none`, `approve`,
  `comment`, or `reject`.
- `lane review` can render a templated review-summary comment without finalizing
  or marking the PR/MR ready.
- `lane finalize` refuses when review is not `approve`.
- `lane finalize` refuses while `openspec/changes/<spec>` still exists.
- `lane finalize` refuses when verification is stale or failing.
- `lane finalize` pushes the final branch state before handoff succeeds.
- `lane finalize` creates or updates non-empty PR/MR title and body before
  success.
- `lane finalize` marks GitHub draft PRs ready for review.
- `lane finalize` handles GitLab draft/WIP MR readiness with the supported CLI or
  documented title update behavior.
- README describes draft PR/MR lifecycle, agent approval semantics, and the human
  review boundary.

## Tasks

- [x] Confirm provider CLI support for GitHub draft/ready and GitLab draft/WIP
  readiness transitions.
- [x] Decide whether `lane start` must fail when draft PR/MR creation fails or can
  create the lane with an explicit warning and missing PR state.
- [x] Design shared PR/MR body template generation for start, push, and finalize.
- [ ] Design optional review-summary comment template generation for `lane
  review`.
- [x] Update `lane start` to create or attach a draft PR/MR and store its URL.
- [x] Update `lane push` to refresh PR/MR metadata when a PR/MR exists.
- [ ] Update `lane review` to render review metadata through the stable comment
  template when posting or refreshing review comments is supported.
- [x] Update `lane finalize` readiness gates for review approval, archived spec,
  fresh verification, pushed branch, and metadata refresh.
- [x] Update `lane finalize` to mark draft PRs/MRs ready for human review.
- [x] Add focused CLI and forge-provider tests.
- [x] Update README lifecycle documentation.
- [x] Remove or revise superseded backlog entries.
