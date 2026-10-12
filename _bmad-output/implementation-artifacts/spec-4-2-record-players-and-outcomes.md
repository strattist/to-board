---
title: 'Record Players and Outcomes'
type: 'feature'
created: '2026-10-12'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Story 4.2 asks that the Host records up to 12 free-text player names and up to 20 ordered free-text outcome entries (zero allowed) on a Session, active or ended, with a clear `422` for invalid input that leaves stored values unchanged, and Host-only access. `PATCH /api/sessions/{id}` and the Session Detail form already store `players_json`/`outcomes_json`, but nothing tests it, the list-limit `422` is a raw Pydantic detail list the UI cannot show, values are not trimmed server-side, entries have no length cap, and the form splits players on commas so a name containing a comma is silently broken into two.

**Approach:** Pin the acceptance criteria with backend tests and a DOM test; make the `422` messages clear strings; trim entries and cap each entry's length on the server; enter players one per line in the form so entries are retained as typed. Existing storage, route and auth stay as they are.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Save on active Session | 3 players, 2 outcomes | 200; stored and returned in submitted order; GET returns the same; survives restart | N/A |
| Save on ended Session | `ended_at` set, edit players, reorder/remove outcomes | 200; `ended_at` and `active` unchanged; Room still ended | N/A |
| Zero entries | `outcomes: []` | 200; outcomes cleared | N/A |
| Partial update | only `players` sent | `outcomes` unchanged | N/A |
| Limits | 12 players / 20 outcomes | 200 | N/A |
| Over limit | 13 players or 21 outcomes | 422 with a string `detail` naming the limit; stored values unchanged | rejected before write |
| Blank entry | `["Alex", "  "]` | 422 string `detail`; stored values unchanged | rejected before write |
| Overlong entry | player > 100 chars or outcome > 200 chars | 422 string `detail`; unchanged | rejected before write |
| Padding | `["  Alex  "]` | stored as `"Alex"` | N/A |
| Name with comma | form line `Smith, Jo` | one player `Smith, Jo` | N/A |
| Unauthenticated | auth enabled, no Host | 401; Guest Room payload carries no players/outcomes | N/A |

</frozen-after-approval>

## Implementation Notes

- Investigation: `GameSession.players_json`/`outcomes_json` (`backend/models/session.py`), `SessionUpdate` + `update_session_record` (`backend/routers/sessions.py`), `update_metadata` (`backend/services/sessions.py`), `SessionDetail.svelte` (players comma-split, outcomes newline-split), `Session` type in `frontend/src/lib/api.ts`. No schema change. `/api/room` serialization is separate and must not expose metadata (assert in test).
- Decisions: per-entry caps 100 (player) / 200 (outcome) characters, server-side trim; validation lives in the router/service so the `detail` is a string the existing `detail()` helper in the form can show.
- Changed: `backend/routers/sessions.py` (`clean_entries`: count, trim, blank and length checks before any write, string `detail`; the unused Pydantic `Field` limits were dropped so the limit message is ours), `frontend/src/components/SessionDetail.svelte` (players one per line in a textarea, labels state the limits), `tests/test_sessions.py` (+6 tests, 11 cases), `frontend/tests/session-detail.dom.test.ts` (+3). No schema change. Suite: 150 passed; frontend check, contracts and DOM (31) pass. Backend tests run with the repo `.venv` (`python3` on PATH resolves to another project's venv).
- Review ran inline (no subagents authorized). Not committed (user instruction). Branch `feat/4-2-record-players-and-outcomes`; sprint-status 4-2 set to `review`, 4-1 to `done`.
- Post-review patches (bmad-review): entries containing a line break are rejected with `422` (the form splits on newlines, so they would reload as several entries); a failed commit on `PATCH` rolls back and returns a clear `500` like create/end; the save message is `role=status` (or `alert` on failure) and clears on edit; tests added for exactly 100/200 characters, line-break rejection, commit failure and the ended Room payload keys. Suite: 155 passed, DOM 29 passed.
- Not patched: last-write-wins across two tabs, duplicate players allowed (intentional: two guests may share a name), no read-only ordered list (4.4), 100/200 caps recorded here as a decision not in the PRD.

## Review Triage Log

- low (rejected): non-string list items still return Pydantic's list-shaped `422` detail -- the form never sends them and it is still a `422`; the UI falls back to "Could not save."
- low (rejected): saved order is shown only inside the editable fields, not as a separate read-only list -- 4.4 owns the history presentation.
- low (rejected): `ensure_ascii` JSON escaping of non-ASCII names -- round-trips correctly, only affects raw DB text.

## Verification

**Commands:**
- `.venv/bin/python3 -m pytest -q` -- expected: all tests pass
- `npm --prefix frontend run check && npm --prefix frontend run test:dom` -- expected: pass
