---
title: 'Start a Session for a Ready Game'
type: 'feature'
created: '2026-09-30'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-3-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Story 3.1 asks that the Host can start a Session for a Game with Published Content, with a UUID, title snapshot, unique Room slug and ISO 8601 UTC `started_at`, persisted immediately; a second start gets 409 and leaves the active Room unchanged; Guests and unauthenticated callers cannot create Sessions; failures never look like success. Session creation already exists (`backend/services/sessions.py`, `backend/routers/sessions.py`), but the API returns `started_at`/`ended_at` as naive timestamps (`2026-09-30T19:00:33.272852`, no UTC marker), and the 409, auth, persistence and failure behaviors are untested.

**Approach:** Make Session timestamps serialize as explicit UTC ISO 8601, and add backend tests that pin each Story 3.1 acceptance criterion. Change other production code only where a test finds a real mismatch.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Start, ready Game | Published pair, no active Session | 201; UUID `id`, title snapshot, `<prefix>-<4 base36>` slug, `started_at` ends in UTC offset/`Z`; row persisted | N/A |
| Start, active exists | Active Session for the Game | Refused; existing Session and Room unchanged | 409 |
| Start, no Published pair | Nothing published | Refused | 422 "Published Content is required to start a Session." |
| Start, unauthenticated | Auth enabled, no token | No Session row created | 401 |
| Start, persistence fails | Commit raises | No success body; no Session row | 500 surfaced, nothing persisted |

</frozen-after-approval>

## Implementation Notes

- Investigation: `create_session` checks Published Content (422) and an active Session (409), and slugs come from `make_room_slug`. The Session router depends on `require_host`. The Room route has no mutating endpoints.
- Not in scope: disabling the Start button when a Session is active. The Game payload carries no active-Session flag, and the AC allows rejection with 409; the UI already surfaces the server error.
- Changed: `backend/routers/sessions.py` (`utc_iso` makes `started_at`/`ended_at` explicit UTC; the browser previously parsed the naive value as local time). `backend/services/sessions.py` (`create_session` catches `SQLAlchemyError`, rolls back, logs the traceback and raises a clear 500; the active-Session check, slug lookup and commit all sit inside the handler). Walkthrough review found a real double-start race (6 simultaneous starts created up to 6 active Sessions), so the database now enforces it: `backend/models/session.py` declares a partial unique index `ux_gamesession_one_active_per_game` on `game_id WHERE ended_at IS NULL`, and `backend/db/init.py` adds it to existing databases at startup (skipped with an error log if a Game already has several active Sessions). An `IntegrityError` on that index returns 409; one on `room_slug` retries with a new slug, up to 3 attempts.
- Tests: 6 added at the end of `tests/test_app.py` (identity, slug and UTC timestamp; 409 keeps the active Room; Host-only; failed save; 6 concurrent starts create one active Session; index restored on an existing database). Suite: 122 passed; frontend contracts and prek pass. Manual checks on the Docker stack passed for the UTC timestamp, the 409, the double-start and the index.
- Review ran inline plus a walkthrough (no subagents). Known gaps: the router's Game lookup in `start_session` sits outside the handler, so a database lock there gives the generic "Request failed (500)" (safe, cosmetic); the duplicate-active-Sessions startup path and the slug-collision retry have no test.
- Deferred to Story 3.2: the QR Reveal and Copy URL use `location.origin` instead of `APP_BASE_URL` (see `deferred-work.md`).
- Committed by the user (`98584da` and follow-up); no commit made here.

## Verification

**Commands:**
- `.venv/bin/python -m pytest -q` -- expected: all tests pass
- `npm --prefix frontend run test:contracts` -- expected: contracts pass
