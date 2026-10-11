---
title: 'Upload and replace a Game Rulebook'
type: 'feature'
created: '2026-09-19'
status: 'done'
review_loop_iteration: 2
baseline_commit: '9140d98db26fe5f47cbd0df434bce34ea93754b3'
context:
  - '{project-root}/AGENTS.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-to-board-2026-09-07/ARCHITECTURE-SPINE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Rulebook upload exists as a thin route, but malformed PDFs can be persisted, filesystem failures can leave orphaned or partial files, and the Host has little feedback while replacement extraction runs. This risks losing the authoritative Rulebook contract and leaves later Content generation dependent on unreliable state.

**Approach:** Harden the existing Game Detail upload path as one vertical slice: validate and atomically stage PDFs, replace the single Rulebook while preserving Published Content and invalidating only replaceable draft state, run extraction safely in the background, and expose clear Host upload/extraction feedback without changing the established API or PDF.js viewer boundary.

## Boundaries & Constraints

**Always:** Keep every Rulebook route behind `require_host`; accept local PDF files only, enforce the configured 100 MB limit, reject malformed input with FastAPI `422` before persistence, and write PDFs/text caches only below the configured uploads dataset. Maintain one Rulebook row per Game, persist an absolute extracted-text path before `ready_to_generate`, preserve Published Markdown on replacement, clear Draft/Rejected working text, and retain stale-worker identity checks. Use the existing SQLModel, service, worker, and PDF.js seams.

**Ask First:** Any change to Rulebook cardinality, the Content state machine or Published-content retention, the upload limit, authentication boundary, dataset layout, or introducing a new PDF/database dependency.

**Never:** Do not expose Rulebooks to Guest routes, accept web URLs, use the browser's native PDF plugin, transmit PDF bytes to a cloud service, add a second database or persistent Docker volume, or broaden this story into PDF annotations, content generation, or auth-model redesign.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|----------------------------|----------------|
| HAPPY_PATH | Authenticated Host uploads a valid local PDF to a Game without a Rulebook | `200` returns the Game with one Rulebook and `extracting`; the PDF is durably stored and extraction is scheduled | N/A |
| HAPPY_PATH | Authenticated Host uploads a valid replacement while Published and Draft/Rejected Content exist | New Rulebook is current; old PDF/text files are removed; Published fields remain; draft fields are cleared; extraction restarts | N/A |
| ERROR_CASE | Missing/non-PDF, malformed/truncated PDF, or file over 100 MB | No new Rulebook row or file is persisted; existing Rulebook and Content remain unchanged | Return `422` with a human-readable `detail` |
| ERROR_CASE | PDF write, replacement, or database failure | No partial new file is left; prior database/file state is restored or retained | Return an error and keep the prior Rulebook usable |
| EDGE_CASE | Extraction finishes after the Rulebook has been replaced | Stale output is removed and the current Rulebook/Content is not mutated | Worker exits without changing current state |

</frozen-after-approval>

## Code Map

- `backend/models/game.py:15-21` -- `Rulebook` SQLModel; preserve the unique `game_id`, path fields, and upload timestamp.
- `backend/routers/games.py:104-132, 194-204` -- Host-only upload, payload, and PDF serving seams; move validation/staging through the existing service boundary without changing route shape.
- `backend/services/content.py:34-44` -- replacement reset and `no_rulebook → extracting` transitions; preserve Published columns and server-owned state changes.
- `backend/services/extraction.py:5-22` -- local pdfplumber extraction; make output publication/cleanup safe and return the existing extraction result.
- `backend/workers/extraction.py:9-40` -- background identity/state checks; retain stale-worker guards and persist an absolute text path before readiness.
- `backend/core/config.py:5-21` -- uploads dataset and configured upload limit; do not hardcode runtime paths.
- `frontend/src/components/Detail.svelte:9-29, 75-80` -- native local PDF input, replacement UI, errors, refresh, and PDF.js link; add explicit busy/confirmation/state feedback without changing the viewer.
- `frontend/src/App.svelte:16-31` and `frontend/src/lib/api.ts:1-20` -- Game refresh/routing and typed API seams used by Detail and polling.
- `tests/test_app.py:258-338` -- existing upload/replacement and stale-worker coverage; extend with validation, rollback, file cleanup, content preservation, absolute paths, and auth assertions.
- `frontend/tests/interaction-contracts.test.mjs:1-45` -- dependency-free frontend contracts; add Rulebook multipart, replacement confirmation, reset, and state-refresh coverage.

## Tasks & Acceptance

**Execution:**
- [x] `backend/routers/games.py` and a focused Rulebook service seam -- validate PDF structure/size, stage writes atomically, replace the unique row transactionally, clean old files safely, and preserve the existing response/auth contract.
- [x] `backend/services/extraction.py` and `backend/workers/extraction.py` -- publish extraction output atomically at an absolute path, remove partial/stale outputs, and keep current-rulebook/state guards authoritative.
- [x] `frontend/src/components/Detail.svelte`, `frontend/src/App.svelte`, and `frontend/src/lib/api.ts` -- confirm replacement, show upload/extraction progress and errors, reset controls, and refresh/poll pipeline state at no more than five seconds.
- [x] `tests/test_app.py` and `frontend/tests/interaction-contracts.test.mjs` -- cover valid/replacement flows, malformed/oversized/auth failures, rollback and cleanup, Content semantics, stale workers, multipart fields, and Host feedback.

**Acceptance Criteria:**
- Given an authenticated Host selects a valid local PDF under the configured limit, when upload is submitted, then the API stores exactly one Rulebook under the uploads dataset, returns `extracting`, and schedules non-blocking local extraction.
- Given a replacement upload succeeds, when extraction eventually completes, then the new Rulebook owns an absolute extracted-text path and reaches `ready_to_generate`; the prior PDF/text files are gone and stale work cannot mutate it.
- Given Published Content exists before replacement, when the new Rulebook is installed, then Published Markdown remains available while Draft/Rejected working fields are invalidated according to the state machine.
- Given invalid, malformed, oversized, unauthenticated, or failed uploads, when the request is made, then the Host boundary and `422`/failure behavior prevent partial persistence and leave any prior Rulebook usable.
- Given the Host is on Game Detail during upload/extraction, when a replacement is selected or state changes, then the UI confirms destructive replacement, exposes accessible busy/error/status feedback, and never uses a native PDF plugin or URL upload.

## Design Notes

The database transaction cannot roll back an already committed filesystem rename, so the implementation should stage the new PDF and defer destructive cleanup until the new row is committed; every failure path must remove only temporary artifacts and leave the prior row/file pair readable. Extraction follows the same rule: write a temporary sibling text file, rename it only after success, and record that absolute final path before transitioning Content.

## Verification

**Commands:**
- `python3 -m pytest tests/test_app.py` -- expected: backend lifecycle, validation, replacement, rollback, auth, and stale-worker tests pass.
- `npm --prefix frontend run check` -- expected: Svelte and TypeScript checks pass.
- `npm --prefix frontend run test:contracts` -- expected: frontend Rulebook upload/replacement contracts pass.
- `npm --prefix frontend run build` -- expected: production Svelte build succeeds.

## Suggested Review Order

**Validation and replacement transaction**

- Validate real PDF structure before any dataset write.
  [`rulebooks.py:27`](../../backend/services/rulebooks.py#L27)

- Stage the new file and replace the unique row with rollback protection.
  [`rulebooks.py:78`](../../backend/services/rulebooks.py#L78)

- Confirm the route keeps the Host boundary and schedules extraction.
  [`games.py:104`](../../backend/routers/games.py#L104)

**Extraction and pipeline state**

- Publish text atomically and preserve the absolute cache path contract.
  [`extraction.py:13`](../../backend/services/extraction.py#L13)

- Check stale identity and cleanup before transitioning Content readiness.
  [`extraction.py:17`](../../backend/workers/extraction.py#L17)

**Host experience**

- Review replacement confirmation, busy feedback, and accessible extraction status.
  [`Detail.svelte:20`](../../frontend/src/components/Detail.svelte#L20)

- Verify five-second polling and out-of-order refresh protection.
  [`App.svelte:18`](../../frontend/src/App.svelte#L18)

**Verification**

- Start with lifecycle, rollback, validation, content, and stale-worker coverage.
  [`test_app.py:265`](../../tests/test_app.py#L265)

- Finish with multipart, confirmation, and pipeline helper contracts.
  [`interaction-contracts.test.mjs:42`](../../frontend/tests/interaction-contracts.test.mjs#L42)

### Review Findings

- [x] [Review][Patch] Retry and persist failed Rulebook cleanup paths [backend/services/rulebooks.py:20-91]
- [x] [Review][Patch] Fsync staged Rulebook bytes before rename [backend/services/rulebooks.py:102-106]
- [x] [Review][Defer] Close the stale extraction worker check/commit race [backend/workers/extraction.py:30-41] — deferred, pre-existing; requires an architecture-level conditional commit/locking decision already recorded in deferred work.
- [x] [Review][Defer] Serialize concurrent Rulebook replacements [backend/services/rulebooks.py:96-115] — deferred, pre-existing; requires a supported worker-topology locking decision already recorded in deferred work.
- [x] [Review][Defer] Add the configured low-extraction-token warning/override flow [backend/workers/extraction.py:28-41] — deferred, pre-existing; broader FR-6 behavior is outside this story's frozen acceptance criteria.
- [x] [Review][Defer] Move synchronous PDF validation/staging off the async upload route [backend/routers/games.py:104-116] — deferred, pre-existing; requires a broader async I/O decision and is not part of this story's contract.
- [x] [Review][Defer] Recover the extraction worker session after database failures [backend/workers/extraction.py:42-48] — deferred, pre-existing; the worker's database-failure recovery policy is broader than this upload slice.

### Review Findings — rerun

- [x] [Review][Patch] Do not report a committed upload as failed when refresh errors [frontend/src/components/Detail.svelte:31-40]
- [x] [Review][Patch] Announce extraction failures with accessible alert semantics [frontend/src/components/Detail.svelte:81-86]
- [x] [Review][Patch] Replay the persisted cleanup journal at application startup [backend/main.py:8-13]
- [x] [Review][Patch] Add direct atomic-publication coverage for extracted-text writes [tests/test_app.py:346-361]
- [x] [Review][Patch] Verify cleanup-journal replay clears a previously persistent failure [tests/test_app.py:415-438]
- [x] [Review][Defer] Close the stale-worker check/commit race and serialize concurrent replacements [backend/workers/extraction.py:30-41; backend/services/rulebooks.py:105-183] — deferred, pre-existing; requires the architecture-level locking/conditional-commit decision already recorded in deferred work.
- [x] [Review][Defer] Complete Authentik bearer-token propagation for browser API calls [frontend/src/lib/api.ts:1-3] — deferred, pre-existing; this is Story 5.1 authentication work outside the frozen upload slice.
- [x] [Review][Defer] Make extraction cleanup/session recovery durable across persistent filesystem or database failures [backend/services/extraction.py:22-32; backend/workers/extraction.py:8-48] — deferred, pre-existing; the broader cleanup/recovery policy is outside this story's replacement transaction.
