# Epic 4 Context: Preserve and Review Game-Night History

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

The Host can rely on every started Session being persisted immediately and durably, add player names and ordered outcomes to a Session, browse past Sessions in reverse chronological order, filter them by Game, and keep readable history even after a Game is deleted. It turns the Session records created in Epic 3 into a lasting game-night log.

## Stories

- Story 4.1: Persist Session Records Reliably
- Story 4.2: Record Players and Outcomes
- Story 4.3: Browse and Filter Session History
- Story 4.4: Present a Durable Session History Experience

## Requirements & Constraints

- A Session stores UUID, Game reference, Game title snapshot and ISO 8601 UTC `started_at`; it is written before success is returned, and a persistence failure fails creation explicitly with no QR Room or active state shown.
- Records survive API container restarts and TrueNAS SCALE updates; an active Session stays identifiable as active after restart.
- A Session must stay readable after its Game is deleted, using the title snapshot, and must remain filterable.
- Players: up to 12 free-text names, no accounts or profiles. Outcomes: up to 20 ordered free-text entries (zero allowed), may represent repeated plays within one Session. Invalid or over-limit input returns 422 and leaves persisted values unchanged.
- Players and outcomes remain editable after a Session has ended without reopening the Session or Room.
- All Session history and metadata routes are Host-only (Authentik); Guest Room routes never expose or edit them.
- Guests are anonymous: no Guest identity, IP or device data is stored in Session records (NFR-7).

## Technical Decisions

- SQLite single file at `/data/db/to-board.db` via SQLModel only; no other engine, no raw sqlite3 (AD-2).
- Persistence only through named TrueNAS dataset bind mounts (`to-board-db` at `/data/db/`); no Docker-managed volumes (AD-3, NFR-4).
- Session model lives in `backend/models/session.py`; state mutation goes through the service layer; API timestamps are ISO 8601 UTC strings stored as TEXT.
- Single uvicorn worker; do not add workers without moving SSE state to a shared channel.

## UX & Interaction Patterns

- Routes: Session Log and Session Detail, reverse chronological, with a Game filter and calm, specific empty states.
- State (active/ended) conveyed by text and accessible semantics, never color alone.
- Shared Host navigation, responsive layouts without unintended horizontal scroll, visible primary-color focus ring, DOM-order focus.
- Skeleton or inline loading, never a full-screen blocking overlay; microcopy without exclamation marks or emoji.

## Cross-Story Dependencies

- 4.1 hardens persistence and snapshot behavior already introduced by Epic 3 Stories 3.1 and 3.5; 4.2 to 4.4 build on that record.
- 4.3 depends on 4.1 snapshots and 4.2 players/outcomes for list display; 4.4 is presentation over 4.2 and 4.3.
