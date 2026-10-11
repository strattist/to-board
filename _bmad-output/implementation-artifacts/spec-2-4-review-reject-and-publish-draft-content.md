---
title: 'Review, Reject, and Publish Draft Content'
type: 'feature'
created: '2026-09-26'
status: 'done'
review_loop_iteration: 0
baseline_commit: 'f2bb401f23f95d85bae2a6935735a2bf15474166'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The Host can open a basic Draft review screen, but it lacks reliable loading, action feedback, accessible state updates, and the required rejection confirmation. The reject service also accepts an incomplete Draft, contrary to the story’s all-or-nothing action contract.

**Approach:** Complete the Host review flow around the existing Content state machine and shared sanitized Markdown renderer. Validate both Draft documents before either action, keep publish and reject atomic, and make the responsive Review screen communicate loading, state changes, and errors inline.

## Boundaries & Constraints

**Always:** Keep one Content row per Game and keep `backend/services/content.py` as the only state-transition owner. Bind Publish and Reject to the exact `draft_revision` returned with the pair the Host reviewed; reject missing or changed revisions with 409 and no mutation. Publish only a complete pair, replace both Published fields together, clear both Draft fields, and set the pipeline to `published`. Reject only a complete Draft in `draft` state, clear only its Draft fields, and preserve any Published pair. Return 409 for invalid state, incomplete pairs, or stale revisions without mutation. Keep Host routes protected, render Markdown through the shared sanitizer, and serve Guests only Published Content. A published pipeline state continues to map to Ready to play. Any polling must be no more frequent than every five seconds.

**Ask First:** Any database schema or migration, new pipeline state, authentication change, new dependency, or change to generation/provider behavior.

**Never:** Add Markdown editing, auto-publish generated content, expose Drafts to Guest or runtime routes, discard prior Published Content on rejection, or make cloud calls during review, preview, or Room access.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|----------------------------|----------------|
| Publish | Complete Draft and `pipeline_state=draft` | Publish both fields as a pair, clear Draft, set state to `published` | A failed request leaves the pair unchanged and shows an inline error |
| Reject | Complete Draft and existing Published pair | Clear only Draft, set state to `rejected`, preserve Published pair, allow regeneration | A failed request leaves content unchanged and shows an inline error |
| Invalid action | Incomplete Draft or state other than `draft` | No fields or state change | API returns 409; UI keeps the Review screen usable |
| Cancel rejection | Confirmation is open | No request and no state change | Close the dialog and restore focus to its trigger |

</frozen-after-approval>

## Code Map

- `backend/models/content.py:6-25` — one Content row owns paired Draft and Published Markdown plus pipeline state and timestamps; no new schema is needed.
- `backend/services/content.py:21-27,101-116` — legal transitions and current `publish()` / `reject()` mutations. Publish validates the pair; reject currently validates state only and needs the same completeness guard.
- `backend/routers/games.py:260-276` — Host-protected Content GET and publish/reject routes already call the service and commit once; preserve their route and error contract.
- `backend/routers/games.py:68-80` and `frontend/src/components/StatusBadge.svelte:1` — Game payload reports readiness from Published fields; `published` displays as Ready to play.
- `frontend/src/App.svelte:64-67` and `frontend/src/components/Detail.svelte:270-272` — `/games/:id/review` is already routed and linked when a Draft exists.
- `frontend/src/components/Review.svelte:1-3` — current minimal review view fetches Content directly, renders both Drafts, and posts actions; add typed API use, explicit states, revision-bound actions, and the destructive dialog here.
- `frontend/src/lib/api.ts:1-4` — shared credentialed API/error helper; add a typed Content shape and GET/action helpers.
- `frontend/src/lib/Markdown.svelte:1-8` — shared `marked` plus DOMPurify renderer; use it for both read-only Draft documents.
- `frontend/src/components/Detail.svelte:202-229` — existing accessible destructive dialog pattern covers focus, keyboard handling, busy state, and focus restoration.
- `frontend/src/components/Preview.svelte:8-23` — typed loading/error and stale-request handling pattern; adapt for Review lifecycle and inline status.
- `tests/test_app.py:728-742` — current publish/reject test exercises rejection only; extend it for publish, complete-pair validation, invalid states, atomicity, and Published preservation.
- `frontend/tests/interaction-contracts.test.mjs:12` — existing interaction contract suite; add review route/API/dialog/status assertions without adding a test dependency.

## Tasks & Acceptance

**Execution:**
- [x] `backend/services/content.py` — require both nonempty Draft fields before rejection; keep validation before any mutation.
- [x] `tests/test_app.py` — cover both actions’ success, 409 cases, pair clearing/copying, state changes, and preservation of existing Published fields.
- [x] `frontend/src/lib/api.ts` — define the typed Content response and shared GET/publish/reject helpers.
- [x] `frontend/src/components/Review.svelte` — use typed helpers; show inline loading, errors, action busy state, and accessible live status; refresh at the allowed cadence while mounted; render sanitized read-only Drafts responsively; add the accessible rejection dialog and prevent duplicate submissions.
- [x] `frontend/tests/interaction-contracts.test.mjs` — cover route behavior, Cancel without a request, Publish without confirmation, rejection confirmation copy, and accessible status/error states.

**Acceptance Criteria:**
- Given a Game has a complete Draft pair, when the Host opens Review, then both documents render read-only through the shared sanitizer, side by side on desktop and stacked on narrow screens.
- Given the Review payload or pipeline state changes asynchronously, when the change is received, then the page reports the current state with accessible live semantics and keeps loading and errors inline. If a complete Draft revision changes, actions remain disabled until the Host reviews the updated pair.
- Given the Host confirms Publish, when the server accepts the action, then both Draft fields become the Published pair atomically, Draft fields clear, the state becomes `published`, and Game Detail shows Ready to play.
- Given the Host chooses Reject, when the confirmation appears, then it explains that rejection clears the Draft and permits regeneration; Cancel preserves the Draft and state, while confirmation clears only the Draft, preserves prior Published Content, and leaves Game Detail able to start a new generation.
- Given a Draft is incomplete, the pipeline is not `draft`, or the submitted revision is missing or stale, when Publish or Reject is requested, then the server returns 409 and no partial mutation occurs.

## Design Notes

Keep the last valid documents visible only while the server reports a complete Draft; otherwise show an inline unavailable state.

## Verification

The checks below passed before the follow-up review fixes. Rerun them before promoting this story from review.

**Commands:**
- `rtk uv run --no-cache pytest -q tests/test_app.py` — backend publish/reject behavior and regression coverage pass.
- `rtk npm --prefix frontend run check` — Svelte and TypeScript checks pass.
- `rtk npm --prefix frontend run test:contracts` — review interaction contracts pass.
- `rtk npm --prefix frontend run build` — production frontend bundle succeeds.

## Suggested Review Order

**Review lifecycle and action protection**

- Draft gating, refresh, and one live status keep Review aligned with the latest Host Content.
  [`Review.svelte:38`](../../frontend/src/components/Review.svelte#L38)

- Versioned requests prevent stale results or navigation after a Game changes.
  [`Review.svelte:73`](../../frontend/src/components/Review.svelte#L73)

- The rejection dialog keeps focus inside while requests are busy.
  [`Review.svelte:187`](../../frontend/src/components/Review.svelte#L187)

**State transitions and API**

- Shared non-whitespace pair validation runs before either publish or reject mutation.
  [`content.py:101`](../../backend/services/content.py#L101)

- Typed helpers centralize the credentialed content read and action requests.
  [`api.ts:37`](../../frontend/src/lib/api.ts#L37)

**Coverage**

- Parameterized 409 cases verify incomplete pairs and invalid states leave content unchanged.
  [`test_app.py:814`](../../tests/test_app.py#L814)

- The rejection path preserves Published content and permits regeneration.
  [`test_app.py:752`](../../tests/test_app.py#L752)

- Interaction contracts protect Cancel, confirmation wiring, accessible status, and inline errors.
  [`interaction-contracts.test.mjs:38`](../../frontend/tests/interaction-contracts.test.mjs#L38)
