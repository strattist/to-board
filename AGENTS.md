<!-- bmad:context -->
<!-- Verified 2026-09-07 against (no commits yet — fill SHA on first refresh after initial commit). Managed by bmad-project-context; edits inside this block are replaced on refresh. Keep anything you want preserved outside the markers. -->

## to-board

Self-hosted board game night companion app. Deployed as a Docker Compose stack on TrueNAS SCALE; serves the Host (Baptiste, single authenticated user) and Guests (unauthenticated, LAN-only) entirely from local storage. No cloud calls at runtime — only during AI content generation, which is Host-triggered only. Planning artifacts in `_bmad-output/planning-artifacts/`; stack decisions deferred to Architecture phase.

## General rules

- Read the existing code before changing it.
- Prefer small, focused changes.
- Do not modify unrelated files.
- Do not introduce dependencies unless necessary.
- Follow the existing project conventions.
- Run relevant tests after making changes.
- Explain failing tests rather than hiding or bypassing them.

## Policy

- Never push directly to `main`; PRs only.
- Never edit files under `_bmad/` or `.agents/` outside an explicit BMad skill invocation.
- Persistent data (PDFs, content, sessions) must map to a named TrueNAS dataset — never a Docker-managed volume. A Docker volume loses data on container rebuild (NFR-4).
- No local LLM inference. All AI generation calls an external cloud API (Anthropic or Google). Never add Ollama or any local model dependency.
- Never collect, log, or persist Guest data (IP address, device info, usage events). Guests are anonymous readers (NFR-7).

## Where things are

- PRD (FR-1–FR-20): `_bmad-output/planning-artifacts/prds/prd-to-board-2026-09-03/prd.md`
- UX spine + mockups: `_bmad-output/planning-artifacts/ux-designs/ux-to-board-2026-09-04/`
- Domain vocabulary (Game, Rulebook, Content, Pipeline State, Session, Room — terms that don't mean what they look like): PRD §4 Glossary

## Running and verifying

Install dependencies from the repository root:

```bash
python3 -m pip install -r requirements.txt
npm --prefix frontend ci
```

Run the backend tests:

```bash
python3 -m pytest
```

Run the pre-commit hooks across the repository:

```bash
uvx prek==0.5.3 run --all-files
```

Run the frontend checks and build:

```bash
npm --prefix frontend run check
npm --prefix frontend run test:contracts
npm --prefix frontend run test:dom
npm --prefix frontend run build
```

To verify the deployed stack locally, prepare `.env` and the bind-mounted data directories as described in `README.md`, then run `rtk docker compose up --build` and check `http://localhost/api/health`.

## Conventions that differ from defaults

- Host authentication: Authentik OIDC SSO — to-board has no login screen. Unauthenticated requests to Host routes redirect to Authentik. Guest routes (`/room/:slug`) require no authentication.
- Real-time session-end notification: SSE. Not polling, not WebSocket (decided — see FR-14).
- Single API worker: the `api` container runs one uvicorn process, and open Guest SSE connections live in that process's memory (`backend/routers/room.py`). Do not add uvicorn/gunicorn workers or scale the `api` service without first moving that state to a shared channel; Guests would silently stop receiving `session-ended`.
- PDF rendering: PDF.js. Never the browser's native PDF plugin — viewer controls must work consistently across browsers (FR-3).
- Guest Room must render without horizontal scroll at 375px viewport (iPhone SE baseline — FR-13).

## Story process

- One story per branch and PR; every commit subject names the story id (`(Story 3.5)`) or uses `chore:`/`fix:`. Keep config or harness changes off story branches unless they are part of the story.
- Every story has a spec artifact in `_bmad-output/implementation-artifacts/` before it is marked `done`.
- An acceptance criterion that is dropped or changed is recorded in the story spec and in `deferred-work.md` (or reconciled in `epics.md`) before the story is marked `done`; a commit message alone is not a record.
- Remove an entry from `deferred-work.md` when the story that resolves it ships.
- A story that changes visible Host or Guest UI is not `done` on DOM and source-text tests alone: check the changed pages once in a real browser at 375px and a desktop width (no horizontal overflow, computed text contrast of at least 4.5:1, visible focus ring) and record the result in the story spec. Review lenses for such a story include contrast and computed focus state.

## Git

- Do not create commits unless explicitly asked.
- Do not reset, rebase, or force-push unless explicitly asked.
- Do not discard existing user changes.

## Security

- Never expose secrets, tokens, credentials, or private keys.
- Do not modify authentication or authorization behavior without explaining the change.
- Do not execute destructive commands without asking first.

<!-- /bmad:context -->

@RTK.md
