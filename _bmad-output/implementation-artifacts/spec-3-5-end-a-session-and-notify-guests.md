---
title: 'End a Session and Notify Guests'
type: 'feature'
created: '2026-10-11'
status: 'done'
baseline_commit: '2917560add816d8b8f0f03b93ca38582d567ad67'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-3-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The end-session plumbing exists (`POST /api/sessions/:id/end`, Room ended payload, SSE `session-ended`) but the Story 3.5 ACs are not met. The Host confirms with a native `confirm()`, a failed or network-error end is not handled cleanly, a repeated end re-notifies, and the Guest "This session has ended." block is inserted already populated, so screen readers may not announce it (deferred from 3.4).

**Approach:** Harden the end flow end to end. The backend persists first and notifies only after a successful commit. The Host gets a destructive confirmation dialog that shows ended only when the server confirms. The Room announces the ended state through a persistent `aria-live="polite"` region. Tests cover each AC.

## Boundaries & Constraints

**Always:** Routers call services; `ended_at` is ISO 8601 UTC. Guest routes stay unauthenticated and store nothing about Guests. Notification happens only after the commit succeeds. Ending an already-ended Session is idempotent (200, current record, no second notification). The ended Room exposes only title and wordmark, never Draft or Published content. Dialog targets are at least 44px and follow the Detail.svelte modal styling and danger tokens.

**Never:** Add dependencies, polling, WebSocket, or new endpoints. Do not change auth or Guest tracking. Do not add an End action to QR Reveal or Game Detail (stays on Session detail). Do not touch the `#6d6d6d` contrast token or the AGENTS.md edit (deferred).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Confirm end | Active Session, Host confirms | `ended_at` set, response `active: false`, Guests notified, Session shown as Ended | N/A |
| Cancel | Dialog open, Cancel or Escape | Dialog closes, Session and Room unchanged, no request sent | N/A |
| End fails | Commit error or network error | Host sees a clear error; Session still shown Active; no SSE sent | 500 "Session could not be ended." with rollback |
| Already ended | POST end on ended Session | 200 with existing `ended_at`; no SSE | N/A |
| Guest connected | Open Room, Host ends | `session-ended` sent, stream closes, content replaced, "This session has ended." announced via live region | N/A |
| Guest arrives after | Ended slug | Room shows ended state at once from the 200 payload, no SSE needed | N/A |

</frozen-after-approval>

## Code Map

- `backend/services/sessions.py:68` -- `end_session(record)` only sets `ended_at`; add the persist step with rollback and a 500 on `SQLAlchemyError`. Returns whether the state changed.
- `backend/routers/sessions.py:62` -- `close_session`; call the service, notify only when it changed, and drop the inline commit. Do not change `serialize`.
- `backend/routers/room.py` -- `room_payload`, `/events` and `notify_session_ended` already meet the SSE ACs. Read-only reference; do not change.
- `frontend/src/components/SessionDetail.svelte` -- replace `confirm()` and the unguarded `r.json()` with a dialog, error state and an in-flight guard. Reload the session from the response only when `active` is false.
- `frontend/src/components/Detail.svelte:302` -- modal markup and CSS to mirror (`.modal-backdrop`, `.modal`, `.danger`, `.confirm`).
- `frontend/src/components/RoomPage.svelte` -- add one always-mounted visually hidden `role="status" aria-live="polite"` region outside the `{#if}` and set it on ended. Remove `aria-live` from the visible ended block. Keep "This room is not available." (asserted in contracts).
- `tests/test_app.py:1268, 2607` -- existing close/ended tests to extend.
- `frontend/tests/room-page.dom.test.ts`, `frontend/tests/interaction-contracts.test.mjs` -- DOM and source contracts to extend; add `session-detail.dom.test.ts` beside them.

## Tasks & Acceptance

**Execution:**
- [x] `backend/services/sessions.py`, `backend/routers/sessions.py` -- commit-then-notify, idempotent end, rollback and a clear 500 on a persistence failure -- AC: failure is never reported as ended
- [x] `tests/test_app.py` -- end sets UTC `ended_at`; Room and events resolve ended; SSE delivered once on end and not on a repeat; commit failure returns 500, leaves `ended_at` null and sends no event; end requires Host; unknown id 404
- [x] `frontend/src/components/SessionDetail.svelte` -- destructive dialog ("End this session? The room will close for all guests."), focus on Cancel, Escape cancels, error alert, button disabled while pending
- [x] `frontend/src/components/RoomPage.svelte` -- persistent live region announcing "This session has ended."; ended view is title, text and wordmark only
- [x] `frontend/tests/session-detail.dom.test.ts`, `frontend/tests/room-page.dom.test.ts`, `frontend/tests/interaction-contracts.test.mjs` -- cancel sends nothing; confirm POSTs and shows Ended; failure keeps Active with error; Room swaps content on SSE, closes the stream, region announces; ended-on-load needs no stream; no `confirm(` in SessionDetail

**Acceptance Criteria:**
- Given an active Session, when the Host picks End session then Cancel, then the Session and Room are unchanged
- Given the Host confirms and the end succeeds, when a Guest requests the Room, then only the ended payload is returned and the QR route shows ended
- Given connected Guests, when the Session ends, then each receives `session-ended`, its stream closes and its page changes without a refresh
- Given the end fails, when the server reports it, then the Host sees an error and the Session is not shown as ended

## Implementation Notes

- `end_session(session, record)` now commits, rolls back with a 500 on `SQLAlchemyError`, and returns True only when it changed state; the router notifies only then.
- Room: one always-mounted `role="status"` region carries "This session has ended."; unavailable keeps its own `aria-live` block.
- `SessionDetail.svelte` rewritten with a modal dialog; ended is shown only when the response has `active: false`.
- Verified: pytest 132 passed, test:dom 18, contracts, check, build, prek all green.

## Review Triage Log

| Finding | Verdict | Route | Evidence |
|---|---|---|---|
| Concurrent end requests both notify (check-then-commit) | medium | patch | Fixed with a conditional `UPDATE ... WHERE ended_at IS NULL` and `rowcount == 1`. |
| Notify raise or refresh failure turns a committed end into a 500 | medium | patch | `refresh` moved inside the try; notify wrapped and logged. Tests added. |
| No test drives the real SSE registry on end | medium | patch | Added a test that registers a queue and asserts exactly one `session-ended`. |
| Focus lost after success or failure; background not inert | low | patch | Focus returns to the End button or heading; `inert` while the dialog is open. Tests added. |
| Raw browser/array error text could reach the Host | low | patch | `detail()` accepts strings only; one fixed message otherwise. |
| 200 with `active: true` and focus return untested | low | patch | Tests added. |
| Failing-commit test leaks the patch on assertion failure | low | patch | Uses `monkeypatch.context()`. |
| Unavailable block inserted already populated for `aria-live` | low | defer | Pre-existing from Story 3.3; outside the ended-state ACs. |
| Backdrop click does not close the dialog | low | rejected | Destructive dialog; accidental dismissal is not wanted, and the fix adds behavior. |
| Rollback itself raising / `record.id` read after rollback | low | patch | Session id captured before the try (rollback-raises case rejected: unreachable in normal use). |
| Retry after failed notify never re-notifies | false | n/a | EventSource reconnects and the server replays `session-ended` for ended Sessions. |
| Save allowed on ended Session | false | n/a | Players and outcomes are meant to be recorded after the game; pre-existing. |
| Event arrives while loading, then fetch fails | false | n/a | The stream opens only after the fetch succeeds. |
| Service raises HTTPException; missing imports | false | n/a | Matches `create_session`; imports exist in the file. |
| Contract regexes brittle | false | n/a | DOM tests cover the behaviors. |
| Live-region container toggles display | low | rejected | Speculative; the region node stays mounted and its text changes. |

## Verification

**Commands:**
- `python3 -m pytest` -- expected: all pass including new end tests
- `npm --prefix frontend run test:dom` -- expected: all DOM tests pass
- `npm --prefix frontend run test:contracts` -- expected: contracts pass
- `npm --prefix frontend run check` -- expected: no type errors
- `npm --prefix frontend run build` -- expected: build succeeds
- `uvx prek==0.5.3 run --all-files` -- expected: hooks pass

**Manual checks:**
- With a Room open on a phone-width tab, end the Session from `/sessions/:id`: the Room changes to the ended state without a refresh.
