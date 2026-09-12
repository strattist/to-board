---
title: "PRD: to-board"
status: final
created: 2026-09-03
updated: 2026-09-03
---

# PRD: to-board

*For Baptiste (sole developer and primary user) and downstream workflow consumers (architecture, UX, epics). Builds on the product brief at `_bmad-output/planning-artifacts/briefs/brief-to-board-2026-09-03/brief.md`. The Glossary in §4 defines all domain nouns; FRs are numbered globally (FR-1 through FR-20); assumptions are tagged inline and indexed in §12.*

---

## 1. Vision

to-board is a self-hosted web app deployed on a personal NAS that centralises everything the Host needs to run a smooth board game night: official PDF rulebooks, AI-generated quick-start guides and cheat sheets, a QR-based room system for instant Guest access, and a growing session history.

The product exists to close the gap between opening a box and actually playing. A Host who has added a game to to-board can explain the rules confidently, show Guests a cheat sheet on their own phones, and log the session without relying on any third-party service. The app runs on the local network, requires no Guest accounts, and accumulates the group's gaming history.

It is Baptiste's personal tool first. The five design invariants from the brief govern every feature decision — they are not preferences, they are constraints:

| Invariant | Enforced by |
|---|---|
| Solo-first | FR-19, FR-20: full app usable without Guests or active Session |
| Unobtrusive | FR-12: no banners, prompts, or consent flows on the Guest Room page |
| PDF-authoritative | FR-8: Published Content never replaces the Rulebook; FR-3: Rulebook viewer always accessible to the Host |
| Layered depth | FR-13: Cheat Sheet first; Rulebook one tap away via Host preview (FR-20) |
| Learns through use | SM-C1: Session Log and Content reviews feed the same feedback loop (see §8 Q8) |

---

## 2. Target User

### 2.1 Jobs To Be Done

**Host (Baptiste):**
- I need to explain a game's rules confidently to mixed-experience groups without reading aloud from a PDF.
- I need Guests to be able to look up rules on their own phones without interrupting the game.
- I need a shared, persistent record of every game night — who played, who won, when.
- I need to manage this from a NAS I already run, without subscribing to any service.

**Guest (friends at the table):**
- I need to join a game session from my phone without downloading an app or creating an account.
- I need a concise reference I can consult silently during play.

---

## 3. Key User Journeys

**UJ-1. Baptiste adds a new game and prepares it for game night.**

- **Persona + context:** Baptiste has just bought Wingspan and wants it ready before the next game night, while relaxed at his desk.
- **Entry state:** Authenticated on the Collection screen. No Wingspan entry yet.
- **Path:**
  1. Taps "Add game"; enters title "Wingspan"; saves.
  2. On the game detail screen, taps "Upload rulebook"; selects the Wingspan PDF from their device.
  3. System confirms upload and surfaces a "Generate content" action.
  4. Baptiste taps Generate; confirms the cloud API call; waits (2–5 minutes).
  5. System notifies when Draft Content is ready; Baptiste navigates to the Review screen.
  6. Reads through the Quick-start Guide and Cheat Sheet; finds the VP scoring section garbled.
  7. Rejects the draft → triggers regeneration; second pass is accurate; publishes.
- **Climax:** "Published" indicator appears on Wingspan in the collection. The game is ready.
- **Resolution:** Baptiste closes the app. Wingspan is in the collection, Content is published, nothing further is needed before game night.
- **Edge case:** API Key is expired. System surfaces a setup-screen link with the specific error; Generation is blocked until the Key is updated. Existing Published Content for other games is unaffected.

---

**UJ-2. Baptiste runs a game night session.**

- **Persona + context:** Baptiste is hosting three friends for a first Wingspan session.
- **Entry state:** Authenticated on the Collection screen. Wingspan has Published Content.
- **Path:**
  1. Selects Wingspan → taps "Start session".
  2. QR Code appears on the host screen (or browser tab cast to a TV).
  3. Friends scan the QR Code; each arrives at the Wingspan Room page on their phones.
  4. Baptiste switches to Play Mode: screen stays awake, rule explanation begins.
  5. Game starts; players reference the Cheat Sheet on their phones throughout.
- **Climax:** Rule explanation completes in under 10 minutes; everyone understands the core loop and starts playing.
- **Resolution:** Session is active in the log. Host and Guests play with no further app interaction required.
- **Edge case:** One Guest's phone camera cannot scan QR. Host reads the Room URL aloud (short, human-readable). [ASSUMPTION: Room URLs are short and pronounceable, e.g., `/room/wingspan-3f2a`.]

---

**UJ-3. A Guest silently looks up a rule mid-game.**

- **Persona + context:** Alex, a first-time Wingspan player, has a question about egg costs but does not want to pause the game.
- **Entry state:** On the Room page (joined via QR Code during UJ-2). Game is mid-play.
- **Path:**
  1. Alex scrolls the Cheat Sheet section on their phone.
  2. Finds "Egg costs" bullet; reads the clarification.
  3. Returns to the game.
- **Climax:** Question answered in under 10 seconds without speaking.
- **Resolution:** Game continues; no one at the table noticed. `[NON-GOAL for MVP: deep-link from Cheat Sheet to PDF page — deferred to v1.1 (see FR-13 note).]`

---

**UJ-4. Baptiste logs the session after game night.**

- **Persona + context:** Game is over, friends are getting ready to leave. Baptiste wants to capture it.
- **Entry state:** Authenticated; the Session from UJ-2 is active.
- **Path:**
  1. Navigates to the active Session; taps "End session".
  2. Adds player names: "Alex, Camille, Jordan".
  3. Sets outcome: "Jordan won".
  4. Saves. QR Code becomes inactive.
- **Climax:** Session is saved in the log with game, players, date, and outcome.
- **Resolution:** Session history grows by one entry. The Wingspan Room URL now shows a "session ended" page.

---

## 4. Glossary

- **Game** — a board game entry in to-board's collection. Has a title, optional cover image, one Rulebook, and one set of Content. Identified by a unique system ID.
- **Rulebook** — the official PDF uploaded by the Host for a Game. The authoritative source for rules; never modified or replaced by AI-generated material.
- **Quick-start Guide** — AI-generated narrative walkthrough of a Game's core rules, written for first-time players. Approximately a 5-minute read. Part of Content.
- **Cheat Sheet** — AI-generated structured reference of key rules, turn sequence, and common gotchas for a Game. Designed for at-a-glance lookup during play. Part of Content.
- **Content** — the pair of Quick-start Guide and Cheat Sheet for a Game. Exists in exactly one Pipeline State at any time.
- **Pipeline State** — the lifecycle state of Content: `Draft` (generated, awaiting Host review), `Published` (Host-approved, served to Guests), `Rejected` (failed Host review, eligible for regeneration).

  Valid transitions:

  | From | To | Trigger |
  |---|---|---|
  | *(none)* | `Draft` | Host triggers Generation (FR-5) |
  | `Draft` | `Published` | Host publishes (FR-7) |
  | `Draft` | `Rejected` | Host rejects (FR-7) |
  | `Rejected` | `Draft` | Host triggers regeneration (FR-5) |
  | `Published` | `Draft` | Host triggers regeneration (new Draft created; Published remains until new Publish) |

  There is no "unpublish" transition. A Game with `Published` Content retains it until the Host publishes a new generation. `Rejected` Content cannot be recovered — only regenerated.

- **Generation** — the one-time process of extracting PDF text locally and sending it to a cloud LLM to produce Draft Content. Triggered explicitly by the Host; requires a configured API Key.
- **API Key** — the cloud LLM credentials supplied by the Host at setup (BYOK). Stored locally on the NAS. Required only for Generation; not required at runtime.
- **Session** — a recorded instance of a Game being played. Contains: game reference, date, Host, player names (optional), outcome (optional). Created when the Host starts a Room flow.
- **Room** — the web page Guests arrive at after scanning the QR Code for a Session. Displays the Game's Published Content. Active while the Session is open; shows a closed state after the Host ends the Session.
- **QR Code** — a scannable code generated per Session encoding the Room URL. Active while the Session is open. One QR Code per Session; no permanent codes.
- **Host** — Baptiste; the sole authenticated user of to-board. Manages the collection, controls Sessions, reviews and publishes Content.
- **Guest** — a friend at the table who joins a Session via QR Code. Unauthenticated; read-only access to the Room. No data is persisted about Guests.
- **Play Mode** — a Host-facing display mode for rule explanation. The screen stay-awake is active; UI chrome is minimised; tap-to-advance through the Quick-start Guide.

---

## 5. Features

### 5.1 Game Collection & PDF Library

**Description:** The Host manages a personal library of Games, each with an uploaded Rulebook PDF. The library is the root of all other features — Generation, Rooms, and Sessions all require a Game. The PDF viewer supports in-browser reading with controls appropriate for a rule-explanation context. The solo-first invariant requires that the PDF viewer and Host Content preview are always accessible without starting a Session (FR-19, FR-20). Realizes UJ-1.

**Functional Requirements:**

#### FR-1: Host creates a Game entry

The Host can create a new Game entry by providing a title.

**Consequences (testable):**
- A Game record is created with a unique system ID, the provided title, and a `created` timestamp.
- The Game appears in the Collection list immediately.
- Optional cover image can be added at creation or later; omitting it does not block creation.

#### FR-2: Host uploads a Rulebook PDF

The Host can upload a PDF file as the Rulebook for a Game.

**Consequences (testable):**
- PDF is stored on the NAS in persistent storage (mapped to a TrueNAS dataset, not a Docker volume).
- System immediately begins local text extraction in the background; Host is not blocked.
- If a Rulebook already exists for the Game, the new upload replaces it. Any existing Draft or Rejected Content is invalidated; Published Content is unaffected until the Host explicitly triggers a new Generation. [ASSUMPTION: this is the right default — see §8 Q6.]
- Upload size limit: [ASSUMPTION: 100 MB; sufficient for all known board game PDFs.]

#### FR-3: Host views a Rulebook PDF in the browser

The Host can open a Game's Rulebook in an in-app PDF viewer.

**Consequences (testable):**
- PDF renders in the browser without requiring a download or a native PDF viewer.
- Viewer supports: zoom in/out, page-by-page navigation, direct page number entry, and section jump via the PDF's own table of contents (if present).
- In Play Mode, the Wake Lock API keeps the screen awake on supported browsers. [ASSUMPTION: Wake Lock API is used; degrades gracefully on unsupported browsers with a visible notice.]
- PDF viewer is accessible to the Host only. Guests do not have direct access to the Rulebook PDF in v1; their reference surface is the Room page (FR-13).

**Out of Scope:**
- Annotation, highlighting, or bookmarking within PDFs (deferred to Could Have).

#### FR-4: Host removes a Game

The Host can delete a Game from the collection.

**Consequences (testable):**
- Game record, Rulebook PDF, extracted text cache, and all Content (Draft, Published, Rejected) are removed from storage.
- Past Sessions referencing the deleted Game are preserved; the Game title is retained as a string snapshot on those Session records (e.g., `"Wingspan (deleted)"`).
- Action requires an explicit confirmation step; irreversible.

#### FR-19: Host accesses the PDF viewer without an active Session

The Host can open and read any Game's Rulebook PDF at any time, regardless of whether a Session is active. (Enforces solo-first invariant.)

**Consequences (testable):**
- The Rulebook viewer is accessible from the Game detail screen; no "Start session" step is required to reach it.
- Play Mode (screen stay-awake) is available to the Host in the viewer regardless of Session state.

#### FR-20: Host accesses Published Content without an active Session

The Host can view a Game's Published Quick-start Guide and Cheat Sheet without starting a Session. (Enforces solo-first invariant; enables layered-depth invariant via Host preview.)

**Consequences (testable):**
- A read-only "Host preview" of Published Content is accessible from the Game detail screen.
- This view is functionally equivalent to the Room page but accessible only to the authenticated Host; no QR Code or Session is generated.

---

### 5.2 AI Content Generation Pipeline

**Description:** For each Game with an uploaded Rulebook, the Host can generate a Quick-start Guide and Cheat Sheet via a cloud LLM. The pipeline follows a draft → review → publish flow: the Host reviews AI output before it is published, and can reject and regenerate if quality is poor. Once Published, Content is served from local NAS storage with no further cloud involvement. Realizes UJ-1.

**Functional Requirements:**

#### FR-5: Host triggers Content generation for a Game

The Host can initiate Generation for a Game that has a Rulebook uploaded.

**Consequences (testable):**
- System confirms the API Key is present and Rulebook text extraction is complete before allowing the trigger; surfaces a clear error message if either is missing.
- Generation creates exactly one Quick-start Guide and one Cheat Sheet per trigger.
- Resulting Content enters `Draft` Pipeline State.
- If Content already exists in `Draft` or `Published` state, the Host is warned before triggering a new generation that will replace the existing Draft.

#### FR-6: System performs PDF text extraction locally

Before any data is sent to the cloud LLM, the system extracts text from the Rulebook PDF on the NAS.

**Consequences (testable):**
- No raw PDF bytes are transmitted outside the home network.
- Extracted text is cached locally; re-extraction is not required on subsequent generation attempts unless the Rulebook is replaced.
- If extraction yields fewer than [ASSUMPTION: 500 tokens], system surfaces a warning ("Rulebook may not have extracted cleanly — check the PDF") before proceeding; Host can override.

#### FR-7: Host reviews and acts on Draft Content

The Host can read Draft Content and take one of two actions: Publish or Reject.

**Consequences (testable):**
- **Publish:** Content transitions to `Published` Pipeline State; previous Published Content (if any) is replaced. [ASSUMPTION: only one Published version per Game at a time — see §8 Q1.]
- **Reject:** Content transitions to `Rejected` Pipeline State; Host can immediately trigger a new Generation (returns to FR-5).
- Host can edit Draft Content inline before publishing. [ASSUMPTION: basic text editing, not rich-text; editing does not change Pipeline State to indicate "manually edited" — see §8 Q1.]
- The Quick-start Guide and Cheat Sheet are reviewed and acted on as a pair; partial publication is not supported.

#### FR-8: Published Content is served from local NAS storage

At runtime — during a Session and in any Room — Content is served entirely from NAS-local storage.

**Consequences (testable):**
- No cloud API calls are made during a Session, Room page load, or any Guest-facing interaction.
- Content remains available if the NAS has no internet connection at the time of a game night.
- If a Game has no Published Content, the "Start session" action is disabled for that Game with a visible reason.

#### FR-9: Host configures the cloud API Key

The Host can supply and update a cloud LLM API Key via a setup screen.

**Consequences (testable):**
- API Key is stored locally on the NAS; never transmitted to any destination other than the configured cloud LLM endpoint during Generation.
- Supported providers at v1: [ASSUMPTION: at least one of Anthropic (Claude Haiku) or Google (Gemini Flash); provider selection configurable.]
- If the API Key is absent or invalid, Generation is disabled app-wide; the setup screen surfaces the specific error returned by the provider.
- Updating the Key does not affect existing Content in any Pipeline State.

---

### 5.3 QR Room Flow

**Description:** The Host starts a Session by selecting a Game; the app generates a QR Code encoding the Room URL. Guests scan with any camera app — no account, no install — and arrive at the Room page, which displays the Game's Published Content. The Room stays active until the Host ends the Session. Realizes UJ-2, UJ-3.

**Functional Requirements:**

#### FR-10: Host starts a Session

The Host can start a Session by selecting a Game that has Published Content.

**Consequences (testable):**
- A Session record is created with: game reference, date/time started, and host identity.
- System generates a unique QR Code for this Session.
- The QR Code and Room URL are displayed immediately on the host screen.
- A Game with no Published Content shows "Start session" as disabled with a tooltip or inline reason.

#### FR-11: System generates a unique, scannable QR Code per Session

Each Session has one QR Code encoding a unique Room URL.

**Consequences (testable):**
- QR Code is scannable by standard smartphone camera apps on iOS and Android without any additional app.
- Room URL is unique per Session; a URL from a previous Session for the same Game does not resolve to the new Session.
- Room URL is human-readable and short enough to be typed if the QR fails to scan. [ASSUMPTION: format `/room/{game-slug}-{short-id}`, e.g. `/room/wingspan-3f2a` — see §8 Q3.]
- QR Code is displayed at a size appropriate for scanning from across a table on a laptop screen.

#### FR-12: Guest accesses the Room via QR Code

A Guest can navigate to the Room URL by scanning the QR Code; no authentication, account, or app install is required.

**Consequences (testable):**
- Room page loads within 3 seconds on a LAN connection.
- No login prompt, sign-up prompt, push notification request, or cookie consent banner is shown to Guests. [ASSUMPTION: the app operates entirely within a private LAN; no GDPR/cookie law obligations apply.]
- If the Session is active, Guest sees the Game's Published Quick-start Guide and Cheat Sheet.
- If the Session has ended (see FR-14), Guest sees a "This session has ended" page with the Game name. No further content is accessible.
- No Guest data (IP address, device info, usage events) is persisted.

#### FR-13: Room page displays Published Content

The Room page presents the Game's Published Quick-start Guide and Cheat Sheet in a mobile-optimised layout.

**Consequences (testable):**
- Quick-start Guide and Cheat Sheet are displayed on the same page, either as tabs or sequential sections.
- Layout is readable on a 375 px-wide screen (iPhone SE baseline) without horizontal scrolling.
- Content scrolls smoothly; no pagination required.

`[NON-GOAL for MVP: deep-links from Cheat Sheet items to specific Rulebook PDF pages — deferred to v1.1.]`

#### FR-14: Host ends a Session

The Host can close an active Session.

**Consequences (testable):**
- Session record is updated with an `ended_at` timestamp.
- QR Code becomes inactive; Room URL transitions to "session ended" state.
- Guests currently on the Room page see a "session ended" notice without a page refresh. [ASSUMPTION: this requires a server-push mechanism (SSE or WebSocket) to notify connected clients — see A-15 and §8 Q7.]
- Session record is preserved in the Session Log (see §5.4).

---

### 5.4 Session Log

**Description:** Every Session is automatically created when the Host starts a Room flow (FR-10) and persists in the log after the Session ends. The Host can add players and an outcome, building a persistent gaming history. Realizes UJ-4.

**Functional Requirements:**

#### FR-15: Session record is created automatically on Session start

When the Host starts a Session (FR-10), a Session record is created without additional Host input.

**Consequences (testable):**
- Record contains: game title snapshot, game ID reference, `started_at` timestamp.
- Record is written to persistent storage (TrueNAS dataset) immediately on Session start; survives a container restart even if the Host never explicitly saves it.

#### FR-16: Host adds players and outcome to a Session

The Host can update a Session record with player names and an outcome.

**Consequences (testable):**
- Player names are free-text strings; no accounts, no linking to user profiles. Up to [ASSUMPTION: 12 players] per Session.
- Outcome is a free-text string (e.g., "Jordan won", "cooperative win", "abandoned").
- Players and outcome can be edited after the Session ends; there is no deadline for updating them.

#### FR-17: Host views the Session Log

The Host can view all past Sessions in reverse-chronological order.

**Consequences (testable):**
- Each Session entry shows: game title, date, player names (if set), outcome (if set).
- Log is filterable by game. [ASSUMPTION: basic filter; no full-text search in v1.]
- Deleted-game Sessions display the preserved title snapshot (see FR-4).

#### FR-18: Session data persists across container restarts and OS updates

All Session records survive Docker container restarts and TrueNAS SCALE system updates.

**Consequences (testable):**
- Session data is stored in a volume mapped to a named TrueNAS dataset, not a Docker-managed volume.
- A fresh container start with the same dataset mount restores the full Session history.

---

## 6. Non-Goals (Explicit)

- **Not a multi-user platform.** There are no Guest accounts, Guest profiles, or Guest-generated content. Guests are anonymous readers.
- **Not for users outside the Host's local game group.** to-board has no public-facing surface and no discovery mechanism. Guests joining via QR Code must be on the local network.
- **Not a BGG client.** No BGG API, no BGG data, no collection sync, no BGG recommendations.
- **Not a game recommender.** No discovery, no wishlist, no want-to-play list, no "games you might like."
- **Not a local AI inference host.** All Generation goes through an external cloud LLM API. The NAS does not run Ollama or any local model.
- **Not a digital game table.** No online play, no virtual board, no game engine, no ruleset implementation.
- **Not a cloud service.** No remote access beyond the local network in v1. [ASSUMPTION: no reverse-proxy or Tailscale required for v1.]
- **Scorecards, adaptive quick-start, and AI card lookup are out of scope for v1.** These are well-defined deferred features (see brief addendum MoSCoW).

---

## 7. MVP Scope

### 7.1 Out of Scope for MVP

- **Content quality voting** — Guest can flag bad AI content to trigger Host regeneration. Deferred to v1.1. `[NOTE FOR PM: highest-value v1.1 item; closes the feedback loop while Guests are still at the table.]`
- **Cheat Sheet deep-links to PDF** — Cheat Sheet items link to the exact Rulebook page. Deferred to v1.1.
- **Private phone view** — dedicated Guest-facing reference mode beyond the existing Room. Deferred to v1.1. `[NOTE FOR PM: Unified personal window — private phone view, interactive scorecards, and AI card lookup are three facets of one concept: each player's personal, silent reference during live play. Design them as a single UX surface, not three independent features. Establish the surface in v1.1 with private phone view; extend it in later iterations. See brief addendum §Key Design Synthesis.]`
- **Session photos** — attach photos to a Session record. Deferred to v1.1.
- **Play Mode tap-to-advance** — step through Quick-start Guide sections with explicit taps. v1 Play Mode = screen stay-awake + minimised chrome only. See §8 Q4.
- **Interactive scorecards** — per-game score tracking. Deferred (Could Have).
- **Adaptive quick-start** — experience detection per player. Deferred (Could Have).
- **AI card lookup** — text or photo search answered by AI in game context. Deferred (Could Have).
- **Rule bookmarks within PDFs** — deferred (Could Have).
- **Multi-device or cloud access** — app runs on LAN only in v1.

---

## 8. Open Questions

1. **Inline editing of Draft Content (FR-7, A-4, A-5):** Should the Host be able to edit Draft Content before publishing? If yes, should edited Content be visually distinguished from purely AI-generated Published Content? *Decision needed before UX design of the Review screen.*

2. **Session start without Published Content (FR-10):** FR-10 disables "Start session" if no Published Content exists. Should a Host be able to start a session with only a Rulebook — i.e., use to-board as a PDF viewer + session logger before Generation? *Consider if it blocks early adoption of the tool.*

3. **Room URL human-readability (FR-11, A-7, UJ-2):** The assumed format `/room/{game-slug}-{short-id}` needs validation — is the short-ID truly pronounceable as a fallback? Alternative: numeric PIN (e.g. `/room/4821`).

4. **Play Mode in v1 (§7.1):** v1 Play Mode is screen stay-awake + minimised chrome only. Tap-to-advance is deferred. Is this meaningful enough to ship in v1, or should Play Mode wait for v1.1 when it is more complete?

5. **Host authentication mechanism (A-12):** Single-user password auth is assumed. Should this be configurable (e.g., skip auth entirely on a trusted LAN)? *Decision affects setup complexity.*

6. **PDF replacement and Content invalidation (FR-2):** When a Rulebook is replaced, the current assumption preserves Published Content until the Host explicitly regenerates. Should replacing the Rulebook always invalidate Published Content instead?

7. **Real-time Session end notification (FR-14, A-15):** Notifying connected Guests that a Session has ended without a page refresh requires a server-push mechanism. Options: SSE (simpler, unidirectional), WebSocket (bidirectional, more overhead), or polling (simplest, slight delay). *Decision affects backend architecture.*

8. **One learning loop, two surfaces (§5.4, SM-C1):** Session history (FR-15–18) and Content quality reviews (FR-7) are two surfaces of the same feedback loop — more session data improves adaptive quick-start (future); more content reviews improve AI quality (present). The architecture should model these as one mechanism from the start so the data schema aligns. This is not a v1 feature decision, but a schema decision the architect should make deliberately. See brief addendum §Key Design Synthesis.

---

## 9. Platform

- **Host interface:** web browser on desktop or laptop (primary); tablet acceptable. No native app.
- **Guest interface:** mobile browser on iOS (Safari) and Android (Chrome). No install, no account. Minimum viewport: 375 px wide (iPhone SE).
- **Deployment:** Docker Compose on TrueNAS SCALE (Linux, x86-64). LAN-served via HTTP; HTTPS optional via reverse proxy (outside scope of v1 setup). [ASSUMPTION: Host accesses the app by NAS IP or hostname on the LAN; no domain name or TLS required for v1.]
- **PDF rendering:** in-browser via [ASSUMPTION: PDF.js]; no reliance on the browser's native PDF plugin, so that viewer controls (zoom, page jump, Wake Lock) are implemented consistently.

---

## 10. Non-Functional Requirements

#### NFR-1: Page load performance

Any page in the app, served on a LAN connection, loads and becomes interactive within **3 seconds** under normal use (up to 8 connected Guests).

#### NFR-2: PDF viewer initial render

The Rulebook PDF viewer renders the first page within **2 seconds** of navigation on a LAN connection for PDFs up to 50 MB.

#### NFR-3: Concurrent Guest capacity

The app supports up to **8 simultaneously connected Guests** in a Room without degradation of NFR-1.

#### NFR-4: Data durability

All persistent data (Rulebook PDFs, extracted text cache, Content at any Pipeline State, Session records) survives Docker container restarts and TrueNAS SCALE OS updates without data loss. Achieved via dataset-mapped volumes (see FR-18).

#### NFR-5: Resource ceiling

The running stack consumes fewer than **2 GB RAM at idle** and fewer than **4 GB RAM under active Session load** (8 Guests connected). CPU usage at idle is negligible (< 5% of a single core).

#### NFR-6: Single-stack deployment

The app is packaged as a single Docker Compose file with all runtime dependencies bundled. No external runtime dependencies are required beyond what is declared in the Compose file.

#### NFR-7: Privacy at runtime

- No Guest data is collected, logged, or transmitted. Guests are anonymous readers; the app captures no IP addresses, device identifiers, or usage events for Guest sessions.
- At runtime (game nights), the app makes no calls to any external service. All Content is served from NAS-local storage.
- The cloud LLM API is called only at Generation time, triggered explicitly by the Host. The payload is extracted Rulebook text only — no personal data, no usage metrics.
- The API Key is stored on the NAS and transmitted only to the configured LLM provider endpoint during Generation. It is never embedded in client-side code or exposed to Guests.

---

## 11. Success Metrics

**Primary**

- **SM-1: v1 completes a real game night end-to-end** — at least one Session is started, Guests join via QR Code, the Cheat Sheet is referenced at the table, and the Session is logged with players and outcome. Validates FR-10, FR-11, FR-12, FR-13, FR-15, FR-16. *Target: achieved once.*

- **SM-2: Content pipeline reliability** — the majority of Games in the collection reach Published state on first or second generation attempt. Validates FR-5, FR-6, FR-7. *Target: ≥ 3 of the first 5 games added reach Published state within two generation passes.*

**Secondary**

- **SM-3: Guests join without asking for help** — no Guest requires verbal instructions to navigate from QR Code scan to Room page. Validates FR-11, FR-12. *Target: observed in first real game night.*

- **SM-4: Host does not consult external rulebooks during play** — the Host does not reach for a phone or open another browser tab to resolve a rules question once a Session is active. Validates FR-8, FR-13. *Target: observed in first real game night.*

- **SM-5: LAN performance target met** — all Room page loads complete in < 3 seconds under a 4-Guest load. Validates NFR-1, NFR-3. *Target: verified in pre-launch test.*

**Counter-metric (do not optimise)**

- **SM-C1: App management time does not exceed play time** — the Host does not spend more total time managing to-board (adding games, reviewing content, logging sessions) than the time saved at game nights. Counterbalances SM-1 and SM-2. If the content review pipeline requires multiple rejection cycles per game, the value proposition erodes.

---

## 12. Assumptions Index

| # | Location | Assumption | Status |
|---|---|---|---|
| A-1 | FR-2 | Rulebook upload size limit is 100 MB | Unvalidated — confirm against largest known rulebook PDFs |
| A-2 | FR-3 | Wake Lock API used for screen stay-awake; degrades gracefully on unsupported browsers | Unvalidated — verify browser support matrix |
| A-3 | FR-6 | Minimum viable extraction threshold is 500 tokens; below this, a warning is shown | Unvalidated — confirm with PDF extraction library |
| A-4 | FR-7 | Only one Published version of Content per Game at a time; new publish replaces previous | Design decision — confirm in §8 Q1 |
| A-5 | FR-7 | Host can edit Draft Content inline before publishing | Design decision — confirm in §8 Q1 |
| A-6 | FR-9 | At least one of Anthropic or Google provider supported at v1; provider selection configurable | Technical decision |
| A-7 | FR-11 | Room URL format: `/room/{game-slug}-{short-id}`; human-readable fallback | Design decision — confirm in §8 Q3 |
| A-8 | FR-12 | App operates on private LAN; no GDPR/cookie consent obligations | Legal assumption — confirm if app will ever be network-accessible beyond LAN |
| A-9 | FR-16 | Maximum 12 players per Session | Unvalidated — confirm against typical game night size |
| A-10 | FR-17 | Session Log filtering is by game only; no full-text search in v1 | Scope decision |
| A-11 | §6 | No reverse-proxy or Tailscale required for v1 | Deployment decision |
| A-12 | §8 Q5 | Host auth: simple password; no OAuth | Design decision — confirm in §8 Q5 |
| A-13 | §9 | PDF rendering via PDF.js | Technical decision |
| A-14 | UJ-2 | Room URL is short and pronounceable for fallback typing | Linked to A-7 |
| A-15 | FR-14 | Real-time Session-end notification requires SSE or WebSocket (not polling) | Technical decision — see §8 Q7 |
