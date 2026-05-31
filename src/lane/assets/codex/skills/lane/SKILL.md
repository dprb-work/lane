---
name: lane
description: Use when working in repositories that use the lane Paseo-native lifecycle CLI, including starting lanes, checking status, running verification, review handoff, finalize, cleanup, or deciding whether raw git worktree commands are appropriate.
---

<!-- lane:codex-skill -->

# Lane Workflow

Use this skill when a repository uses `lane` for Paseo-native development lanes.

## Rules

- Prefer `lane` commands over raw `git worktree`, raw `git push`, or ad hoc
  checkout commands.
- Start coherent work with `lane start <type>/<slug>` unless the user explicitly
  says not to or `lane`/Paseo is unavailable.
- Work inside the created Paseo workspace, not the source checkout.
- Use `lane status` and `lane doctor` before diagnosing lane lifecycle issues.
- Use `lane run -- <command>` for lane-scoped commands.
- Use `lane verify` for repository verification when available.
- Use `lane review`, then `lane finalize`, before human PR or MR handoff when
  the lane is ready.
- Use `lane cleanup` for merged lanes and `lane abort` for cancelled lanes.
- If `lane` or Paseo is unavailable and raw Git is necessary, state the
  exception before using raw Git.

## Common Commands

```bash
lane init
lane start feat/example --base main
lane status
lane doctor
lane run -- python -m pytest
lane verify
lane push
lane review
lane finalize
lane cleanup
```

## Notes

`lane` owns ignored `.lane/` state, required OpenSpec specs, verification,
review orchestration, finalize, cleanup, and abort policy. Paseo owns workspace
and worktree creation, setup, services, provider runtimes, agents, terminals,
and archive behavior.
