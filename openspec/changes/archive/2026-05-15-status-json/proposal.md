# Proposal: Status JSON

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

Add a narrow machine-readable output mode for `lane status` so agents and scripts
can consume stored lane state and read-only health facts without parsing the
human text format.

## Problem

`lane status` already gathers the useful state and health facts, but it only
prints them as line-oriented human text. Automation needs a stable shape before
broader JSON support is added to other lifecycle commands.

## Scope

In scope:

- Add `lane status --json`.
- Include stored lane state under `state` and read-only health facts under
  `health`.
- Preserve default human output.
- Update focused tests and README/backlog notes.

Out of scope:

- JSON output for `lane list`, `lane verify`, `lane review`, `lane push`, or
  `lane finalize`.
- New health fields or state mutation.

## Approach

Reuse the existing status resolver, `state_to_dict`, and `collect_status_health`.
The CLI switches only at print time, producing a compact JSON object and leaving
all existing human output unchanged.

## Review Notes

- Known risks: JSON consumers may infer the current field names are stable before
  the broader structured-output design is complete.
- Verification expectations: run the focused CLI test plus the repo verification
  command.
