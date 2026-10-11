---
title: 'Add prek pre-commit checks'
type: 'chore'
created: '2026-09-16'
status: 'done'
route: 'one-shot'
---

# Add prek pre-commit checks

## Intent

**Problem:** The repository has no shared pre-commit checks, so local changes and CI do not enforce basic file and repository hygiene consistently.

**Approach:** Add a pinned prek-compatible hook configuration with `uv lock --check`, install uv for the CI hook job, and document the pinned local command in `AGENTS.md`.

## Suggested Review Order

**Hook configuration**

- Defines repository-wide syntax and hygiene checks while preserving generated assets.
  [`.pre-commit-config.yaml:1`](../../.pre-commit-config.yaml#L1)

**CI integration**

- Runs the same hooks on every push and pull request with a pinned prek release.
  [`ci.yml:17`](../../.github/workflows/ci.yml#L17)

**Agent workflow**

- Gives agents the exact pinned command for local all-files verification.
  [`AGENTS.md:50`](../../AGENTS.md#L50)
