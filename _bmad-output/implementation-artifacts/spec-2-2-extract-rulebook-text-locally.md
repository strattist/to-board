---
title: 'Extract Rulebook Text Locally'
type: 'feature'
created: '2026-09-22'
status: 'done'
review_loop_iteration: 0
baseline_commit: 'e1b32137cf0fd2869f291d7fbe3fd18d5cb49ff2'
context:
  - '/home/baptiste/work/to-board/_bmad-output/implementation-artifacts/epic-2-context.md'
  - '/home/baptiste/work/to-board/_bmad-output/implementation-artifacts/spec-2-1-configure-and-protect-the-llm-provider.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Rulebook uploads already launch local extraction, but the worker discards the extracted token count, does not surface low-quality extraction, and has no server-enforced way for the Host to acknowledge that warning. The Host therefore cannot distinguish a usable cache from a likely image-only or malformed extraction before requesting cloud generation.

**Approach:** Harden the existing pdfplumber/atomic-cache worker, evaluate the configured minimum token threshold, and expose a non-secret warning while keeping the pipeline ready for an explicit Host override. Keep extraction local and asynchronous, persist only the absolute text-cache path, and preserve the existing stale-rulebook, replacement, and recovery semantics.

## Boundaries & Constraints

**Always:** Use the uploaded PDF from the persistent uploads dataset; write the `.txt` cache atomically before `ready_to_generate`; run blocking PDF work through the existing executor/thread-pool boundary; compare `len(text.split())` with `Settings.extraction_min_tokens`; keep warning/error state server-owned; require a server-validated `allow_low_quality` acknowledgement before generation when below threshold; never expose filesystem paths or PDF bytes to the frontend/provider; retain Published Content and recorded predecessor state.

**Ask First:** Changing the 500-token default, introducing a new database table or persistence location, or changing the Content state machine beyond extraction and generation prerequisite validation.

**Never:** Send raw PDFs to a provider, mark extraction ready without a durable cache path, trust a frontend-only override, treat a stale worker as current, add a local LLM, or add a separate worker service.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|-----------------------------|----------------|
| Clean extraction | Current Rulebook PDF, token count at/above threshold | Atomic text file, absolute `extracted_text_path`, `ready_to_generate`, no warning | No partial output on failure |
| Low-quality extraction | Current PDF, token count below threshold | Cache and absolute path still persist; pipeline is ready with a clear warning exposed to Host | Generation is rejected until `allow_low_quality` is explicitly true |
| Extraction failure | Malformed/read error or incomplete write | Remove partial cache, clear extracted path, transition to `no_rulebook`, surface safe failure | Existing Published fields remain unchanged |
| Replacement/stale job | Old worker finishes after Rulebook replacement | Ignore result and remove stale output; only replacement can become ready | No state or path mutation for stale row |
</frozen-after-approval>

## Code Map

- `backend/services/extraction.py:13-37` -- pdfplumber extraction, atomic `.part` writer, token count, and executor wrapper; preserve durable-write behavior.
- `backend/workers/extraction.py:17-48` -- current-ID checks, cache-path persistence, Content transition, failure cleanup; add threshold/warning handling and executor use.
- `backend/services/content.py:25-57` -- sole extraction transition owner; preserve `prior_pipeline_state` and warning/error semantics.
- `backend/routers/games.py:31-55,108-120,207-218` -- Game payload, upload scheduling, and generation prerequisite; expose warning metadata without paths and validate the override server-side.
- `backend/core/config.py:5-18` -- existing `extraction_min_tokens` setting; do not introduce a second threshold source.
- `backend/db/init.py:5-13` -- startup recovery for interrupted extraction; retain recorded predecessor behavior and clean only safe orphan artifacts.
- `frontend/src/App.svelte:17-51` -- five-second pipeline polling; refresh Collection cards as well as selected Game Detail while extraction runs.
- `frontend/src/lib/api.ts:6-38`, `frontend/src/components/Detail.svelte:37-230`, `frontend/src/components/StatusBadge.svelte:1-3` -- typed warning/override contract, accessible warning copy, and generation gating.
- `tests/test_app.py:1070-1284`, `frontend/tests/interaction-contracts.test.mjs:16-31,95-100,208-214` -- extend extraction, threshold, stale/recovery, override, polling, and non-disclosure coverage.

## Tasks & Acceptance

**Execution:**
- [x] `backend/services/extraction.py`, `backend/workers/extraction.py` -- keep blocking extraction in FastAPI's background thread pool, retain atomic output, evaluate token quality, persist warning/path only for the current Rulebook, and clean failures/stale output.
- [x] `backend/services/content.py`, `backend/routers/games.py`, `backend/db/init.py` -- preserve server-owned transitions/recovery, expose a safe warning field, and enforce `allow_low_quality` for below-threshold generation.
- [x] `frontend/src/lib/api.ts`, `frontend/src/components/Detail.svelte`, `frontend/src/App.svelte`, `frontend/src/components/StatusBadge.svelte` -- show calm accessible warning/status, require explicit acknowledgement, and poll extraction state within five seconds.
- [x] `tests/test_app.py`, `frontend/tests/interaction-contracts.test.mjs` -- cover clean/low-quality/failure/stale/restart paths, override enforcement, atomicity, and absence of PDF/path leakage.

**Acceptance Criteria:**
- Given a valid uploaded Rulebook, when extraction completes, then a durable absolute text path is stored before the pipeline reaches `ready_to_generate`, and no raw PDF bytes leave local storage.
- Given extracted text below the configured threshold, when the Host views the Game, then a clear warning is shown and generation cannot start until the Host explicitly acknowledges the warning; the server rejects a missing acknowledgement.
- Given extraction fails or the process restarts mid-job, when recovery runs, then no incomplete path is treated as ready and the Content returns to its recorded predecessor with a safe message.
- Given a Rulebook is replaced or a stale worker completes, when results are committed, then old caches cannot overwrite the replacement and existing Published Content remains unchanged.

## Spec Change Log

## Design Notes

Keep the warning in the existing Content error/status channel for persistence, but expose it separately from fatal errors in the Game payload so the UI can render warning semantics. Compute/validate quality from the persisted text path on the server; do not trust a client-supplied token count or boolean alone. Re-upload remains the retry path after a failed extraction.

## Verification

**Commands:**
- `python3 -m pytest` -- expected: all backend tests pass, including extraction quality, recovery, stale-worker, and override cases.
- `npm --prefix frontend run check` -- expected: Svelte/TypeScript checks pass.
- `npm --prefix frontend run test:contracts` -- expected: frontend warning, polling, and API contracts pass.
- `npm --prefix frontend run build` -- expected: production bundle succeeds with no PDF/path leakage.

## Suggested Review Order

1. Start with the server contract and generation gate: [`backend/routers/games.py`](../../backend/routers/games.py#L49) and [`backend/routers/games.py`](../../backend/routers/games.py#L224).
2. Follow the extraction lifecycle and restart recovery: [`backend/workers/extraction.py`](../../backend/workers/extraction.py#L20) and [`backend/db/init.py`](../../backend/db/init.py#L8).
3. Review the Host-facing warning and acknowledgement flow: [`frontend/src/components/Detail.svelte`](../../frontend/src/components/Detail.svelte#L39), [`frontend/src/components/GameCard.svelte`](../../frontend/src/components/GameCard.svelte#L77), and [`frontend/src/components/StatusBadge.svelte`](../../frontend/src/components/StatusBadge.svelte#L1).
4. Confirm collection polling and request-body contracts: [`frontend/src/App.svelte`](../../frontend/src/App.svelte#L45), [`frontend/src/lib/api.ts`](../../frontend/src/lib/api.ts), and [`frontend/tests/interaction-contracts.test.mjs`](../../frontend/tests/interaction-contracts.test.mjs#L119).
5. Run the backend acceptance coverage, especially the quality override and recovery cases: [`tests/test_app.py`](../../tests/test_app.py#L1088).

### Review Findings

- [x] [Review][Patch] Generation prerequisite ordering returns the wrong missing-key error — the new cache-file check runs before the established API-key check, so a missing cache and missing key return “Rulebook extraction is not complete” and fail the existing contract test [backend/routers/games.py:227-233]
- [x] [Review][Patch] Extraction cache paths are read without uploads-root containment validation — canonicalize persisted paths and reject paths or symlinks that escape the configured uploads dataset before payload, generation, or provider reads [backend/routers/games.py:51-58,227-233; backend/workers/generation.py:29-41]
- [x] [Review][Patch] Extraction cleanup failures have no durable retry — unlink errors are swallowed while the row is reset, so later startup recovery no longer revisits the orphaned artifact [backend/db/init.py:31-45; backend/workers/extraction.py:51-60]
- [x] [Review][Patch] Startup recovery skips orphan files when the Rulebook row is missing — reconcile the game upload directory even when an extracting Content row has no Rulebook record [backend/db/init.py:13-16]
- [x] [Review][Patch] Unreadable extraction caches are reported as ready — distinguish a readable UTF-8 cache from a mere regular file and expose a recoverable extraction failure [backend/routers/games.py:51-65]
- [x] [Review][Patch] Game payload construction recounts entire extraction caches on every response — persist or reuse extraction quality metadata instead of rereading large caches during five-second polling [backend/routers/games.py:51-58]
- [x] [Review][Patch] Detail warning enforcement has only source-level verification — add a runtime component test proving the Generate button stays disabled until acknowledgment and sends the override only afterward [frontend/src/components/Detail.svelte:105-114,243; frontend/tests/interaction-contracts.test.mjs:10-31]
- [x] [Review][Patch] Collection polling has only source-level verification — add a behavior test for refreshing a busy non-selected game and cleaning up the interval [frontend/src/App.svelte:45-50; frontend/tests/interaction-contracts.test.mjs:35-44]
- [x] [Review][Patch] Startup recovery failure paths lack executable coverage — test unlink failure, missing Rulebook rows, unsafe paths, and leftover partial files [backend/db/init.py:31-45; tests/test_app.py:1146-1177]
- [x] [Review][Patch] Low-quality rejection does not prove that no cloud task starts — assert the generation worker/provider is not invoked when the server rejects a missing acknowledgment [tests/test_app.py:1088-1119]
- [x] [Review][Patch] Blocking extraction warnings use conflicting live-region semantics — use assertive alert behavior or a consistent status role [frontend/src/components/Detail.svelte:232-236]
- [x] [Review][Patch] Collection warning badges lack explicit card positioning — style the new warning badge so it cannot enter normal flow or overlap card content [frontend/src/components/GameCard.svelte:77-81; frontend/src/components/StatusBadge.svelte:1-3]

- [x] [Review][Defer] Rulebook metadata still exposes the absolute PDF path [backend/routers/games.py:198-208] — deferred, pre-existing
- [x] [Review][Defer] PDF delivery still trusts persisted paths without uploads-root containment [backend/routers/games.py:210-221] — deferred, pre-existing
- [x] [Review][Defer] Stale-worker cleanup removes only the final cache and not matching partial files [backend/workers/extraction.py:22-27] — deferred, pre-existing
- [x] [Review][Defer] The extraction threshold accepts negative configuration values [backend/core/config.py:16] — deferred, pre-existing
