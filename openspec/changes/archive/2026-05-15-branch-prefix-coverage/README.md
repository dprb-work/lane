# branch-prefix-coverage

Align lane branch parsing with the repository's conventional branch policy.

## Scope

- Accept every branch prefix allowed by repo policy.
- Keep `feat/` mapped to the `spec-driven` OpenSpec schema.
- Map every other allowed prefix to `lane-lite`.
- Keep the public command surface unchanged; no new type or schema flags.
- Update tests, README, and backlog state.

## Acceptance

- `lane start` and branch parsing accept `build`, `chore`, `ci`, `docs`, `feat`,
  `fix`, `perf`, `refactor`, `revert`, `style`, and `test`.
- `feat/` still uses `spec-driven`.
- Every other allowed prefix uses `lane-lite`.
- Unsupported prefixes still fail with guidance.

## Tasks

- [x] Expand supported branch prefix mapping.
- [x] Add tests for every allowed lane-lite prefix.
- [x] Update README branch schema table.
- [x] Remove completed backlog item.
