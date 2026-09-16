# Epic 1 Context: Build and Manage the Game Library

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Give the Host a durable game library that is the entry point for every later workflow: create and browse Games, manage their authoritative Rulebooks, consult Rulebooks without a Session, and remove Games safely while preserving historical Session meaning.

## Stories

- Story 1.1: Create and Browse Game Entries
- Story 1.2: Upload and Replace a Game Rulebook
- Story 1.3: View a Rulebook Independently
- Story 1.4: Delete a Game Safely
- Story 1.5: Implement the Host Collection and Game Detail Experience

## Requirements & Constraints

- Host creation accepts a non-empty title, produces a UUID v4 and ISO 8601 UTC creation timestamp, and makes the Game visible in Collection immediately.
- A Game may have one optional JPEG, PNG, or WebP cover no larger than 10 MB. Invalid or corrupt covers must not be persisted. Rulebooks are PDFs with the approved upload limit, stored durably, and one active Rulebook is allowed per Game.
- Rulebook replacement must remove the old file, extracted-text cache, and row atomically. Existing Published Content remains until explicitly regenerated; dependent Draft or Rejected content follows the pipeline invalidation rules.
- Game and Rulebook management is Host-only through the Authentik boundary. Guest routes remain anonymous and must not expose collection management or Rulebooks.
- Game deletion removes associated files and Content while historical Sessions retain their game-title snapshot.
- All structured data uses the single SQLModel-backed SQLite database. Persistent database, PDFs, and extracted text use the named TrueNAS dataset mounts; no Docker-managed persistent volume or second database is allowed.
- Game state is server-owned and must be represented by the current PipelineState, not inferred or mutated by the frontend. API errors use standard FastAPI shapes.

## Technical Decisions

- Use the layered monolith: FastAPI/Python backend, compiled Svelte frontend, and nginx front door; no runtime Node process.
- Keep Game, Rulebook, Content, PipelineState, Session, and Room as the domain vocabulary. UUID generation, slugification, and UTC timestamps use shared backend conventions.
- Keep service-layer ownership of persistence and state transitions. Extraction runs asynchronously in-process and writes the absolute extracted-text path before the Game becomes ready for generation.
- Host pipeline state is polled at no more than five seconds; SSE is reserved for Guest Session-end notification.
- Protect every Host API route with `require_host`; Authentik OIDC/JWKS is the authentication model and there is no in-app login screen.

## UX & Interaction Patterns

- Collection is a responsive poster grid using 2:3 Game Cards, 160–260px card sizing, 16px gaps, and a 32px minimum main-content inset within the dark Aura design system.
- A card uses cover art when available and an initials placeholder otherwise. Its title is one-line truncated, its current status is always text-bearing, and it is keyboard-focusable and activatable with Enter or Space.
- Status labels are calm and semantic: “No content yet”, “Preparing…”, “Ready to generate”, “Generating…”, “Needs review”, “Ready to play”, and “Rejected”. Color never carries meaning alone.
- Host navigation uses the responsive sidebar and Game Detail route relationships defined by the UX spine. Forms use accessible labels, visible 2px focus rings, and 44px touch targets; destructive actions require confirmation.
- Rulebooks render through PDF.js with zoom, page navigation, direct page entry, and optional table-of-contents navigation. The browser’s native PDF plugin is not used.

## Cross-Story Dependencies

Story 1.1 establishes the Game record, Collection, status display, and cover flow used by all later Epic 1 stories. Story 1.2 supplies the Rulebook and extraction prerequisites for content-generation work in Epic 2. Story 1.3 depends on Rulebook persistence and Host authorization. Story 1.4 must preserve Session title snapshots from Epic 4 while removing current Game-owned data. Story 1.5 consolidates the Host Collection and Game Detail surfaces over these capabilities.
