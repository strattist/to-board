---
title: 'Create and browse game entries'
type: 'feature'
created: '2026-09-16'
status: 'in-progress'
story_id: '1-1'
review_loop_iteration: 0
baseline_commit: 'd9a141cac4bb67be132f26fd9c4d70c1ddba2e49'
context:
  - '{project-root}/AGENTS.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The Game collection is the root of every later workflow, but the current create-and-browse path is only a thin implementation and does not fully deliver the approved Host experience. Game creation must reliably normalize and persist the domain record, while the Collection must make entries discoverable and accessible without exposing management to Guests.

**Approach:** Complete the Story 1.1 vertical slice across the existing SQLModel/FastAPI and Svelte surfaces. Preserve the current service and API boundaries, add the missing optional cover-image creation/update behavior and accessible collection interactions, and prove the behavior with focused backend regression tests.

## Boundaries & Constraints

**Always:** Keep Game creation and collection endpoints behind `require_host`; use UUID v4 IDs, trimmed non-empty titles, ISO 8601 UTC timestamps, and the existing `slugify()`/service conventions. Store cover files only below the configured uploads dataset, validate JPEG/PNG/WebP covers at no more than 10 MB, expose status as text plus color, and keep Collection cards keyboard-activatable and responsive at the prescribed poster-grid sizes.

**Ask First:** Any change to the Game data model, route shape, authentication model, persistent-storage locations, or behavior that changes the approved Epic 1 scope or affects later Rulebook/Content dependencies.

**Never:** Do not add Guest identity tracking, a login screen, a second database, Docker-managed persistent storage, direct frontend pipeline-state mutation, native PDF handling, or unrelated Epic 1/2/3 features.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|----------------------------|----------------|
| HAPPY_PATH | Authenticated Host submits a valid title, with or without a cover | `201` returns the normalized Game; UUID, UTC creation time, and `no_rulebook` state are present; the entry appears in Collection | N/A |
| ERROR_CASE | Title is whitespace-only, or cover is unsupported, corrupt, or over 10 MB | No Game or invalid file is persisted | Return FastAPI `422` detail and leave existing data unchanged |
| ERROR_CASE | Unauthenticated request calls Game list/create or cover upload | No collection data or management operation is exposed | Enforce the existing Host auth boundary (`401`/redirect behavior) |

</frozen-after-approval>

## Code Map

- `backend/models/game.py:8-13` -- Game persistence fields and UTC timestamp; do not introduce a second model or alter Rulebook cardinality.
- `backend/services/games.py:9-18` -- existing title normalization and Game creation service; extend only through this service boundary when needed.
- `backend/routers/games.py:19-75, 103-126` -- `GameCreate`, `payload()`, list/create/detail endpoints, and existing cover upload route; preserve FastAPI error shapes and dataset paths.
- `backend/core/auth.py:7-36` -- `require_host()` is the mandatory Host boundary for all Game routes.
- `backend/core/utils.py:1-20` -- shared UUID and slug helpers used by Game creation.
- `frontend/src/App.svelte:16-24` -- collection routing, refresh lifecycle, and current add-game action.
- `frontend/src/components/Collection.svelte:1-3` -- responsive Collection grid, loading, empty state, and Add game control.
- `frontend/src/components/GameCard.svelte:1-3` -- accessible card, initials fallback, status placement, and focus styling.
- `frontend/src/components/StatusBadge.svelte:1-3` -- text-bearing Pipeline State labels and loading treatment.
- `tests/test_app.py:21-30` -- existing creation/validation coverage; extend with listing, metadata, cover validation, and Host-boundary assertions.

## Tasks & Acceptance

**Execution:**
- [ ] `backend/routers/games.py` and `backend/services/games.py` -- complete the validated optional cover flow and Game response contract without bypassing service/auth/storage boundaries.
- [ ] `frontend/src/App.svelte`, `frontend/src/components/Collection.svelte`, and `frontend/src/components/GameCard.svelte` -- replace the fragile create prompt with an accessible Host form flow and ensure collection cards expose title, status, and keyboard navigation consistently.
- [ ] `frontend/src/components/StatusBadge.svelte` -- retain or refine calm, text-bearing labels for every current pipeline state without color-only meaning.
- [ ] `tests/test_app.py` -- cover normalized creation, UUID/timestamp/list ordering, empty and populated Collection responses, valid/invalid covers, and unauthenticated Game management.

**Acceptance Criteria:**
- Given an authenticated Host is viewing Collection, when a valid title is saved, then exactly one Game is created and appears without a full-page reload.
- Given a title has leading/trailing whitespace, when it is submitted, then the persisted and returned title is trimmed; a whitespace-only title returns `422` and creates nothing.
- Given a valid JPEG, PNG, or WebP cover no larger than 10 MB, when it is uploaded for a Game, then it is stored below the configured uploads path and the card uses the cover with the Game title as alt text.
- Given an invalid, corrupt, or oversized cover, when upload is attempted, then the API returns `422` and does not replace an existing valid cover.
- Given the Collection contains Games, when a Host opens it at supported viewport sizes, then cards form the responsive 2:3 poster grid, expose a text-bearing status, and activate with Enter or Space.
- Given a request is unauthenticated, when it calls Game list, create, or cover-management endpoints, then the Host auth boundary rejects it and no Guest route grants equivalent access.

## Design Notes

The existing backend already owns Game creation, list payloads, and cover upload. Prefer extending those seams rather than introducing a parallel endpoint or frontend-only state. The Collection should remain a library-first surface: no search, pagination, or unrelated detail workflows are required for this story.

## Verification

**Commands:**
- `pytest -q tests/test_app.py` -- expected: all Game creation, collection, cover, and existing lifecycle tests pass.
- `npm --prefix frontend run check` -- expected: Svelte/TypeScript checks pass if the repository exposes this script.

**Manual checks (if no CLI):**
- Open Collection as Host, create a title with whitespace and a valid cover, confirm the normalized title, cover frame, alt text, status label, empty/loading states, and keyboard activation.
