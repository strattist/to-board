---
title: 'View a Rulebook Independently'
type: 'feature'
created: '2026-09-19'
status: 'done'
review_loop_iteration: 0
baseline_commit: '63e36170ca4aca62fdae4b6f1a718cabbf49ef27'
context:
  - '{project-root}/AGENTS.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-to-board-2026-09-07/ARCHITECTURE-SPINE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The Host can reach a Rulebook route and a basic PDF.js canvas, but the viewer is incomplete for real reading: it has no outline navigation, Wake Lock/read-mode behavior, robust loading/error feedback, or reduced Host navigation. Missing persisted files can also surface as a server error instead of a clear resource failure.

**Approach:** Complete the existing `/games/:id/pdf` vertical slice across the protected PDF endpoint, App route, and PDF.js viewer. Preserve the current route and dependency boundary while adding outline/page/zoom controls, responsive reduced navigation, optional Wake Lock with a calm unsupported notice, safe missing-file responses, and focused regression contracts.

## Boundaries & Constraints

**Always:** Keep Rulebook metadata and PDF bytes behind `require_host`; serve only the persisted active Rulebook through `application/pdf`; keep Guest Room routes unable to access PDFs; use the bundled `pdfjs-dist` worker and canvas rather than the browser PDF plugin; do not create a Session; keep controls keyboard-accessible, touch-sized, responsive, and calm in copy; return clear `404` errors for missing Games, Rulebooks, or files.

**Ask First:** Any change to Authentik/OIDC behavior, Rulebook storage/cardinality, PDF.js dependency/version, persistent dataset layout, or adding annotations/download/cloud processing.

**Never:** Do not expose a public/static PDF URL, add web-URL uploads, send Rulebook bytes to a cloud service, add a second PDF renderer, broaden into Play Mode tap-to-advance, or redesign Host authentication.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|----------------------------|----------------|
| HAPPY_PATH | Authenticated Host opens a Game with a Rulebook | `/games/:id/pdf` loads the first page in the PDF.js canvas; zoom, previous/next, page entry, and an available outline all work without creating a Session | N/A |
| HAPPY_PATH | Browser supports Wake Lock and Host enables reading mode | Screen wake lock is requested while viewing and released when leaving/unmounting | A rejected request leaves the viewer usable and reports a calm status |
| ERROR_CASE | Game, Rulebook row, or persisted PDF file is absent | API returns a clear `404`; viewer shows a specific unavailable/error state and no misleading blank document | Do not emit a server traceback or claim the viewer loaded |
| ERROR_CASE | Unauthenticated request or Guest request targets metadata/PDF | Host authentication boundary rejects the request; Guest Room remains unchanged | Return the existing `401` behavior |
| EDGE_CASE | PDF has no outline or direct page input is invalid/out of range | Outline control is hidden/disabled; page value is clamped to a valid page and rendering remains stable | Show no noisy error |
| EDGE_CASE | Browser lacks Wake Lock API | Viewer remains fully usable and shows a visible calm notice that wake lock is unavailable | No feature failure |

</frozen-after-approval>

## Code Map

- `backend/routers/games.py:178-188` -- `rulebook_info` and `rulebook_file`; preserve Host dependency, validate the Game/active row/file, and keep `application/pdf` delivery.
- `backend/models/game.py:15-20` -- `Rulebook` owns the unique Game reference and persisted PDF path; do not alter storage shape.
- `backend/core/auth.py:18-36` -- `require_host` is the existing authentication boundary for both metadata and bytes.
- `frontend/src/App.svelte:17-53` -- route parsing, selected Game lookup, sidebar rendering, and `/games/:id/pdf` mount; add viewer-mode navigation reduction without affecting Guest routes or Session creation.
- `frontend/src/components/Detail.svelte:97-104` -- conditional View rulebook action; retain its no-Rulebook gating and route target.
- `frontend/src/components/PDFViewer.svelte:1-10` -- current PDF.js worker/canvas, serialized rendering, zoom, and page controls; extend this seam with outline, loading/error, page normalization, and Wake Lock behavior.
- `frontend/src/components/Sidebar.svelte:1-3` -- existing 240px/60px collapse contract used by reduced viewer navigation.
- `frontend/package.json:8-20`, `frontend/vite.config.ts:1-3`, `frontend/public/pdf.worker.mjs` -- established PDF.js dependency and bundled worker/build path; reuse them.
- `tests/test_app.py:264-363`, `frontend/tests/interaction-contracts.test.mjs:1-56` -- existing Rulebook/backend and dependency-free frontend contract suites; add PDF response/auth and viewer interaction coverage.

## Tasks & Acceptance

**Execution:**
- [x] `backend/routers/games.py` -- harden Rulebook metadata/file responses for missing Games and files while preserving Host-only MIME delivery -- prevent inconsistent 500 responses.
- [x] `frontend/src/components/PDFViewer.svelte` -- implement outline drawer/navigation, robust loading/error states, normalized page entry, responsive controls, and optional Wake Lock lifecycle/status -- complete the reading experience without native PDF rendering.
- [x] `frontend/src/App.svelte` and `frontend/src/components/Sidebar.svelte` -- identify PDF viewer mode and reduce Host navigation while retaining accessible escape/back navigation and responsive layout.
- [x] `tests/test_app.py` and `frontend/tests/interaction-contracts.test.mjs` -- cover PDF success/404/auth/file-missing behavior and viewer control, outline, Wake Lock fallback, and route contracts.

**Acceptance Criteria:**
- Given an authenticated Host opens a Game with an uploaded Rulebook, when the viewer route loads, then PDF.js renders the first page without creating a Session and the Host can zoom, navigate pages, enter a page number, and use an available outline.
- Given the viewer is open, when Host navigation is displayed, then it is reduced according to the PDF viewer UX while remaining keyboard- and mobile-usable.
- Given a browser supports Wake Lock, when reading mode is enabled and later left, then the lock is requested and released; when unsupported or rejected, the viewer remains usable and announces a calm visible notice.
- Given the Game, Rulebook row, or file is missing, when the route or PDF resource is requested, then a clear unavailable/`404` state is shown and no blank or misleading viewer is presented.
- Given an unauthenticated request or Guest Room request targets a Rulebook, when it reaches the server, then the Host boundary rejects it and no Guest route exposes PDF bytes.
- Given a PDF is loaded at supported desktop, tablet, or 375px mobile widths, when controls are used, then the layout has no unintended horizontal scroll and does not rely on the native browser PDF plugin.

## Design Notes

Keep PDF.js document loading and rendering in one component so route teardown can cancel/release resources. Treat outline entries as optional PDF.js metadata: expose a drawer only when entries exist, recursively render nested destinations, and close it after navigation. Wake Lock is an enhancement, never a prerequisite for reading.

## Verification

**Commands:**
- `python3 -m pytest tests/test_app.py` -- expected: Rulebook PDF success, missing-file, 404, and Host-auth tests pass.
- `npm --prefix frontend run check` -- expected: Svelte and TypeScript checks pass.
- `npm --prefix frontend run test:contracts` -- expected: viewer route/control and Wake Lock fallback contracts pass.
- `npm --prefix frontend run build` -- expected: production bundle includes the PDF.js worker and succeeds.

## Suggested Review Order

**Protected Rulebook boundary**

- Validate missing Games, rows, and persisted files before serving bytes.
  [`games.py:178`](../../backend/routers/games.py#L178)

- Confirm the PDF response retains Host auth and the application PDF MIME type.
  [`games.py:190`](../../backend/routers/games.py#L190)

**Viewer lifecycle and reading controls**

- Follow document loading, optional outline handling, and source replacement cleanup.
  [`PDFViewer.svelte:146`](../../frontend/src/components/PDFViewer.svelte#L146)

- Inspect Wake Lock race guards and release behavior across toggles and teardown.
  [`PDFViewer.svelte:97`](../../frontend/src/components/PDFViewer.svelte#L97)

- Review rendering, zoom scaling, page navigation, and responsive canvas overflow.
  [`PDFViewer.svelte:74`](../../frontend/src/components/PDFViewer.svelte#L74)

**Reduced Host navigation**

- Check viewer route rendering, Contents Escape behavior, and accessible exit navigation.
  [`App.svelte:50`](../../frontend/src/App.svelte#L50)

- Confirm PDF mode becomes icon-only while preserving a labeled Back-to-game control.
  [`Sidebar.svelte:5`](../../frontend/src/components/Sidebar.svelte#L5)

**Verification**

- Exercise PDF success, 404, MIME, no-Session, and Host-auth contracts.
  [`test_app.py:279`](../../tests/test_app.py#L279)

- Check the dependency-free viewer, route, outline, and Wake Lock contracts.
  [`interaction-contracts.test.mjs:8`](../../frontend/tests/interaction-contracts.test.mjs#L8)
