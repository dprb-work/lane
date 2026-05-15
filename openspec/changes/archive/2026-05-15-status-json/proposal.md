# Proposal: Lifecycle JSON Output

## Metadata

- Change id: `status-json`
- Status: `archived`
- Branch: `feat/status-json`
- Worktree: `/home/d/wt/lane/status-json`
- PR: `https://github.com/dprb-work/lane/pull/17`
- OpenSpec rationale:
  - changes public CLI behavior
  - spans CLI, tests, README, and backlog state

## Intent

Add machine-readable output modes for lifecycle commands whose results already
have compact structured shapes, so agents and scripts can consume lane state,
health, diagnostics, verification, review, push, sync, and finalize outcomes
without parsing human text.

## Problem

Several commands already gather structured values internally but only print
line-oriented human text. Automation needs stable JSON output for the common lane
inspection and handoff path.

## Scope

In scope:

- Add `--json` to `lane status`, `lane list`, `lane doctor`, `lane verify`,
  `lane sync`, `lane review`, `lane push`, and `lane finalize`.
- Include stored lane state under `state` wherever command output is lane-scoped.
- Include read-only status health facts under `health` for `lane status --json`.
- Preserve default human output.
- Update focused tests and README/backlog notes.

Out of scope:

- JSON output for destructive cleanup/abort flows or arbitrary `lane run`
  command streaming.
- New health fields or state mutation.

## Approach

Reuse existing command result dataclasses and `state_to_dict`. Each command
switches only at print time, producing a compact JSON object and leaving existing
human output unchanged.

## Review Notes

- Known risks: JSON consumers may infer the current field names are a long-term
  versioned schema before schema policy exists.
- Verification expectations: run the focused CLI test plus the repo verification
  command.
