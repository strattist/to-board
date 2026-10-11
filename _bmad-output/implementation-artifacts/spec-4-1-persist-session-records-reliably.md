---
title: 'Persist Session Records Reliably'
type: 'feature'
created: '2026-10-11'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Story 4.1 asks that each started Session is persisted immediately with UUID, Game reference, title snapshot and UTC `started_at`; survives API restarts (active stays active) and TrueNAS updates via bind-mounted datasets only; stays readable after its Game is deleted; and a persistence failure never shows a Room. Creation, snapshot, failure and one-active behavior exist from Epic 3 and are tested, but restart durability, active-state after restart and the bind-mount-only guarantee have no test.

**Approach:** Add backend tests pinning the untested acceptance criteria: a Session read through a fresh engine on the same database file after restart, active state preserved, and `docker-compose.yml` persisting data only through the two named dataset bind mounts. Change production code only where a test finds a real mismatch.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Restart, active Session | Session started, app restarted on same db file | Same id, snapshot, slug, `started_at`; `ended_at` null; `active` true; second start still 409 | N/A |
| Restart, ended Session | Session ended, app restarted | `ended_at` retained, `active` false | N/A |
| Compose persistence | `docker-compose.yml` | `/data/db` and `/data/uploads` are `bind` mounts; no top-level named volumes | N/A |
| Game deleted | Historical Session, Game deleted | Snapshot and Room state readable (already covered in `tests/test_games.py`) | N/A |

</frozen-after-approval>

## Implementation Notes

- Investigation: `GameSession` (`backend/models/session.py`) stores id, `game_id`, `game_title_snapshot`, `room_slug`, `started_at`, `ended_at`. `create_session` commits before returning and converts `SQLAlchemyError` to a 500 (tested). Game deletion leaves Session rows in place (SQLite foreign keys are not enforced) and `tests/test_games.py` already pins the snapshot. Restart is `initialize_database()` over the same file; compose already uses bind mounts for `/data/db` and `/data/uploads`.
- Not in scope: schema changes (the `game_id` foreign key stays), Session history UI (4.3/4.4), players and outcomes (4.2).

- Changed: `tests/test_sessions.py` only (3 tests): an active Session read after a restart keeps id, snapshot, slug and `started_at`, stays active, still returns 409 on a second start and keeps its Room open; an ended Session stays ended with the same `ended_at`; `docker-compose.yml` has only the `/data/db` and `/data/uploads` bind mounts, no top-level named volumes and no short-form `:/data/` volume. No production code changed: every test passed against existing behavior. Suite: 139 passed.
- Review ran inline (no subagents; none were authorized). Known limit: the restart is simulated with `engine.dispose()` plus a fresh lifespan in-process, and the compose check is a text scan, not a YAML parse (PyYAML is not in `requirements.txt`). Real dataset durability on TrueNAS is not exercised here.
- Not committed (user instruction: leave changes in the working tree).

## Review Triage Log

- low (rejected): compose test parses text, so reformatting `docker-compose.yml` could break it -- it fails loudly rather than passing falsely, and adding a YAML dependency is not warranted.
- low (rejected): restart is simulated in-process -- covers reopening the same SQLite file and startup recovery, which is the only application-owned part of AC2.

## Verification

**Commands:**
- `python3 -m pytest -q` -- expected: all tests pass
