<!-- bmad:context -->
<!-- Verified 2026-09-07 against (no commits yet — fill SHA on first refresh after initial commit). Managed by bmad-project-context; edits inside this block are replaced on refresh. Keep anything you want preserved outside the markers. -->

## to-board

Self-hosted board game night companion app. Deployed as a Docker Compose stack on TrueNAS SCALE; serves the Host (Baptiste, single authenticated user) and Guests (unauthenticated, LAN-only) entirely from local storage. No cloud calls at runtime — only during AI content generation, which is Host-triggered only. Planning artifacts in `_bmad-output/planning-artifacts/`; stack decisions deferred to Architecture phase.

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

TODO: no commands yet — stack decisions deferred to Architecture phase. Verify and fill on first refresh after code exists.

## Conventions that differ from defaults

- Host authentication: Authentik OIDC SSO — to-board has no login screen. Unauthenticated requests to Host routes redirect to Authentik. Guest routes (`/room/:slug`) require no authentication.
- Real-time session-end notification: SSE. Not polling, not WebSocket (decided — see FR-14).
- PDF rendering: PDF.js. Never the browser's native PDF plugin — viewer controls must work consistently across browsers (FR-3).
- Guest Room must render without horizontal scroll at 375px viewport (iPhone SE baseline — FR-13).

<!-- /bmad:context -->

@RTK.md
