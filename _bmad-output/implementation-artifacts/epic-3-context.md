# Epic 3 Context: Run a Game Night with Guest Rooms

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

The Host starts a Session for a Game with Published Content, shows a scannable QR Room on a full-screen reveal, and ends the Session. Guests open the Room anonymously on their phones, read the Quick-start Guide and Cheat Sheet served from local storage, and are told in real time when the Session ends.

## Stories

- Story 3.1: Start a Session for a Ready Game
- Story 3.2: Reveal and Share a Session QR Room
- Story 3.3: Access the Guest Room Anonymously
- Story 3.4: Use the Mobile Guest Room
- Story 3.5: End a Session and Notify Guests

## Requirements & Constraints

- A Session needs Published Content and is refused otherwise; Rulebook extraction state is irrelevant. Only one active Session per Game; a second start returns 409 and leaves the existing Room unchanged.
- A Session records a UUID, Game reference, title snapshot, unique Room slug and ISO 8601 UTC `started_at`, persisted immediately. Failures must surface clearly; never show a QR or Room for an unpersisted Session.
- Guests are anonymous: no auth, account, app install, push prompt or cookie banner. Never persist or log IP, device info or usage events. No Guest alias or presence list exists (dropped in the Epic 3 retro to keep NFR-7 strict). No external runtime calls.
- Up to 8 simultaneous Guests. The Room is interactive within the NFR-1 target on the LAN and has no horizontal scroll at 375px.
- Unknown, malformed, inactive or ended slugs show a clear unavailable/ended state. Draft and Rejected Content is never exposed to Guests.
- Ending a Session sets `ended_at`, deactivates the QR and Room, and notifies Guests with no refresh. A failed end must not be presented as ended.

## Technical Decisions

- Host session routes (`/api/sessions/*`) depend on `require_host`. Guest routes (`GET /api/room/:slug`, `GET /api/room/:slug/events`) carry no auth dependency.
- Room slug is `<game.room_slug_prefix>-<4-char base36>`, generated at Session creation. Slugification lives in `backend/core/utils.py:slugify()`.
- SSE is the only real-time channel: `GET /api/room/:slug/events` sends `event: session-ended` then closes. Connections are tracked in memory as asyncio Queues only, with no client IP stored.
- State changes are server-owned in `backend/services/`. Routers call services and never write to the DB directly.
- Room content is served from the `published_*` Content columns (Markdown). The frontend renders it through the single shared sanitizing `<Markdown>` component.
- The QR code is generated client-side; the QR Reveal and Room Page are Svelte routes/components.

## UX & Interaction Patterns

- QR Reveal (`/session/:id`): a full-screen `role="dialog"` with `aria-label="Game night session for [Game Title]"`. It shows a blurred cover-art backdrop, a 280px QR with `alt="QR code for [Game Title] room — URL: [room-url]"`, the game title in display type, and the mono Room URL. The URL copies on click, with the label "Copy" becoming "Copied" for 1.5s. The sidebar is hidden, a top-right `×` or Escape exits without ending the Session, and the fade is 300ms (0 under reduced motion).
- Start session is disabled with an explanation when there is no Published Content or a Session is already active.
- Room Page: a centered single column, max 640px, with the game title, a minimal wordmark, sticky "Quick-start Guide" and "Cheat Sheet" tabs that toggle via `display` with no navigation, and 44px minimum touch targets. No Host chrome and no microcopy beyond headings.
- End session uses a destructive confirmation: "End this session? The room will close for all guests." The ended Room shows the game title, "This session has ended." and the wordmark, announced via `aria-live="polite"`.

## Cross-Story Dependencies

- 3.2, 3.3 and 3.5 depend on the Session and slug created in 3.1. 3.4 builds on the Room route from 3.3. 3.5's SSE closes streams opened by 3.3's Room.
- Frontend DOM test harness (Vitest + @testing-library/svelte + jsdom, separate `test:dom` script) is to be set up just before Story 3.4.
- Epic 4 (Session history) consumes the Session records created here.
