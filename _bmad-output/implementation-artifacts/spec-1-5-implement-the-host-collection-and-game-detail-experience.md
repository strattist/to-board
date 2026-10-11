---
title: 'Implement the Host Collection and Game Detail Experience'
type: 'feature'
created: '2026-09-21'
status: 'done'
review_loop_iteration: 0
baseline_commit: '50d7cc458d0bae257d46c7de1abb2fbed5ebc7b9'
context:
  - '{project-root}/AGENTS.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The Host can reach the existing Collection and Game Detail routes, but the shell and action surfaces do not yet provide the approved responsive behavior, clear state explanations, or complete error handling. The result is a usable prototype rather than a dependable entry point for managing Games.

**Approach:** Harden the existing Svelte shell and components into the approved Host Collection and Game Detail experience, reusing the current authenticated Game DTO, server-owned pipeline states, routes, and upload/delete flows. Add responsive navigation/card behavior and make every Detail action visibly explain when it is available, busy, unavailable, or failed.

## Boundaries & Constraints

**Always:** Keep `/` as the Host Collection and `/games/:id` as Game Detail. Use the existing `GET /api/games` DTO and server pipeline state; keep all management routes behind the existing Host authentication boundary. Preserve Rulebook, Content, Preview, Session, cover, and deletion route contracts. Meet the 32px desktop content inset, 160px minimum responsive card track, 2:3 cards, 16px grid gap, progressive first-load skeletons, visible text status, keyboard activation, 2px focus treatment, and 44px touch targets. Persist sidebar collapse in `localStorage`, support Cmd/Ctrl+B, and close the mobile drawer through Escape or its backdrop.

**Ask First:** Any backend/model/API contract change, new dependency, authentication change, Guest-route behavior change, or change to pipeline-state ownership or deletion semantics.

**Never:** Infer or mutate pipeline state in the frontend; add a second data source; expose Host management to Guests; use color alone for state; leave async action failures silent; introduce a runtime Node server; or collect Guest telemetry.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|-----------------------------|----------------|
| HAPPY_PATH | Host opens `/` or a valid `/games/:id` | Responsive Collection/Detail renders with available actions and text-bearing state | N/A |
| FIRST_LOAD | Game list request pending | Collection shows progressive card skeletons, then cards or the calm empty state | Request failure remains visible as an alert |
| RESPONSIVE_NAV | Desktop, tablet, or mobile viewport; toggle, Cmd/Ctrl+B, Escape, or backdrop | Sidebar uses expanded/collapsed/drawer behavior and preserves preference | Drawer never traps the page behind an undiscoverable overlay |
| ACTION_UNAVAILABLE | Missing Rulebook/extraction/content or busy pipeline | Action is disabled or omitted with a specific calm explanation | No request is issued |
| ACTION_ERROR | Start, generate, upload, or refresh request returns non-2xx | Busy state clears and an accessible, actionable error is shown | Never navigate or claim success |

</frozen-after-approval>

## Code Map

- `frontend/src/App.svelte:17-53` -- route selection, list refresh/polling, sidebar state, keyboard shortcut, and mobile shell; add responsive defaults/backdrop without changing route contracts.
- `frontend/src/components/Sidebar.svelte:2-6` -- Host nav links and collapse/drawer presentation; preserve Collection, Session Log, and Settings labels while adding touch/tooltip/backdrop-compatible behavior.
- `frontend/src/components/Collection.svelte:1-38` -- add-game form, skeleton/empty states, and grid; align layout with the 160px minimum and responsive spacing contract.
- `frontend/src/components/GameCard.svelte:6-82` -- authenticated cover fallback, initials, title/status, Space activation, and focus ring; refine overlay and touch/hover presentation.
- `frontend/src/components/Detail.svelte:8-198` -- Rulebook, Content, Preview, Session, cover, and deletion actions; centralize busy/error handling and state-specific explanations while retaining the existing delete flow.
- `frontend/src/components/StatusBadge.svelte:1-2` -- canonical pipeline labels and loading indicator; reuse rather than duplicating state vocabulary.
- `frontend/src/lib/api.ts:1-26` -- typed fetch/error wrapper and existing Game DTO; add only wrappers needed to make Detail actions checkable and consistent.
- `frontend/tests/interaction-contracts.test.mjs:1-110` -- dependency-free frontend contracts; extend coverage for responsive navigation, grid/card semantics, and Detail action gating/errors.

## Tasks & Acceptance

**Execution:**
- [x] `frontend/src/App.svelte`, `frontend/src/components/Sidebar.svelte` -- implement responsive sidebar defaults, persisted collapse, keyboard toggle, mobile backdrop/close, active navigation, and accessible focus/touch behavior.
- [x] `frontend/src/components/Collection.svelte`, `frontend/src/components/GameCard.svelte` -- implement the responsive grid, skeleton/empty states, cover/initials fallback, title truncation, status placement, and hover/focus/touch card treatment.
- [x] `frontend/src/components/Detail.svelte`, `frontend/src/lib/api.ts` -- make Preview/Session/Rulebook/Content actions state-aware with busy, non-2xx, and success-only navigation behavior and calm explanations.
- [x] `frontend/tests/interaction-contracts.test.mjs` -- cover the I/O matrix and accessibility/source contracts without weakening existing deletion and upload coverage.

**Acceptance Criteria:**
- Given an authenticated Host opens the app, when the shell loads, then Collection is the default route and navigation exposes Collection, Session Log, and Settings with the prescribed responsive sidebar behavior.
- Given a Host views Collection, when data is loading, empty, or populated, then skeletons, calm empty copy, or accessible 2:3 cards render with responsive tracks, cover fallback, title truncation, status text, and keyboard activation.
- Given a Host views Game Detail, when pipeline prerequisites change, then Rulebook, Content, Preview, and Session actions are enabled, disabled, or explained from the server DTO without client state inference.
- Given any Detail action succeeds or fails, when the request completes, then busy indicators and accessible calm messaging reflect the result and navigation occurs only after success.
- Given any Host interactive control receives focus or a mobile drawer is opened, when keyboard or pointer input is used, then focus/touch targets and Escape/backdrop closure meet the UX contract.

## Design Notes

Treat the existing Game payload as the single rendering model. Keep action availability declarative from `pipeline_state`, `rulebook.has_extracted_text`, and content flags; route all requests through the shared API error wrapper so FastAPI `detail` messages reach the UI. Do not broaden this story into backend schema or pipeline changes.

## Verification

**Commands:**
- `npm --prefix frontend run check` -- expected: Svelte and TypeScript checks pass.
- `npm --prefix frontend run test:contracts` -- expected: existing and new Collection/Sidebar/Card/Detail contracts pass.
- `npm --prefix frontend run build` -- expected: production bundle succeeds.
- `python3 -m pytest tests/test_app.py` -- expected: existing Host/Guest API contracts remain green.

## Suggested Review Order

**Host shell and navigation**

- Refresh and route state coordinate responsive defaults, drawer lifecycle, and loading/error boundaries.
  [`App.svelte:19`](../../frontend/src/App.svelte#L19)

- Sidebar navigation preserves browser semantics while adding active routes, drawer presentation, and touch targets.
  [`Sidebar.svelte:11`](../../frontend/src/components/Sidebar.svelte#L11)

**Game actions and state**

- Detail derives action availability from the server DTO and reports busy, failure, and success states.
  [`Detail.svelte:45`](../../frontend/src/components/Detail.svelte#L45)

- Preview owns its single authenticated fetch and renders loading, content, or an accessible error.
  [`Preview.svelte:9`](../../frontend/src/components/Preview.svelte#L9)

- Shared wrappers keep Host credentials, endpoint contracts, and FastAPI error propagation consistent.
  [`api.ts:25`](../../frontend/src/lib/api.ts#L25)

**Collection presentation**

- Collection renders progressive loading, error suppression, empty copy, and responsive card tracks.
  [`Collection.svelte:38`](../../frontend/src/components/Collection.svelte#L38)

- Cards retain keyboard activation, cover fallback, semantic status, and touch/hover overlay behavior.
  [`GameCard.svelte:68`](../../frontend/src/components/GameCard.svelte#L68)

**Verification and tracking**

- Contracts assert accessibility seams, API request shapes, and endpoint-specific failures.
  [`interaction-contracts.test.mjs:14`](../../frontend/tests/interaction-contracts.test.mjs#L14)

### Review Findings

- [x] [Review][Patch] Mobile navigation leaves keyboard focus behind the open drawer [frontend/src/App.svelte:61-62] — opening the drawer does not move focus into it or make the obscured page inert, so keyboard users can interact with controls behind the backdrop.
- [x] [Review][Patch] Preview and Start session remain enabled during a busy pipeline [frontend/src/components/Detail.svelte:37-50,192-193] — the busy-state matrix requires actions to be disabled or explained while extraction or generation is active, but these controls gate only on published-content flags.
- [x] [Review][Patch] Game-card titles are invisible at rest [frontend/src/components/GameCard.svelte:76,81] — the title overlay has `opacity:0` until hover/focus, contrary to the requirement that populated cards show their title without interaction.
- [x] [Review][Patch] Failed uploads can retain a previous success message [frontend/src/components/Detail.svelte:106-151,201] — Rulebook and cover upload handlers do not clear `actionStatus` before starting, so a later upload error can appear alongside stale success feedback.
- [x] [Review][Patch] Preview content is not refreshed when the route id changes [frontend/src/components/Preview.svelte:5-13] — fetching only in `onMount` allows a reused `/games/:id/preview` component to keep another game's content after SPA navigation.
- [x] [Review][Patch] Cmd/Ctrl+B toggles the sidebar while editing fields [frontend/src/App.svelte:61] — the global shortcut does not ignore editable targets, so typing the shortcut in Settings or another input changes shell state unexpectedly.
- [x] [Review][Patch] Collection errors discard already loaded cards [frontend/src/components/Collection.svelte:38] — a refresh failure renders an empty `aria-hidden` grid instead of preserving usable stale cards alongside the visible alert.
- [x] [Review][Patch] Action success can be reported after its refresh was superseded [frontend/src/App.svelte:19-30,frontend/src/components/Detail.svelte:57-65] — `refreshAfterAction` treats a superseded refresh as success even though it did not confirm the post-action DTO.
- [x] [Review][Defer] Create flow can report a persisted game as failed when refresh fails [frontend/src/lib/create-flow.js:6-9] — deferred, pre-existing.
- [x] [Review][Defer] localStorage access is not guarded in restricted browsers [frontend/src/App.svelte:40-51] — deferred, pre-existing behavior.
