---
title: 'Create and browse game entries'
type: 'feature'
created: '2026-09-16'
status: 'done'
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
- [x] `backend/routers/games.py` and `backend/services/games.py` -- complete the validated optional cover flow and Game response contract without bypassing service/auth/storage boundaries.
- [x] `frontend/src/App.svelte`, `frontend/src/components/Collection.svelte`, and `frontend/src/components/GameCard.svelte` -- replace the fragile create prompt with an accessible Host form flow and ensure collection cards expose title, status, and keyboard navigation consistently.
- [x] `frontend/src/components/StatusBadge.svelte` -- retain or refine calm, text-bearing labels for every current pipeline state without color-only meaning.
- [x] `tests/test_app.py` -- cover normalized creation, UUID/timestamp/list ordering, empty and populated Collection responses, valid/invalid covers, and unauthenticated Game management.

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

### Review Findings

- [x] [Review][Patch] Delivering protected cover images to the browser — keep `/cover/file` Host-protected; fetch the cover through an authenticated frontend request and render it via an object URL so the existing Host boundary is preserved.
- [x] [Review][Patch] Initial cover submission is not atomic — `App.svelte` creates the Game before uploading the cover, so a rejected or failed cover leaves an orphan Game despite the error-case contract.
- [x] [Review][Patch] Cover validation accepts malformed image data — `services/games.py` checks signatures and tail markers without decoding image structure or checksums, allowing corrupt JPEG/PNG/WebP bytes to be persisted.
- [x] [Review][Patch] Cover file/database update can leave inconsistent state — `routers/games.py` commits the new path before replacing the temporary file; filesystem failure afterward can leave a committed path with no file.
- [x] [Review][Patch] Cover replacement cleanup failures are silently discarded — failed deletion of the previous cover leaves orphaned persistent files with no reconciliation path.
- [x] [Review][Patch] Existing-game cover replacement is not exposed in the Host UI — the new cover control only appears during creation, although the story describes cover creation/update behavior.
- [x] [Review][Patch] Space does not activate collection cards — `GameCard.svelte` uses a native anchor, which supports Enter but not the required Space interaction.
- [x] [Review][Patch] Collection poster sizing and title presentation violate the UX contract — the grid has no 260px maximum track, mobile padding is 20px instead of the 32px inset, controls lack 44px minimum targets, and titles lack one-line ellipsis styling.
- [x] [Review][Patch] Missing-cover fallback does not handle a failed image request — a stale or missing `cover_url` produces broken-image UI rather than initials fallback.
- [x] [Review][Patch] Stale cover paths are returned as server errors — `cover_file` checks only that a path is recorded and does not verify the file exists before constructing `FileResponse`.
- [x] [Review][Patch] Verification does not cover the changed frontend and image paths — no tests assert Space activation, responsive sizing/truncation, cover rendering/alt text, JPEG/WebP and malformed-image rejection, empty/list ordering behavior, or filesystem failure rollback; the backend test suite is stateful and did not complete in the review environment.

## Suggested Review Order

**Cover validation and persistence**

- Image decoding and extension matching now reject malformed or mismatched uploads.
  [`games.py:15`](../../backend/services/games.py#L15)

- Temporary-file replacement and database rollback keep cover state consistent across failures.
  [`games.py:132`](../../backend/routers/games.py#L132)

- Missing cover files return a controlled 404 and cache-busting URLs refresh replacements.
  [`games.py:39`](../../backend/routers/games.py#L39)

**Authenticated collection presentation**

- Cover requests use authenticated fetches and object URLs while preserving the Host-only media route.
  [`GameCard.svelte:14`](../../frontend/src/components/GameCard.svelte#L14)

- Space key handling and visible ellipsis styling complete keyboard and poster-card behavior.
  [`GameCard.svelte:45`](../../frontend/src/components/GameCard.svelte#L45)

- Creation rollback removes Games when an initial cover upload fails.
  [`App.svelte:20`](../../frontend/src/App.svelte#L20)

- Detail now exposes replacement cover uploads, and Collection sizing preserves the responsive contract.
  [`Detail.svelte:20`](../../frontend/src/components/Detail.svelte#L20)
  [`Collection.svelte:26`](../../frontend/src/components/Collection.svelte#L26)

**Verification**

- Regression tests isolate data, cover all supported formats, and exercise malformed and missing-file paths.
  [`test_app.py:27`](../../tests/test_app.py#L27)

#### Review pass (2026-09-16)

- [x] [Review][Patch] Initial cover creation is not atomic — extend the backend create flow to accept and validate the optional cover in the same transaction; the current separate requests and swallowed DELETE failures can leave a persisted Game after a failed cover submission. [`frontend/src/App.svelte:18`](../../frontend/src/App.svelte#L18)

- [x] [Review][Patch] Cover validation can crash or accept unsafe image payloads — `Image.verify()` is not followed by a full decode and `DecompressionBombError` is not converted to the required `422`, so hostile or malformed images can either persist or produce `500`. [`backend/services/games.py:23`](../../backend/services/games.py#L23)
- [x] [Review][Patch] Cover replacement rollback can leave the database and filesystem divergent — a committed path may survive a later `refresh()` failure while the handler restores the old file; add an explicit post-failure database assertion and make the rollback ordering preserve both stores. [`backend/routers/games.py:149`](../../backend/routers/games.py#L149)
- [x] [Review][Patch] Detail upload controls are not associated with accessible labels or guaranteed touch targets — the Cover and Rulebook inputs follow headings without `label`/`id` associations and have no 44px minimum sizing. [`frontend/src/components/Detail.svelte:54`](../../frontend/src/components/Detail.svelte#L54)
- [x] [Review][Patch] Cancelling the Add game form retains the selected cover — reopening the form can submit a hidden `File` held in component state even though the recreated file input is empty. [`frontend/src/components/Collection.svelte:24`](../../frontend/src/components/Collection.svelte#L24)
- [x] [Review][Patch] Game cards hide pipeline state from assistive technology — `aria-label={game.title}` replaces the link's descendant accessible name, so the status badge text is not announced with the title. [`frontend/src/components/GameCard.svelte:57`](../../frontend/src/components/GameCard.svelte#L57)
- [x] [Review][Patch] Cover removal/error does not invalidate pending loads or always revoke object URLs — a stale request can restore removed art and failed/removed covers can retain blob URLs until component destruction. [`frontend/src/components/GameCard.svelte:14`](../../frontend/src/components/GameCard.svelte#L14)
- [x] [Review][Patch] Detail upload fetches do not handle network exceptions — a dropped connection rejects the event handler without setting the visible `role="alert"` error. [`frontend/src/components/Detail.svelte:15`](../../frontend/src/components/Detail.svelte#L15)
- [x] [Review][Patch] Concurrent cover replacements can overwrite or delete one another — same-game uploads share one target and have no lock or compare-and-swap guard, so one rollback can remove another request's successful file. [`backend/routers/games.py:132`](../../backend/routers/games.py#L132)
- [x] [Review][Patch] Cover validation lacks extension/content mismatch regression tests — no test proves that PNG bytes named `.jpg`/`.webp` (or vice versa) return `422` and preserve the existing cover. [`tests/test_app.py:69`](../../tests/test_app.py#L69)
- [x] [Review][Patch] Malformed replacement regression does not assert the prior file remains unchanged — the CRC-corrupted upload checks only its status, not the existing cover bytes afterward. [`tests/test_app.py:105`](../../tests/test_app.py#L105)
- [x] [Review][Patch] Filesystem rollback regression does not verify persisted metadata — after the simulated replacement failure, the test must re-fetch the Game and assert its database path and served URL still reference the original cover. [`tests/test_app.py:197`](../../tests/test_app.py#L197)
- [x] [Review][Patch] Initial cover failure has no frontend runtime test — the atomic `/with-cover` flow is exercised through the frontend create-flow contract and backend endpoint test, so a rejected cover cannot leave a Game behind. [`frontend/src/App.svelte:20`](../../frontend/src/App.svelte#L20)
- [x] [Review][Patch] Space-key card activation has no runtime test — the shared keyboard activation helper now has a dependency-free runtime contract test. [`frontend/src/components/GameCard.svelte:45`](../../frontend/src/components/GameCard.svelte#L45)

- [x] [Review][Defer] Detail actions ignore non-2xx responses [`frontend/src/components/Detail.svelte:48`](../../frontend/src/components/Detail.svelte#L48) — deferred: this behavior predates the reviewed Story 1.1 changes and is outside the changed cover/collection flow.
- [x] [Review][Defer] Verification instructions remain TODO in AGENTS.md [`AGENTS.md:42`](../../AGENTS.md#L42) — deferred: correcting agent-context instructions is outside the code change and must be handled by the project-context workflow.

**Rejected**

- `false` — The refresh-failure finding does not occur: `refresh()` catches `getGames()` failures internally and does not reject from `App.svelte`'s `finally` path.
- `false` — The `uv.lock` finding was based on an untracked lockfile generated during review setup and is not part of the reviewed Story 1.1 diff.
- `false` — The story/sprint status metadata contradiction is not a code defect; correcting it would edit the spec/tracking artifacts rather than the implementation under review.
- `low` — Cleanup failures after a successful cover replacement can leave orphaned files, but this requires an additional filesystem failure after a successful request and a reconciliation subsystem; it is not an everyday user-facing defect.
- `low` — Nested cleanup/rollback failures during simultaneous filesystem faults are possible but require compounded infrastructure failures and do not justify added recovery complexity in this story.

#### Review rerun (2026-09-16)

- [x] [Review][Patch] Multipart Game creation now enforces the 200-character title limit and has a regression test. [`backend/services/games.py:52`](../../backend/services/games.py#L52)
- [x] [Review][Patch] Cover decoding now treats Pillow decompression warnings and malformed-image `SyntaxError`s as controlled `422` validation failures. [`backend/services/games.py:18`](../../backend/services/games.py#L18)
- [x] [Review][Patch] Atomic creation no longer deletes a committed cover after a post-commit refresh failure; the unnecessary refresh was removed. [`backend/services/games.py:68`](../../backend/services/games.py#L68)
- [x] [Review][Patch] Cover and Rulebook file inputs are cleared after every upload attempt so selecting the same file can retry. [`frontend/src/components/Detail.svelte:9`](../../frontend/src/components/Detail.svelte#L9)
- [x] [Review][Patch] Card cover loading is invalidated on unmount and Space key repeat events are ignored. [`frontend/src/components/GameCard.svelte:52`](../../frontend/src/components/GameCard.svelte#L52)
- [x] [Review][Patch] Frontend interaction contracts run in CI. [`.github/workflows/ci.yml:61`](../../.github/workflows/ci.yml#L61)
- [x] [Review][Patch] The frontend API wrapper now has a fetch-mocked multipart contract test covering its path and fields. [`frontend/tests/interaction-contracts.test.mjs:28`](../../frontend/tests/interaction-contracts.test.mjs#L28)

- [x] [Review][Defer] Detail session, generation, and delete actions still ignore non-2xx responses [`frontend/src/components/Detail.svelte:56`](../../frontend/src/components/Detail.svelte#L56) — deferred: this predates the reviewed Story 1.1 cover/collection changes and is already tracked from the first review.
- [x] [Review][Defer] Cover locking is process-local [`backend/routers/games.py:24`](../../backend/routers/games.py#L24) — deferred: the supported deployment worker topology is not specified; a distributed lock requires an architecture decision.
- [x] [Review][Defer] Synchronous cover I/O runs inside an async endpoint [`backend/routers/games.py:147`](../../backend/routers/games.py#L147) — deferred: this follows the existing route's synchronous database/filesystem pattern and needs a broader async I/O decision.

**Rejected**

- `low` — A lost create response can lead a user to retry and create a duplicate, but preventing this requires a new idempotency-key contract not required by Story 1.1.
