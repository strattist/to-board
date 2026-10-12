---
title: 'Browse and Filter Session History'
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

**Problem:** Story 4.3 asks that Session Log lists Sessions newest first, each showing Game title, date, players, outcome entries (in saved order, repeats kept) and active or ended state; that the Host can filter by Game and clear the filter; that Sessions of a deleted Game stay readable by title snapshot and filterable; that empty and no-match states are calm and specific; and that the route is Host-only. `GET /api/sessions[?game_id=]` already returns newest first, but Session Log shows only title, date and state, has no filter, no player/outcome display, no loading or error state, and nothing tests ordering, filtering, deleted-Game history or Guest isolation.

**Approach:** Pin the API behaviour with backend tests (deterministic order, filter, deleted Game, Host-only). Rebuild `SessionPages.svelte` as the Session Log: filter options come from the Sessions' own `game_id` + title snapshot (so a deleted Game stays filterable), the filtered list is fetched with `?game_id=`, entries render players and an ordered outcomes list, and empty/no-match/error states are specific. No schema change.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Load log | several Sessions | newest `started_at` first; each entry: title, date, state text, players if any, outcomes if any | N/A |
| Same start time | equal `started_at` | order is stable (tie broken by `id`) | N/A |
| Filter | choose Game | only that Game's Sessions; Clear restores the full list | N/A |
| Repeated outcomes | `["Alex won", "Alex won"]` | both shown, in order, as separate list items | N/A |
| Deleted Game | Game deleted after Sessions | entry shows title snapshot; listed and filterable by `game_id` | N/A |
| No Sessions | empty DB | "No sessions yet" text with how one starts | N/A |
| No match | filter with zero Sessions | "No sessions for this game" text and a Clear filter button | N/A |
| Load failure | API non-2xx / network | `role=alert` message, no empty-state claim | retry by reload |
| Unauthenticated | auth enabled, no Host | 401; `/api/room` payloads carry no history | N/A |

</frozen-after-approval>

## Implementation Notes

- Investigation: `list_sessions` in `backend/routers/sessions.py` already filters on `game_id` and orders `started_at.desc()`; add `GameSession.id` as tie-break. Game deletion (`_delete_game_locked`, `backend/services/games.py`) keeps Session rows and snapshots (`tests/test_games.py`). `SessionPages.svelte` is the `/sessions` route in `App.svelte`; entries link to `/sessions/{id}` (SessionDetail). `Session` type in `frontend/src/lib/api.ts`.
- Decisions: filter options derived from the unfiltered list (distinct `game_id`, latest snapshot title) rather than the Games API, so deleted Games remain selectable; filtering uses the existing `?game_id=` query; native `<select>` with a visible label for accessibility; state shown as text.
- Out of scope: pagination, Session Detail read-only presentation and responsive polish (Story 4.4).
- Changed: `backend/routers/sessions.py` (`id` tie-break), `frontend/src/components/SessionPages.svelte` (rebuilt Session Log), `tests/test_sessions.py` (+4), `frontend/tests/session-log.dom.test.ts` (+3). Suite: 159 passed; frontend check, contracts and DOM (32) pass. Not committed (user instruction). Branch `feat/4-3-browse-and-filter-session-history`; sprint-status 4-3 set to `review`.
- Review ran inline (no subagents authorized). Patched: stale responses from overlapping filter changes are ignored.

## Review Triage Log

- medium (patched): overlapping filter requests could show an older response; a request counter now discards stale results.
- low (rejected): filter options come from Sessions only, so a Game with no Sessions is not listed -- nothing to filter to.
- low (rejected): no pagination for very long logs -- not in the acceptance criteria; single Host LAN scale.
- low (rejected): Session Log rows are not responsive-polished or table-structured -- Story 4.4 owns presentation.
