---
title: 'to-board build kickoff'
type: 'feature'
created: '2026-09-12'
status: 'done'
baseline_commit: 'bb912376bd07d9556f8352fa427d500ad02c8247'
review_loop_iteration: 1
context: ['{project-root}/AGENTS.md','{project-root}/_bmad-output/planning-artifacts/prds/prd-to-board-2026-09-03/prd.md','{project-root}/_bmad-output/planning-artifacts/architecture/architecture-to-board-2026-09-07/ARCHITECTURE-SPINE.md','{project-root}/_bmad-output/planning-artifacts/ux-designs/ux-to-board-2026-09-04/','{project-root}/_bmad-output/planning-artifacts/epics.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The product vision for to-board has already been validated in planning artifacts, but there is no implementation work started yet. The project needs a disciplined build pass that turns the approved requirements, UX, and architecture into working, reviewable code without drifting from the agreed constraints.

**Approach:** Implement the project in bounded epic-story slices, starting with the first ready feature set, while preserving the architecture invariants and verifying results against the PRD, UX, and sprint tracking before moving on.

## Boundaries & Constraints

**Always:**
- Follow the architecture spine and its invariants: Python FastAPI backend, compiled Svelte frontend, nginx front door, SQLite with SQLModel, TrueNAS dataset bind mounts, and no Docker volumes for persistent runtime data.
- Preserve the domain vocabulary and API boundaries defined in the PRD and architecture: Game, Rulebook, Content, Session, Room, and PipelineState.
- Respect host-vs-guest auth, no Guest data logging, and the single cloud-generation model only for Host-triggered content generation.
- Store content as Markdown in SQLite and render with a single shared sanitized frontend component.
- Use the existing sprint status file as the source of truth for epic/story progression.

**Ask First:**
- Any change that alters the app’s core architecture, data model cardinality, or auth model beyond what the architecture spine already authorizes.
- Any scope change that adds a new feature outside the approved FRs or defers a requirement that is tied to a story already tracked in the epic breakdown.

**Never:**
- No Docker-managed persistent volumes for runtime data.
- No local LLM inference or local model dependency.
- No Guest identity capture, analytics, or persistent Guest data.
- No direct frontend mutation of pipeline state.
- No added database engines or raw sqlite3 write patterns outside the single SQLModel path.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY_PATH | Host creates a Game and uploads a PDF rulebook | Game appears in collection, rulebook is stored under dataset mount, extraction starts, and the Host sees pipeline progress | If upload or extraction fails, show validation or service error with no silent success |
| ERROR_CASE | Missing API key or extraction prerequisites before generation | Generation request is blocked with a clear validation error and no cloud call occurs | Return a human-readable FastAPI error and keep pipeline state unchanged |
| HAPPY_PATH | Guest opens room URL after Session start | Anonymous guest page loads mobile content without auth and shows current published content | Graceful ended-room notice if Session has closed |
| ERROR_CASE | Re-upload of a rulebook for an existing Game | Old rulebook row and files are replaced atomically with the new one | Transaction failure prevents partial replacements and leaves prior state intact |

</frozen-after-approval>

## Code Map

- `AGENTS.md` -- repo-level operating constraints and project-specific policy for the app and BMad workflow.
- `_bmad-output/planning-artifacts/prds/prd-to-board-2026-09-03/prd.md` -- authoritative product requirements and FR/NFR baseline.
- `_bmad-output/planning-artifacts/architecture/architecture-to-board-2026-09-07/ARCHITECTURE-SPINE.md` -- technical invariants, stack decisions, and state-machine rules.
- `_bmad-output/planning-artifacts/ux-designs/ux-to-board-2026-09-04/` -- UX expectations, flows, and responsive UI requirements.
- `_bmad-output/planning-artifacts/epics.md` -- story breakdown and epic ordering that drives implementation slices.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- current implementation readiness and story status ledger.

## Tasks & Acceptance

**Execution:**
- [x] `backend/` -- scaffold the FastAPI app, config, database model layer, and service routes in line with the architecture spine and PRD.
- [x] `frontend/` -- scaffold the Svelte SPA shell, shared styles, and Host/Guest route structure to match the UX design and mobile constraints.
- [x] `backend/services/` -- implement the game, rulebook, content, and session state transitions without allowing frontend-owned mutation.
- [x] `backend/workers/` and related extraction flow -- implement local PDF extraction and staged generation pipeline behavior with recovery logic.
- [x] `frontend/src/` -- implement the Host collection, Game Detail, PDF viewer, QR reveal, and Guest Room behavior described in UX and FR coverage.
- [x] `docker-compose.yml` and deployment config -- wire the runtime stack to the approved TrueNAS datasets and nginx/API topology.
- [x] `tests/` or equivalent validation targets -- add coverage for the critical flows and pipeline edge cases enumerated in the PRD and architecture.

**Acceptance Criteria:**
- Given the project requirements are loaded, when the implementation begins, then the system follows the architecture invariants and is split into coherent, reviewable epic/story work.
- Given a valid Game and Rulebook, when the Host uploads and generates content, then the app applies the allowed pipeline transitions and preserves the published content correctly.
- Given a Session is started, when Guests access the room URL, then they can view the published quick-start and cheat-sheet content without authentication and without a refresh on closure.
- Given local persistent storage requirements, when the app restarts, then SQLite and uploaded files remain on the approved TrueNAS dataset mounts and no runtime data is lost.

## Spec Change Log

## Design Notes

The app should be built as a series of epic slices rather than a single monolithic commit. The first slice should focus on the core library and rulebook lifecycle (Game + Rulebook + content pipeline), because the architecture and PRD make those the dependency chain for Sessions and Guest Rooms. This keeps the implementation testable and preserves a clean path to review: model/store layer first, then the Host UI, then the Session/Guest experience.

## Verification

**Commands:**
- `npm install --no-fund --no-audit` -- expected: frontend dependency tree installs cleanly for the Svelte app.
- `python -m compileall backend` -- expected: backend modules compile without syntax errors.
- `pytest -q` or equivalent test runner -- expected: critical acceptance tests for game, content, and session workflows pass.

**Manual checks (if no CLI):**
- Open the Host collection and confirm the UX matches the approved responsive layout and sidebar behavior.
- Verify the Guest Room remains anonymous and mobile-safe at 375px width.
- Confirm the app reads and writes only to the named dataset paths, not Docker-managed volumes.

## Suggested Review Order

**Application boundary and persistence**

- FastAPI lifespan initializes SQLModel tables and recovers interrupted jobs.
  [`main.py:7`](../../backend/main.py#L7)

- Dataset paths and bind mounts keep SQLite and uploads durable across rebuilds.
  [`docker-compose.yml:1`](../../docker-compose.yml#L1)

**Domain state and background work**

- Server-owned pipeline transitions preserve published Markdown while drafts regenerate.
  [`content.py:7`](../../backend/services/content.py#L7)

- Rulebook replacement swaps the unique row, files, and extraction job boundary.
  [`games.py:72`](../../backend/routers/games.py#L72)

- Guest Room serving exposes only published content and supports session-end SSE.
  [`room.py:14`](../../backend/routers/room.py#L14)

**Host and Guest experience**

- SPA routing separates authenticated Host surfaces from the anonymous Room and QR reveal.
  [`App.svelte:22`](../../frontend/src/App.svelte#L22)

- Shared Markdown rendering sanitizes generated content before browser insertion.
  [`Markdown.svelte:1`](../../frontend/src/lib/Markdown.svelte#L1)

**Verification**

- Acceptance tests cover creation, prerequisites, publication, sessions, uploads, and replacement.
  [`test_app.py:18`](../../tests/test_app.py#L18)
