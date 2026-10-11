---
title: 'Delete a Game Safely'
type: 'feature'
created: '2026-09-20'
status: 'done'
review_loop_iteration: 0
baseline_commit: 'b2ab05b84967c78e1355334c610fcb90b3d77616'
context:
  - '{project-root}/AGENTS.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Game deletion exists as a thin endpoint and browser confirmation, but file failures are swallowed, database failures can leave files and rows out of sync, and the UI navigates away even when deletion fails. This risks losing current assets while falsely reporting success and does not meet the approved destructive-action UX.

**Approach:** Harden the existing Game deletion vertical slice across the service, protected route, Game Detail confirmation flow, and regression tests. Make current Game-owned records and files removable as one recoverable operation while preserving historical Session records and their title snapshots.

## Boundaries & Constraints

**Always:** Keep deletion behind `require_host` and `DELETE /api/games/{game_id}`. Remove the Game, its single Rulebook row and PDF/extracted-text files, its cover, and its Content row/state from the configured uploads dataset and SQLite database. Preserve every `GameSession` row and its `game_title_snapshot` (including deleted-game context). Contain cleanup to the uploads dataset, surface FastAPI-shaped errors, and never navigate/report success after a failed request. Use a modal overlay with explicit danger-confirm and ghost-cancel actions, accessible focus/44px controls, and no request on cancel.

**Ask First:** Any change to Session retention or Room semantics for an active Session, the authentication boundary, persistent dataset locations, or a new deletion/migration model beyond the existing SQLModel and cleanup patterns.

**Never:** Delete historical Sessions, expose deletion to Guest routes, use a browser `confirm()` as the only dialog, silently ignore storage errors, claim a successful `204` while leaving known partial state, add a second database, or use Docker-managed persistent storage.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|----------------------------|----------------|
| HAPPY_PATH | Host confirms a Game with cover, Rulebook, extracted text, Content, and historical Sessions | `204`; Game/Rulebook/Content and current files are gone; Sessions remain queryable with title snapshots; Collection no longer lists the Game | N/A |
| CANCEL | Host opens the dialog and cancels | No DELETE request; all rows and files remain unchanged | N/A |
| ERROR_CASE | Unknown Game id | No mutation | Return `404` with `detail` |
| ERROR_CASE | File removal, staging, or DB commit fails | No success is reported; database/files are restored or queued for durable reconciliation without deleting Sessions | Return a clear non-2xx error |
| ERROR_CASE | Unauthenticated or Guest request | No mutation or Guest capability | Existing Host auth rejection/redirect |

</frozen-after-approval>

## Code Map

- `backend/routers/games.py:99-103` -- protected DELETE route and 404 contract; preserve route shape and status behavior.
- `backend/services/games.py:82-95` -- current `delete_game()` and `remove_file()` seam; replace swallowed, non-recoverable cleanup with safe, recoverable deletion while keeping service ownership.
- `backend/models/game.py:7-20`, `backend/models/content.py:11-26`, `backend/models/session.py:5-13` -- rows to remove versus historical Session snapshot that must survive.
- `backend/routers/sessions.py:23-43`, `backend/routers/room.py:14-21` -- historical Session/detail and Room lookups; ensure deletion does not cascade or dereference a missing Game.
- `backend/services/rulebooks.py:25-145` -- uploads-root validation, cleanup retries, and journal patterns to reuse rather than invent unsafe path handling.
- `frontend/src/components/Detail.svelte:1-120` -- current delete button, native confirmation, and unconditional navigation; add modal, busy/error state, and shared API call.
- `frontend/src/lib/api.ts:1-25` -- existing `deleteGame()` wrapper with credentials, 204 handling, and FastAPI error propagation.
- `tests/test_app.py`, `frontend/tests/interaction-contracts.test.mjs` -- existing backend/frontend contract suites; add deletion, preservation, failure, auth, and cancel coverage.

## Tasks & Acceptance

**Execution:**
- [x] `backend/services/games.py` and cleanup helpers -- implement contained, recoverable deletion of current Game-owned rows/files and preserve Sessions; test storage and commit failure paths.
- [x] `backend/routers/games.py` and related historical lookups -- keep Host-only 404/204/error contracts and prevent deletion from cascading into Session history.
- [x] `frontend/src/components/Detail.svelte` -- replace native confirmation/raw fetch with an accessible modal, explicit cancel/confirm, busy state, and visible failure handling; navigate only after success.
- [x] `tests/test_app.py` and `frontend/tests/interaction-contracts.test.mjs` -- cover successful cleanup, cancellation, Session snapshot preservation, failure consistency, missing Game, and Host authorization.

**Acceptance Criteria:**
- Given a Host opens Game Detail, when Delete game is chosen, then an accessible irreversible-action dialog offers explicit confirm and cancel controls.
- Given the Host cancels, when the dialog closes, then no DELETE request occurs and all current rows/files remain unchanged.
- Given the Host confirms, when deletion succeeds, then current Game-owned rows/files are removed, historical Sessions remain available with their title snapshots, and the Collection refresh no longer shows the Game.
- Given storage or database deletion fails, when the request returns, then the UI shows the failure and the API does not report success while leaving known inconsistent state.
- Given an unknown, unauthenticated, or Guest request, when deletion is attempted, then it receives the existing 404 or Host-auth rejection and no data is removed.

## Design Notes

Filesystem and SQLite cannot share a single transaction. Stage or tombstone files beneath the uploads dataset, commit row deletion only when staging succeeds, restore/reconcile on rollback, and use the existing safe-path/retry conventions so a failure is visible and recoverable. Session history is a separate durable record: never delete it merely because its source Game is gone.

## Verification

**Commands:**
- `python3 -m pytest tests/test_app.py` -- expected: all existing tests plus deletion cleanup, Session preservation, auth, and failure-path tests pass.
- `npm --prefix frontend run check` -- expected: Svelte/TypeScript checks pass.
- `npm --prefix frontend run test:contracts` -- expected: modal/cancel/confirm/API error contracts pass.
- `npm --prefix frontend run build` -- expected: production build succeeds.

## Suggested Review Order

**Deletion boundary and recovery**

- Start at the protected API entrypoint and its 404/204 contract.
  [`games.py:99`](../../backend/routers/games.py#L99)

- Follow service-owned staging, row deletion, rollback, and reconciliation behavior.
  [`games.py:266`](../../backend/services/games.py#L266)

- Inspect staging-directory containment before any persisted asset moves.
  [`games.py:246`](../../backend/services/games.py#L246)

- Verify startup retries cleanup work left by a failed deletion.
  [`main.py:10`](../../backend/main.py#L10)

**Host confirmation flow**

- Trace dialog opening, cancellation, error handling, and success-only navigation.
  [`Detail.svelte:82`](../../frontend/src/components/Detail.svelte#L82)

- Inspect keyboard trapping, focus restoration, explicit danger/cancel actions, and irreversible copy.
  [`Detail.svelte:116`](../../frontend/src/components/Detail.svelte#L116)

**Verification coverage**

- Review asset removal and historical Session preservation through the Host API.
  [`test_app.py:230`](../../tests/test_app.py#L230)

- Check staging, database, journal, containment, and authorization failure cases.
  [`test_app.py:278`](../../tests/test_app.py#L278)

- Confirm frontend modal contracts and shared DELETE API behavior.
  [`interaction-contracts.test.mjs:8`](../../frontend/tests/interaction-contracts.test.mjs#L8)

### Review Findings

- [x] [Review][Patch] Reject deletion while a Session is active [backend/services/games.py:266-310] — **High.** Decision: return `409` whenever the Game has an active `GameSession`, before staging any files or deleting rows. This preserves the Room and its Content until the Host ends the Session explicitly.
- [x] [Review][Patch] Make cleanup and rollback journal persistence fail-safe [backend/services/games.py:129-151,201-229] — **High.** `_write_cleanup_journal()` and `_write_recovery_journal()` catch `OSError`, log it, and return. If tombstone removal or restoration then fails, the operation returns an error but leaves files without a durable record for startup reconciliation, violating the requirement that failures be restored or durably queued.
- [x] [Review][Patch] Journal deletion intent before staging to cover process crashes [backend/services/games.py:266-321] — **High.** Assets are moved before the database transaction and no intent is persisted until an exception path. A process crash after `Path.replace()` (or after commit but before journal persistence) can leave database paths pointing at missing files or committed tombstones that startup cannot discover; the current recovery only replays already-written journals.
- [x] [Review][Patch] Serialize Game deletion with cover and Rulebook replacement [backend/services/games.py:266-298; backend/routers/games.py:131-168] — **High.** Deletion takes no shared per-Game lock, while cover replacement uses `_cover_locks` and Rulebook replacement has no matching lock. Concurrent operations can stage or commit a new asset while deletion removes or restores paths, leaving rows and files inconsistent.
- [x] [Review][Patch] Make cleanup journals concurrency-safe [backend/services/games.py:129-147,201-229,318-322] — **High.** Both journals are single global files replaced wholesale. Overlapping deletions or rollback attempts can overwrite another request’s pending entries, stranding tombstones or losing restoration work.
- [x] [Review][Patch] Treat missing or recreated recovery targets as an unresolved failure [backend/services/games.py:154-182,232-243] — **High.** Recovery skips missing tombstones and can then clear the journal, while `_restore_staged()` treats a missing tombstone as success. Replay also unconditionally replaces the original path, so a newly recreated asset can be overwritten by stale staged data. These paths can report recovery complete while the original asset remains missing or has been replaced incorrectly.
- [x] [Review][Patch] Make post-commit cleanup failure idempotent and explicit [backend/services/games.py:318-321; frontend/src/components/Detail.svelte:100-114] — **Medium.** Once the database commit succeeds, a tombstone unlink failure returns `500`; the UI stays on the detail page and a retry receives `404` even though the Game is already deleted. The API/UI need a reconciliation-safe response or an explicit “deleted, cleanup pending” state rather than a retry path that reports a contradictory failure.
- [x] [Review][Patch] Exercise the delete dialog at runtime rather than with source regexes [frontend/tests/interaction-contracts.test.mjs:8-20; frontend/src/components/Detail.svelte:82-133] — **Medium.** Contract tests verify literals and test `deleteGame()` directly, but never click Confirm or Cancel, dispatch Tab/Shift+Tab/Escape, or assert success-only navigation and error rendering. A handler can omit the DELETE call, issue it from Cancel, or let focus escape while all current assertions pass.
- [x] [Review][Patch] Cover startup and multi-asset recovery failure paths [tests/test_app.py:278-405; backend/main.py:10-15] — **Medium.** Tests do not exercise cleanup replay through FastAPI lifespan, restoration-journal creation/replay, or a database failure with cover plus PDF and extracted text together. Regressions in those paths can pass despite leaving persisted rows and files inconsistent.
