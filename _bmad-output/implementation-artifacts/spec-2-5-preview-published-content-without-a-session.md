---
title: 'Preview Published Content Without a Session'
type: 'feature'
created: '2026-09-28'
status: 'done'
review_loop_iteration: 0
baseline_commit: 'eeee42186cd256488295d1680b9fe532e2169889'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Story 2.5 is still marked backlog even though its Host Preview route and view already exist. Current tests do not prove that requesting Preview before a Session leaves session data untouched, returns the complete pair Guest Rooms receive, or keeps Draft content private.

**Approach:** Preserve the existing local, read-only Preview flow. Add focused backend and frontend contract coverage for the Story 2.5 boundaries, and make only the smallest implementation correction if that coverage finds a real mismatch.

## Boundaries & Constraints

**Always:** Require Host authentication. Read the complete Published Quick-start Guide and Cheat Sheet from local SQLite. Preview must not create a Session or Room, call a cloud provider, or expose Draft or Rejected content. Render both documents with the shared sanitized Markdown component and keep Preview read-only.

**Ask First:** A change to authentication, the API response shape, database schema, dependencies, or the Preview interaction and presentation.

**Never:** Add editing, Publish, Reject, generation, or Session controls to Preview; return a partial Published pair; fall back to Draft content.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Published pair, no Session | Complete Published pair; no existing Session | Preview returns both documents and leaves Session/Room state unchanged | N/A |
| No complete Published pair | Draft-only, Rejected, or incomplete Published fields | Preview does not return content | Standard 404 resource response |
| Guest or unauthenticated request | No valid Host identity | Preview content is not returned | 401 or Authentik redirect |

</frozen-after-approval>

## Code Map

- `_bmad-output/planning-artifacts/epics.md:529-549` — Story 2.5 intent and acceptance criteria.
- `_bmad-output/implementation-artifacts/epic-2-context.md` — Published pair invariants, Host/Guest boundary, and local-storage constraints.
- `backend/routers/games.py:280-284` — Host-protected Preview endpoint reads Game and Content and returns only the Published pair; currently returns 404 if either document is absent.
- `backend/services/sessions.py` and `backend/routers/room.py` — Session eligibility and Guest Room response used to compare the same pair.
- `frontend/src/components/Detail.svelte:51,106-111,240-244` and `frontend/src/App.svelte:73,76` — Preview entry point, route, and published-content gate.
- `frontend/src/components/Preview.svelte:1-32`, `frontend/src/lib/api.ts:53,57`, and `frontend/src/lib/Markdown.svelte:1-8` — Preview loading/error states, typed request, and shared sanitized rendering.
- `tests/test_app.py:950-1006` — Existing busy-state and incomplete-pair coverage; the current success test creates a Session before requesting Preview.
- `frontend/tests/interaction-contracts.test.mjs:152-173,338-340,456` — Existing Detail/API contracts; no direct contract currently protects Preview rendering or read-only state.

## Tasks & Acceptance

**Execution:**
- [x] `tests/test_app.py` — Verify Preview returns both Published fields before any Session exists, creates no Session or provider work, matches both documents served by a Guest Room, returns 404 for Draft-only content, and rejects unauthenticated access.
- [x] `frontend/tests/interaction-contracts.test.mjs` — Protect use of the shared Markdown renderer for both documents, read-only presentation, and a clear unavailable state.

**Acceptance Criteria:**
- Given a Game has a complete Published pair and no Session, when the Host opens Preview, then both Published documents are returned and no Session or Room is created.
- Given the same Game has an active Guest Room, when Host Preview and Guest Room content are read, then both expose the same Published Quick-start Guide and Cheat Sheet.
- Given Published content is absent or incomplete while Draft or Rejected content exists, when Preview is requested, then it shows a clear unavailable state or returns 404 without exposing that content.
- Given the requester is unauthenticated or a Guest, when Host Preview is requested, then Host authentication rejects or redirects the request.
- Given Preview content is rendered, when the Host views either document, then it uses the shared sanitizer and exposes no content mutation or generation controls; serving it makes no cloud call.

## Spec Change Log

## Verification

**Commands:**
- `rtk uv run --no-cache pytest -q tests/test_app.py` — Passed: 94 tests; 2 dependency deprecation warnings.
- `rtk npm --prefix frontend run test:contracts` — Passed: frontend interaction contracts passed.
- `rtk npm --prefix frontend run check` — Passed: 0 errors and 0 warnings.

## Suggested Review Order

**Published data boundary**

- Preview returns both Published documents without creating session state or changing Content.
  [`test_app.py:972`](../../tests/test_app.py#L972)

- Guest Room parity confirms both audiences receive the same Published pair.
  [`test_app.py:1014`](../../tests/test_app.py#L1014)

**Unavailable and access boundaries**

- Draft-only, Rejected, and incomplete pairs return 404 without mutating stored content.
  [`test_app.py:1037`](../../tests/test_app.py#L1037)

- Host authentication blocks unauthenticated Preview requests before content is returned.
  [`test_app.py:1077`](../../tests/test_app.py#L1077)

**Preview rendering contract**

- The route preserves the Game ID from Detail navigation into the Preview component.
  [`interaction-contracts.test.mjs:64`](../../frontend/tests/interaction-contracts.test.mjs#L64)

- Both sanitized documents render only in the successful, read-only content branch.
  [`interaction-contracts.test.mjs:106`](../../frontend/tests/interaction-contracts.test.mjs#L106)

**Sprint tracking**

- Story 2.5 moves to review after the verified acceptance checks.
  [`sprint-status.yaml:51`](sprint-status.yaml#L51)
