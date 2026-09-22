## Deferred from: code review of story-1-1-create-and-browse-game-entries (2026-09-16)

- Detail's session, generation, and delete actions ignore non-2xx responses. This predates the Story 1.1 cover/collection implementation and should be addressed in the broader Detail workflow.
- AGENTS.md still contains TODO verification instructions. Updating agent-context guidance belongs to the project-context workflow, not this implementation review.

## Deferred from: code review rerun of story-1-1-create-and-browse-game-entries (2026-09-16)

- Detail's session, generation, and delete actions still ignore non-2xx responses; this predates the Story 1.1 cover/collection changes.
- Cover replacement locking is process-local; supporting multiple workers requires an architecture decision about distributed locking.
- Synchronous cover filesystem/database work runs inside an async endpoint; converting this route needs a broader async I/O decision.

## Deferred from: spec-1-2-upload-and-replace-a-game-rulebook (2026-09-19)

- source_spec: `spec-1-2-upload-and-replace-a-game-rulebook.md`
  summary: Add the configured low-extraction-token warning and Host override flow.
  evidence: `Settings.extraction_min_tokens` exists but the broader FR-6 warning/override behavior is outside Story 1.2's upload-and-replace acceptance criteria.
- source_spec: `spec-1-2-upload-and-replace-a-game-rulebook.md`
  summary: Serialize concurrent Rulebook replacements and close the remaining stale-worker commit race.
  evidence: The current in-process identity checks predate this story; stronger cross-request locking/conditional commits require an architecture decision for the supported worker topology.
- source_spec: `spec-1-2-upload-and-replace-a-game-rulebook.md`
  summary: Complete end-to-end Authentik browser redirect/token propagation for Host API calls.
  evidence: Frontend/API auth wiring is a pre-existing Story 5.1 hardening concern; this story preserves the Host-only dependency and sends credentials without changing the auth model.

## Deferred from: code review of spec-1-2-upload-and-replace-a-game-rulebook (2026-09-19)

- source_spec: `spec-1-2-upload-and-replace-a-game-rulebook.md`
  summary: Close the stale extraction worker check/commit race.
  evidence: The worker rechecks identity before mutation, but a replacement can commit between that check and the worker commit; fixing this requires an architecture-level conditional commit or locking decision.
- source_spec: `spec-1-2-upload-and-replace-a-game-rulebook.md`
  summary: Serialize concurrent Rulebook replacements.
  evidence: Concurrent uploads can race on the unique Rulebook row; supported worker topology and lock scope require an architecture decision.
- source_spec: `spec-1-2-upload-and-replace-a-game-rulebook.md`
  summary: Add the configured low-extraction-token warning and Host override flow.
  evidence: `Settings.extraction_min_tokens` is not consumed by this story; the broader FR-6 behavior is outside the frozen upload-and-replace acceptance criteria.
- source_spec: `spec-1-2-upload-and-replace-a-game-rulebook.md`
  summary: Move synchronous PDF validation and staging off the async upload route.
  evidence: The route still performs bounded read, pdfplumber validation, and local staging synchronously; changing the I/O model requires a broader async decision and is not part of this story.
- source_spec: `spec-1-2-upload-and-replace-a-game-rulebook.md`
  summary: Recover the extraction worker session after database failures.
  evidence: The worker's exception path does not explicitly rollback before attempting failure-state queries/commit; this pre-existing worker recovery policy is broader than the upload slice.

## Deferred from: code review rerun of spec-1-2-upload-and-replace-a-game-rulebook (2026-09-19)

- source_spec: `spec-1-2-upload-and-replace-a-game-rulebook.md`
  summary: Close the stale-worker check/commit race and serialize concurrent Rulebook replacements.
  evidence: Identity checks and cleanup-journal updates are not guarded by a cross-request lock or conditional commit; supported worker topology and lock scope require an architecture decision.
- source_spec: `spec-1-2-upload-and-replace-a-game-rulebook.md`
  summary: Complete Authentik bearer-token propagation for browser API calls.
  evidence: Browser API helpers send credentials but do not acquire or attach the Bearer token expected by `require_host`; this is pre-existing Story 5.1 authentication work outside the upload slice.
- source_spec: `spec-1-2-upload-and-replace-a-game-rulebook.md`
  summary: Make extraction cleanup and database-session recovery durable across persistent failures.
  evidence: Extraction temporary/output cleanup and worker exception recovery remain best-effort; a broader recovery policy is outside this story's replacement transaction.

## Deferred from: spec-1-5-implement-the-host-collection-and-game-detail-experience (2026-09-21)

- source_spec: `spec-1-5-implement-the-host-collection-and-game-detail-experience.md`
  summary: Disable Start session when the Game already has an active Session.
  evidence: The current Game DTO does not expose active-session state; adding that signal or a new query requires a backend/API contract decision outside this frontend story.
- source_spec: `spec-1-5-implement-the-host-collection-and-game-detail-experience.md`
  summary: Add an explicit warning before regeneration clears an existing Draft Content.
  evidence: Draft replacement semantics belong to the Content-generation workflow; the approved Story 1.5 intent only requires state-aware availability and calm errors.
- source_spec: `spec-1-5-implement-the-host-collection-and-game-detail-experience.md`
  summary: Add rendered component tests for Svelte navigation, Collection/Card states, Detail actions, and Preview branches.
  evidence: Current dependency-free contracts verify source seams and API requests; a DOM test harness would require a separate test-stack decision and dependency scope.

## Deferred from: code review of spec-1-5-implement-the-host-collection-and-game-detail-experience (2026-09-21)

- source_spec: `spec-1-5-implement-the-host-collection-and-game-detail-experience.md`
  summary: Create flow can report a persisted game as failed when the follow-up refresh fails.
  evidence: `frontend/src/lib/create-flow.js:6-9` performs creation and refresh sequentially; this behavior predates the reviewed change.
- source_spec: `spec-1-5-implement-the-host-collection-and-game-detail-experience.md`
  summary: localStorage access is not guarded in restricted browsers.
  evidence: `frontend/src/App.svelte:40-51` reads and writes localStorage without a guard; this behavior predates the reviewed change.

## Deferred from: code review of spec-2-1-configure-and-protect-the-llm-provider.md (2026-09-22)

- source_spec: `spec-2-1-configure-and-protect-the-llm-provider.md`
  summary: Reject whitespace-only extracted text before cloud generation.
  evidence: `backend/services/extraction.py` has marked empty extraction output ready since before this story; tightening that prerequisite belongs to the extraction story.
- source_spec: `spec-2-1-configure-and-protect-the-llm-provider.md`
  summary: Serialize first-time AppSettings initialization under concurrent requests.
  evidence: The GET/PUT singleton insert race predates this story and requires a broader database-startup or conflict-handling decision.
- source_spec: `spec-2-1-configure-and-protect-the-llm-provider.md`
  summary: Add a maximum API-key length bound before encryption.
  evidence: The Settings API already accepted unbounded keys before this story; selecting provider-specific limits is broader hardening work.

## Deferred story: 2.7 — Make Rulebook extraction optional to start a Session

- story_id: `2-7`
  summary: Allow the Host to start a Session when Published Content is already available, even if the current Rulebook extraction is absent or still in progress.
  rationale: Rulebook extraction is required for new Content generation, but it should not block a game night that can already use the previously published Quick-start Guide and Cheat Sheet.
  scope: Reconcile the server-side Session readiness check, Game Detail action state, and related tests while preserving extraction as a prerequisite for generation and keeping Guest Rooms backed only by Published Content.
