---
title: 'Use the Mobile Guest Room'
type: 'feature'
created: '2026-10-07'
status: 'done'
baseline_commit: 'f02c03d9b5190da945d37a1ec2c96967fc8e0e7e'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-3-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Story 3.4 asks that a Guest on a phone reads the Quick-start Guide and Cheat Sheet in a Room that is a centered 640px column, with sticky tabs, 44px touch targets, no horizontal scroll at 375px, sanitized Markdown, and a clear unavailable state. `RoomPage.svelte` (from 3.3) has the basic tabs, but nothing proves or enforces these rules: Markdown prose, code, tables and images can overflow, tabs lack ARIA and focus rings, `aria-live` wraps the whole page, and there is no DOM test harness.

**Approach:** Harden `RoomPage.svelte` and the shared `Markdown.svelte` against the ACs, and set up the Vitest + @testing-library/svelte + jsdom harness decided in the Epic 2 retro (separate `test:dom` script, `test:contracts` kept) to test Room behavior.

## Boundaries & Constraints

**Always:** Room stays free of Host chrome, forms, storage, cookies and external requests. Markdown renders only through the shared sanitizing `Markdown.svelte`. Tabs toggle with no navigation. Interactive targets are at least 44px. Use design tokens from DESIGN.md (`#15141b`, `#a277ff`, `#6d6d6d`, `#edecee`). Honor `prefers-reduced-motion`.

**Never:** Add other dependencies than Vitest, `@testing-library/svelte`, `@testing-library/jest-dom` (optional) and jsdom as devDependencies. No Playwright. No backend, SSE or auth change. No Draft/Rejected Content fallback. Do not build the ended-state flow (Story 3.5) beyond keeping what exists working.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Active Room | 200 with both Markdown fields | Title, wordmark, two tabs; Quick-start shown first | N/A |
| Tab switch | Select "Cheat Sheet" | Cheat Sheet visible, Quick-start hidden, no navigation, `aria-selected` updates | N/A |
| Unsafe Markdown | `<script>`, `onerror=`, `javascript:` link | Stripped before render; nothing executes | N/A |
| Long content | Long word/URL, wide table, `pre`, big image | Wraps or scales within the column; no horizontal overflow | N/A |
| Unavailable | 404 / network failure | "This room is not available." with wordmark; no content, tabs or Draft text | Never shows stale content |
| Ended | `ended: true` | Existing ended view (title, "This session has ended.") | N/A |

</frozen-after-approval>

## Code Map

- `frontend/src/components/RoomPage.svelte` -- Room page (single-line compact style); fetch `/api/room/:slug`, SSE `session-ended`, tabs via `{#if}`. Rewrite tab/markup/CSS; keep fetch, SSE and the "This room is not available." text (asserted by `tests/interaction-contracts.test.mjs` ~L543).
- `frontend/src/lib/Markdown.svelte` -- shared DOMPurify + marked renderer used by Room and Review/Preview. Add overflow-safe CSS only (`overflow-wrap:anywhere`, `img{max-width:100%}`, `pre` wrap, table scroll-free layout); keep sanitization untouched.
- `frontend/src/App.svelte:76` -- routes `/room/:slug` to `RoomPage`; global `:global(*){box-sizing:border-box}`, focus ring rule is scoped to `.app` so Room needs its own `:focus-visible`. Do not change.
- `frontend/package.json`, `frontend/vite.config.ts` -- add `test:dom` script and a `test` block (jsdom, `@testing-library/svelte` svelte plugin, `resolve.conditions: ['browser']`).
- `_bmad-output/planning-artifacts/ux-designs/*/DESIGN.md` L157-164, L265-267 and `mockups/mock-room-page.html` -- tab/header treatment (18px title, 12px wordmark, 2px active indicator, 20px side padding).
- `backend/routers/room.py:14-21` -- already 404s on missing Published Content; read-only reference.

## Tasks & Acceptance

**Execution:**
- [x] `frontend/package.json`, `frontend/vite.config.ts` -- add devDependencies and `test:dom` (`vitest run`) -- harness decided in retro item 7
- [x] `frontend/src/components/RoomPage.svelte` -- `role=tablist/tab/tabpanel`, `aria-selected`/`aria-controls`, both panels toggled by `hidden`/`display`, sticky tabs with `min-height:44px`, visible 2px focus ring, `aria-live` only on the ended/unavailable block, wordmark, 20px padding, `max-width:640px`
- [x] `frontend/src/lib/Markdown.svelte` -- overflow-safe styles for long words, `pre`, tables, images, headings
- [x] `frontend/tests/room-page.dom.test.ts` -- DOM tests for the matrix: tabs/ARIA, switching, unsafe Markdown stripped, unavailable on 404 and network error, no Host chrome, no `input`/storage use; mock `fetch` and `EventSource`
- [x] `frontend/tests/interaction-contracts.test.mjs` -- source contracts for 640px, 44px, sticky tabs, `overflow-wrap`, no `overflow-x` scroll

**Acceptance Criteria:**
- Given an active Room, when it renders at 375px, then the layout is a single centered column of at most 640px with the title and wordmark and no Host chrome
- Given long prose, lists, headings, code and tables, when shown at 375px, then they wrap or scale and the page needs no horizontal scroll
- Given Markdown with unsafe markup, when rendered, then scripts, event handlers and `javascript:` URLs are removed
- Given Published Content is missing, when the Room loads, then only the unavailable state shows

## Implementation Notes

## Spec Change Log

## Review Triage Log

| Finding | Verdict | Route | Evidence |
|---|---|---|---|
| Inactive tab unreachable by keyboard (roving tabindex, no key handler) | medium | patch | `RoomPage.svelte` tabs have `tabindex=-1` and no keydown; Tab skips it. |
| EventSource URL not `encodeURIComponent`-ed | low | patch | Fetch encodes, stream does not; one-word fix. |
| `prefers-reduced-motion` rule vacuous | low | patch | No transition declared anywhere; delete rule. |
| `table-layout:fixed` squeezes tables; Markdown CSS also hits Host Review/Preview; svg/video unbounded | medium | patch | `Markdown.svelte` is shared; use auto layout with `anywhere` wrapping, bound svg/video. |
| `test:dom` not run in CI | medium | patch | `ci.yml` runs check/contracts/build only; AGENTS.md edit part deferred. |
| Unmount cleanup, `cancelled` guard, ended-on-load stream untested | medium | patch | No test unmounts before asserting; teardown could be deleted undetected. |
| Dependency caret ranges vs exact pins | low | patch | Existing devDependencies are pinned exactly. |
| Ended notice in non-persistent live region | medium | defer | Ended announcement belongs to Story 3.5 AC; no persistent region exists yet. |
| `test:dom` missing from AGENTS.md verification list | low | defer | Fix edits an agent-context file. |
| Inactive tab / wordmark contrast `#6d6d6d` ~3.6:1 | medium | defer | Value is the DESIGN.md `foreground-muted` token; pre-existing design decision, not this story's. |
| SSE error/missed `session-ended` | false | n/a | Server replays `session-ended` on connect for ended sessions and EventSource auto-reconnects. |
| 200 with null body / non-string fields / invalid JSON | false | n/a | Backend returns a fixed shape or 404; unreachable via the real API. |
| `slug` prop change without remount | false | n/a | Router mounts one Room per navigation; guests do not switch rooms in place. |
| Fetch not aborted / state written after unmount | low | rejected | Harmless write to a destroyed Svelte component; fix adds AbortController complexity. |
| Both panels rendered while hidden | false | n/a | Spec requires display toggle; cost is negligible for two documents. |
| Empty-tab state when a field is missing | false | n/a | `room_payload` already returns 404 if either published field is empty. |
| Background outside 640px column | false | n/a | `App.svelte` sets global `body{background:#15141b}`. |
| `vite.config` VITEST-conditional resolve | false | n/a | Vitest sets `VITEST` automatically; build verified unaffected. |
| Unsafe-Markdown test vacuous | false | n/a | Test also asserts no `script`, `[onerror]` or `javascript:` links in the DOM. |
| h1 24px→18px, sticky tabs scroll title, missing blockquote/hr/link styles, thin 5xx tests | false | n/a | 18px/sticky behaviour match DESIGN.md and the mockup; remaining are non-defects for this story. |

## Verification

**Commands:**
- `npm --prefix frontend ci` -- expected: installs including new devDependencies
- `npm --prefix frontend run test:dom` -- expected: all DOM tests pass
- `npm --prefix frontend run test:contracts` -- expected: contracts pass
- `npm --prefix frontend run check` -- expected: no type errors
- `npm --prefix frontend run build` -- expected: build succeeds
- `python3 -m pytest` -- expected: backend tests still pass

**Manual checks:**
- Open `/room/<slug>` in browser devtools at 375px with long Markdown: no horizontal scrollbar; tabs reachable one-handed.
