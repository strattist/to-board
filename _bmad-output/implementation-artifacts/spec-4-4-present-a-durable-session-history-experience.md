---
title: 'Present a Durable Session History Experience'
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

**Problem:** Story 4.4 asks that Session Log and Session Detail stay usable on desktop, tablet and mobile Host viewports without unintended horizontal scroll; that focus order follows the DOM with the primary-color focus ring and accessible names; that loading uses inline or skeleton indicators, never a blocking overlay; that update feedback is calm, specific and not misleading; and that active and ended state is text, not color alone. Session Detail has no loading indicator, formats its date without a guard (`Invalid Date`), says only `Saved.`, shows saved players and outcomes only inside editable fields, and lets long unbroken names overflow.

**Approach:** Frontend-only polish of `SessionPages.svelte` and `SessionDetail.svelte`: an inline loading state and shared date guard in Detail, a read-only saved summary (players, ordered outcomes) above the form, specific save and failure microcopy, text state badges, wrapping rules for long text, and DOM tests for each criterion. No API or schema change.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Detail loading | request pending | inline `role=status` "Loading session…" in the page, no overlay; replaced by content | load failure shows `role=alert` |
| Saved summary | players and outcomes stored | read-only players list and ordered outcomes list (repeats kept) reflect the last saved values | empty lists show "No players recorded" / "No outcomes recorded" |
| Save success | PATCH ok | `role=status` "Players and outcomes saved." and summary updates | N/A |
| Save failure | PATCH non-2xx / network | `role=alert` with server `detail` or "Players and outcomes could not be saved. Your changes are still in the form." | summary unchanged |
| Bad date | unparsable `started_at` | `Unknown date`, never `Invalid Date` | N/A |
| Long text | 100-char unbroken name or title | wraps inside the viewport at 375px, no horizontal scroll | N/A |
| State | active or ended | text "Active" / "Ended" in a bordered badge, never color alone | N/A |

</frozen-after-approval>

## Implementation Notes

- Investigation: shared Host nav, responsive padding and the global `#a277ff` focus ring already come from `App.svelte` (`.app a/select/textarea:focus-visible`); Session Detail's own buttons carry the same ring. `SessionPages.svelte` already has inline loading, text state and `role=alert` errors (Story 4.3). Gaps are those listed in the Problem.
- Out of scope: pagination, edit-conflict handling, any API change.
- Changed: `frontend/src/lib/session-format.ts` (shared date guard), `frontend/src/components/SessionPages.svelte` (skeleton rows while loading, text state badge, 44px filter controls, long-text wrapping), `frontend/src/components/SessionDetail.svelte` (inline loading status, read-only saved players and ordered outcomes, specific save/failure copy, text state badge, date guard, wrapping, `muted` contrast), tests (+4 Detail, +2 Log; one assertion updated for the new save copy). No API or schema change. Frontend check, contracts, DOM (42) and build pass; backend untouched.
- Review ran inline (no subagents authorized). Not committed (user instruction). Branch `feat/4-4-present-a-durable-session-history-experience`; sprint-status 4-4 set to `review`.
- Not verified: visual layout at 375px/768px in a real browser; jsdom cannot assert horizontal overflow. The wrapping and `min-width:0` rules are the mitigation.

## Review Triage Log

- low (rejected): the Detail form is not keyboard-trapped or reordered; DOM order already matches visual order, and the global `.app` focus ring covers links, textareas and buttons.
- low (rejected): no pagination or optimistic update; out of scope for presentation.
