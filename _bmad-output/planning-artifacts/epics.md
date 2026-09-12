---
stepsCompleted: [1, 2]
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-to-board-2026-09-03/prd.md
  - _bmad-output/planning-artifacts/architecture/architecture-to-board-2026-09-07/ARCHITECTURE-SPINE.md
  - _bmad-output/planning-artifacts/ux-designs/ux-to-board-2026-09-04/DESIGN.md
  - _bmad-output/planning-artifacts/ux-designs/ux-to-board-2026-09-04/EXPERIENCE.md
---

# to-board planning breakdown

## Overview

This document provides the complete epic and story breakdown for to-board, decomposing the requirements from the PRD, UX Design, and Architecture into implementable stories.

## Requirements Inventory

### Functional Requirements

- FR-1: Host creates a Game entry with a title, unique ID, timestamp, immediate Collection visibility, and optional cover image.
- FR-2: Host uploads a Rulebook PDF; it is persisted on the NAS, extracted in the background, replaced safely on re-upload, and constrained by the upload limit.
- FR-3: Host views a Rulebook in an in-app PDF.js viewer with zoom, page navigation, page entry, and table-of-contents navigation; Play Mode wake lock is supported where available; Guests cannot access the PDF.
- FR-4: Host deletes a Game with explicit confirmation; associated files and Content are removed while past Sessions retain a title snapshot.
- FR-5: Host triggers Content generation only when API key and extraction prerequisites are satisfied; generation creates one Quick-start Guide and one Cheat Sheet and warns before replacing an existing Draft.
- FR-6: System extracts Rulebook text locally before any cloud call, caches it, warns on low extraction quality, and permits Host override.
- FR-7: Host reviews Draft Content and publishes or rejects it as a pair; rejected content can be regenerated; Draft content is read-only in the UI.
- FR-8: Published Content is served from local NAS storage with no runtime cloud calls and disables session start when no Published Content exists.
- FR-9: Host configures and updates an LLM API key and provider; the key is local, encrypted, never exposed in responses or frontend code, and provider errors are surfaced.
- FR-10: Host starts a Session only for a Game with Published Content; a Session, unique Room URL, and QR presentation are created immediately.
- FR-11: Each Session has one unique, scannable, short and human-readable QR Room URL.
- FR-12: Guests access an active Room without authentication, installation, prompts, or persisted identity data; ended Rooms show a closed state.
- FR-13: Room displays Published Quick-start and Cheat Sheet content in a mobile layout usable at 375px without horizontal scrolling.
- FR-14: Host ends a Session; the record is timestamped, the Room closes, the QR becomes inactive, and connected Guests receive the closure without refresh.
- FR-15: Session records are created automatically at Session start with game snapshot, game reference, and start timestamp, and persist immediately.
- FR-16: Host edits free-text player names and outcome, including after Session end.
- FR-17: Host views reverse-chronological Session history with game filtering and preserved titles for deleted Games.
- FR-18: Session data survives container restarts and TrueNAS SCALE updates through persistent dataset storage.
- FR-19: Host opens the PDF viewer and Play Mode from Game Detail without an active Session.
- FR-20: Host views Published Content from Game Detail without an active Session and without creating a Room or Session.

### NonFunctional Requirements

- NFR-1: LAN pages become interactive within 3 seconds with up to 8 connected Guests.
- NFR-2: PDF.js renders the first page within 2 seconds for PDFs up to 50 MB on LAN.
- NFR-3: The application supports 8 simultaneously connected Guests without degradation of NFR-1.
- NFR-4: PDFs, extracted text, Content, and Sessions survive container restarts and TrueNAS SCALE updates.
- NFR-5: Runtime resource use remains below 2 GB RAM idle, 4 GB under active 8-Guest load, and 5% of one core idle.
- NFR-6: Deployment is one Docker Compose stack with bundled runtime dependencies and no undeclared external runtime dependency.
- NFR-7: Guests are anonymous; no Guest data is collected, logged, transmitted, or persisted, runtime serving is local-only, cloud generation is Host-triggered only, and API keys remain private.

### Additional Requirements

- AD-1: Use a layered monolith: Python 3.12 FastAPI backend, compiled Svelte SPA frontend, nginx static serving and API reverse proxy; no runtime Node process; exactly `backend/` and `frontend/` top-level application directories.
- AD-2: Store all structured data in one SQLite file through SQLModel at `/data/db/to-board.db`; do not add another database engine or raw sqlite3 access.
- AD-3: Persist only through the named TrueNAS dataset bind mounts `to-board-db` at `/data/db/` and `to-board-uploads` at `/data/uploads/`; no Docker-managed persistent volumes.
- AD-4: Store Content as Markdown in SQLite (`draft_*` and `published_*` columns); render through one sanitized shared frontend Markdown component.
- AD-5: Enforce the server-side Content pipeline state machine in `services/content.py`, including HTTP 409 invalid transitions, one Content row per Game, preserved Published Content during regeneration, and no frontend-owned state mutation.
- AD-6: Run extraction in a thread pool and generation as an async in-process task; persist extracted text paths; record `prior_pipeline_state`; recover stuck jobs on startup.
- AD-7: Use SSE only for Guest Session-end notification; use Host polling at no more than 5 seconds for extraction and generation state.
- AD-8: Protect Host routes with Authentik OIDC/JWKS and leave Guest Room routes open; encrypt API keys once with Fernet and `SECRET_KEY`; never log Guest identity or expose secrets.
- AD-9: Enforce one active Rulebook per Game and replace its files and row transactionally on re-upload.
- Use domain nouns `Game`, `Rulebook`, `Content`, `PipelineState`, `Session`, and `Room`; UUID v4 identifiers; slugification in one shared utility; ISO 8601 UTC API timestamps; standard FastAPI error shapes.
- Implement the prescribed API route boundaries, service-layer state mutation, environment-based runtime configuration, and two-container Compose topology.
- Preserve deferred scope: no Play Mode tap-to-advance, v1.1 deep links, private phone view, quality voting, session photos, scorecards, adaptive quick-start, AI card lookup, or cloud/multi-device access.

### UX Design Requirements

- UX-DR1: Implement the Aura dark token system, semantic colors, DM Sans/DM Mono typography, 4px spacing scale, rounded shape scale, and 1px border rules from DESIGN.md.
- UX-DR2: Build responsive Host layout with a 240px/60px sidebar, 32px minimum content padding, centered 1400px max content width, and responsive collection grid.
- UX-DR3: Build Game Cards with 2:3 cover art, responsive overlay behavior, initials fallback, one text-bearing pipeline badge, keyboard focus, and one-line title truncation.
- UX-DR4: Build semantic Status Badges for every pipeline state, always pairing color with text and using live status semantics where updates occur.
- UX-DR5: Build the Host sidebar with persistent localStorage collapse preference, Cmd/Ctrl+B toggle, icon labels/tooltips, mobile drawer behavior under 768px, backdrop dismissal, and complete keyboard access.
- UX-DR6: Implement Collection, Game Detail, Content Review, Host Preview, PDF Viewer, QR Reveal, Session Log, Session Detail, and Settings routes with the specified navigation relationships.
- UX-DR7: Implement Content Review as read-only two-panel/stacked Markdown display with sticky Reject/Publish actions and destructive Reject confirmation.
- UX-DR8: Implement a browser-consistent PDF.js viewer with zoom, previous/next, page input, optional table-of-contents drawer, and no native PDF plugin dependency.
- UX-DR9: Implement QR Reveal as a full-screen, 300ms reduced-motion-aware fade with hidden sidebar, blurred cover background, 280px QR code, title, copyable monospace URL, exit control, dialog semantics, and accessible QR alt text.
- UX-DR10: Implement the Guest Room as a chrome-free, max-640px, mobile-first page with game title, minimal wordmark, sticky Quick-start/Cheat Sheet tabs, instant section switching, and no horizontal scroll at 375px.
- UX-DR11: Implement the Room ended state as a centered notice and announce the SSE-driven content replacement through an `aria-live="polite"` region.
- UX-DR12: Apply the prescribed calm microcopy and state labels; do not add exclamation marks, emoji, marketing copy, navigation badges, or Guest-facing prompts.
- UX-DR13: Implement keyboard tab order, visible 2px focus rings, Escape behavior, 44px touch targets, alt text, ARIA labels/expanded state/status/dialog roles, and reduced motion behavior.
- UX-DR14: Implement native PDF file selection only (`accept=".pdf"`), no drag-and-drop, progressive skeleton/inline loading states, and destructive-action confirmations only.
- UX-DR15: Implement Room URL copy feedback changing from Copy to Copied for 1.5 seconds.

### FR Coverage Map

- FR-1: Epic 1 — Create Game entries
- FR-2: Epic 1 — Upload and replace Rulebooks
- FR-3: Epic 1 — Browse Rulebooks in PDF.js
- FR-4: Epic 1 — Delete Games safely
- FR-5: Epic 2 — Trigger Content generation
- FR-6: Epic 2 — Extract Rulebook text locally
- FR-7: Epic 2 — Review, reject, and publish Draft Content
- FR-8: Epic 2 — Serve Published Content locally
- FR-9: Epic 2 — Configure the cloud API key
- FR-10: Epic 3 — Start Sessions
- FR-11: Epic 3 — Generate unique QR Rooms
- FR-12: Epic 3 — Support anonymous Guest access
- FR-13: Epic 3 — Display mobile Room content
- FR-14: Epic 3 — End Sessions and notify Guests
- FR-15: Epic 4 — Persist Sessions at start
- FR-16: Epic 4 — Record players and outcomes
- FR-17: Epic 4 — Browse and filter Session history
- FR-18: Epic 4 — Preserve Session data across restarts
- FR-19: Epic 1 — Access Rulebooks without Sessions
- FR-20: Epic 2 — Preview Published Content without Sessions

## Workstreams

### Epic 1: Build and Manage the Game Library
The Host can create, browse, update, view, and remove Games and their authoritative Rulebooks, including accessing the PDF independently of any Session.
**FRs covered:** FR-1, FR-2, FR-3, FR-4, FR-19

### Epic 2: Prepare Trusted Game Content
The Host can configure the LLM provider, extract Rulebook text locally, generate Draft Content, review it, reject or regenerate it, publish approved content, and preview Published Content without a Session.
**FRs covered:** FR-5, FR-6, FR-7, FR-8, FR-9, FR-20

### Epic 3: Run a Game Night with Guest Rooms
The Host can start a Session for a ready Game, display a scannable QR Room, and end the Session. Guests can anonymously access a mobile-optimized Room with local Published Content and receive the ended-state notice in real time.
**FRs covered:** FR-10, FR-11, FR-12, FR-13, FR-14

### Epic 4: Preserve and Review Game-Night History
The Host can rely on automatic Session persistence, add players and outcomes, browse historical Sessions, filter by Game, and retain useful records even when a Game is deleted.
**FRs covered:** FR-15, FR-16, FR-17, FR-18

<!-- Repeat for each epic in epics_list (N = 1, 2, 3...) -->

## Epic 1: Build and Manage the Game Library

The Host can create, browse, update, view, and remove Games and their authoritative Rulebooks, including accessing the PDF independently of any Session.

**FRs covered:** FR-1, FR-2, FR-3, FR-4, FR-19

### Story 1.1: Create and Browse Game Entries

As the Host,
I want to create a Game with a title and optional cover image,
So that it appears in my collection and can become the foundation for Rulebook and Content preparation.

**Acceptance Criteria:**

**Given** I am authenticated and viewing the Collection  
**When** I choose “Add game,” enter a valid title, and save  
**Then** a Game is created with a UUID, the supplied title, and an ISO 8601 UTC creation timestamp  
**And** the new Game appears in the Collection immediately.

**Given** I submit a title containing leading or trailing whitespace  
**When** the Game is saved  
**Then** the title is normalized according to the application’s validation rules  
**And** an empty result is rejected with the standard `422` validation response.

**Given** I create a Game without a cover image  
**When** the Game is saved  
**Then** creation succeeds  
**And** the Game Card displays the accessible initials placeholder on the prescribed raised surface.

**Given** I provide an optional JPEG, PNG, or WebP cover image no larger than 10 MB  
**When** I save the Game  
**Then** the image is stored under the configured persistent uploads dataset  
**And** the Game Card displays it inside a consistent 2:3 portrait frame using cover fitting  
**And** the image has alt text equal to the Game title.

**Given** I provide an unsupported, corrupted, or oversized cover image  
**When** I save the Game  
**Then** the request is rejected with a clear `422` validation error  
**And** no invalid file is persisted.

**Given** I am unauthenticated  
**When** I call the Game creation or Collection endpoint  
**Then** the request is rejected or redirected through the Authentik Host authentication boundary  
**And** no Guest route provides access to Game management.

**Given** the Collection contains Games  
**When** I open the Collection at supported Host viewport sizes  
**Then** Games appear in the responsive poster grid  
**And** each card shows the title and a text-bearing status indicator without relying on color alone  
**And** keyboard users can focus a card and activate it with Enter or Space.

### Story 1.2: Upload and Replace a Game Rulebook

As the Host,
I want to upload or replace a Game’s Rulebook PDF,
So that the authoritative rules are stored durably and can be prepared for Content generation.

**Acceptance Criteria:**

**Given** I am authenticated on a Game Detail screen  
**When** I select a PDF from my device through the native file picker and submit it  
**Then** the PDF is stored under the configured TrueNAS uploads dataset  
**And** the Game has exactly one active Rulebook  
**And** extraction begins asynchronously without blocking the request.

**Given** the selected file is not a valid PDF or exceeds the 100 MB upload limit  
**When** I submit the upload  
**Then** the request is rejected with a clear `422` validation error  
**And** no invalid or partial file is persisted.

**Given** the Game already has a Rulebook  
**When** I upload a replacement PDF  
**Then** the previous PDF and extracted-text file are removed  
**And** the new Rulebook row and file references replace them in one database transaction  
**And** the existing Published Content remains available until the Host explicitly regenerates it  
**And** existing Draft or Rejected Content is invalidated according to the pipeline rules.

**Given** extraction is in progress  
**When** I view the Collection or Game Detail screen  
**Then** the current state is shown as “Preparing…” with a non-blocking loading indicator  
**And** the Host can navigate elsewhere in the application.

**Given** extraction completes successfully  
**When** the worker persists the extracted text  
**Then** it writes the absolute extracted-text path to the Rulebook record before the Content state becomes ready for generation  
**And** later generation reads the text from that persisted path rather than reconstructing a path.

**Given** the upload request is unauthenticated  
**When** it is submitted  
**Then** it is rejected or redirected through the Authentik Host authentication boundary  
**And** no Guest route can upload or replace a Rulebook.

**Given** I use the Rulebook upload control  
**When** the native file picker opens  
**Then** it accepts local PDF files only  
**And** the v1 flow does not download Rulebooks from web URLs.

### Story 1.3: View a Rulebook Independently

As the Host,
I want to open and read a Game’s Rulebook without starting a Session,
So that I can consult the authoritative rules whenever needed.

**Acceptance Criteria:**

**Given** a Game has an uploaded Rulebook  
**When** I select “View rulebook” from Game Detail  
**Then** the Rulebook opens at `/games/:id/pdf` in the in-app PDF.js viewer  
**And** no Session is created or required.

**Given** the PDF viewer is open  
**When** I use its controls  
**Then** I can zoom in and out  
**And** move to the previous or next page  
**And** enter a page number directly  
**And** open the PDF table of contents when one is available.

**Given** the viewer loads a PDF of up to 50 MB on the LAN  
**When** I navigate to the viewer  
**Then** the first page renders within the NFR-2 target  
**And** rendering does not rely on the browser’s native PDF plugin.

**Given** the Host navigates to the PDF viewer  
**When** the viewer is displayed  
**Then** the Host navigation is reduced according to the PDF Viewer UX behavior  
**And** the layout remains usable at supported desktop, tablet, and mobile widths.

**Given** a Game has no uploaded Rulebook  
**When** I attempt to open its Rulebook viewer  
**Then** the action is unavailable or returns a clear `404` resource error  
**And** no viewer is opened with misleading empty content.

**Given** I am unauthenticated or accessing as a Guest  
**When** I request a Rulebook viewer route or PDF resource  
**Then** the request is rejected or redirected through the Host authentication boundary  
**And** Guest Room routes never expose the PDF.

**Given** the browser does not support the optional Wake Lock API  
**When** I use the Host’s Rulebook reading mode  
**Then** the viewer remains usable  
**And** the interface gives a visible, calm notice that screen wake-lock is unavailable.

### Story 1.4: Delete a Game Safely

As the Host,
I want to delete a Game and its current assets,
So that my collection stays accurate without losing historical Session context.

**Acceptance Criteria:**

**Given** I am authenticated on a Game Detail screen  
**When** I choose “Delete game”  
**Then** a destructive confirmation dialog explains that the action is irreversible  
**And** the dialog offers explicit confirm and cancel actions.

**Given** I cancel the deletion confirmation  
**When** the dialog closes  
**Then** the Game, Rulebook, Content, and associated files remain unchanged.

**Given** I confirm deletion  
**When** the deletion completes  
**Then** the Game record is removed  
**And** its Rulebook PDF, extracted-text cache, cover image, and all Content states are removed from persistent storage  
**And** the Collection no longer displays the Game.

**Given** the Game has historical Sessions  
**When** I confirm deletion  
**Then** those Session records remain available  
**And** each retains the Game title snapshot and does not fail because the Game record is gone.

**Given** a deletion encounters a storage or database failure  
**When** the operation fails  
**Then** the failure is surfaced clearly  
**And** the system does not report success while leaving an inconsistent partial deletion.

**Given** I am unauthenticated or accessing as a Guest  
**When** I request Game deletion  
**Then** the request is rejected or redirected through the Host authentication boundary  
**And** Guest routes provide no deletion capability.

### Story 1.5: Implement the Host Collection and Game Detail Experience

As the Host,
I want a clear, responsive Collection and Game Detail experience,
So that I can manage Games and reach their Rulebooks and Content preparation actions efficiently.

**Acceptance Criteria:**

**Given** I am authenticated  
**When** I open the application  
**Then** the Collection is the default Host route  
**And** the Host sidebar provides Collection, Session Log, and Settings navigation.

**Given** I view the Collection on supported viewport widths  
**When** the page renders  
**Then** the sidebar uses the prescribed expanded, collapsed, or mobile drawer behavior  
**And** the Game grid uses responsive columns with a minimum card width of 160px  
**And** first-load data uses progressive skeleton loading rather than a full-screen loading state.

**Given** I view a Game Card  
**When** the card is idle, hovered, focused, or rendered on a touch device  
**Then** cover art, title, placeholder behavior, overlay, status badge, and focus treatment follow the UX contract  
**And** the card remains keyboard accessible.

**Given** I am on Game Detail  
**When** I inspect the Game  
**Then** I can see its current pipeline status and reach the available Rulebook, Content, preview, upload, and deletion actions  
**And** actions are enabled or disabled with calm, specific explanations based on current state.

**Given** I use the sidebar  
**When** I click its toggle, press Cmd/Ctrl+B, or use a mobile backdrop  
**Then** the sidebar transitions or closes according to the responsive UX rules  
**And** its collapse preference is persisted in `localStorage`.

**Given** any interactive Host control receives keyboard focus  
**When** it is focused  
**Then** it has a visible 2px offset primary-color focus ring  
**And** touch targets on mobile are at least 44×44px  
**And** navigation order follows the DOM reading order.

**Given** the application displays state or errors  
**When** a user action completes or fails  
**Then** messaging uses the prescribed calm microcopy without exclamation marks, emoji, or marketing language  
**And** state is communicated with text as well as color.

## Epic 2: Prepare Trusted Game Content

The Host can configure the LLM provider, extract Rulebook text locally, generate Draft Content, review it, reject or regenerate it, publish approved content, and preview Published Content without a Session.

**FRs covered:** FR-5, FR-6, FR-7, FR-8, FR-9, FR-20

**Relevant architecture constraints:** server-owned Content state machine, one Content row per Game, local Markdown persistence, in-process async generation, extracted-text path authority, startup stuck-job recovery, Fernet encryption, Authentik-protected Host routes, and no cloud calls during runtime Room or preview access.

**Relevant UX requirements:** Settings, Game Detail status and action states, Content Review read-only two-panel/stacked layout, shared sanitized Markdown rendering, sticky Publish/Reject actions, calm error copy, inline loading states, and accessible status updates.

### Story 2.1: Configure and Protect the LLM Provider

As the Host,
I want to configure the LLM provider and API key,
So that I can enable Content generation without exposing credentials.

**Acceptance Criteria:**

**Given** I am authenticated on Settings  
**When** I submit a supported provider and API key  
**Then** the key is encrypted with the single Fernet implementation using `SECRET_KEY` before it is stored in SQLite  
**And** Settings shows only a non-secret configured state.

**Given** an API key is stored  
**When** any API or frontend request returns Settings data  
**Then** the plaintext or encrypted key is never included in the response or compiled frontend bundle.

**Given** I update or replace the API key  
**When** the update succeeds  
**Then** existing Draft, Rejected, and Published Content remains unchanged  
**And** future generation uses the new configuration.

**Given** the provider rejects the key during a generation attempt  
**When** the provider error is returned  
**Then** the Host sees a clear provider-specific error  
**And** existing Published Content for every Game remains available.

**Given** I am unauthenticated or accessing as a Guest  
**When** I request or mutate Settings  
**Then** the request is rejected or redirected through Authentik  
**And** Guest routes expose no provider or key information.

### Story 2.2: Extract Rulebook Text Locally

As the Host,
I want Rulebook text extracted and cached locally,
So that generation can use the authoritative PDF without transmitting the PDF itself to a cloud provider.

**Acceptance Criteria:**

**Given** a valid Rulebook upload has completed  
**When** the extraction worker runs  
**Then** it extracts text locally using the configured PDF extraction library  
**And** no raw PDF bytes are sent outside the home network  
**And** the extracted text is written under the persistent uploads dataset.

**Given** extraction completes successfully  
**When** the worker persists its result  
**Then** the absolute extracted-text path is stored on the Rulebook record  
**And** the Content pipeline transitions from `extracting` to `ready_to_generate` through the Content service  
**And** the path is available for subsequent generation.

**Given** extraction yields fewer than the configured minimum viable token threshold  
**When** the result is evaluated  
**Then** the Host sees a clear warning that the Rulebook may not have extracted cleanly  
**And** the Host can explicitly override the warning before generation.

**Given** extraction fails  
**When** the worker reports the failure  
**Then** the Content pipeline returns to `no_rulebook` according to the server-side transition rules  
**And** the failure is surfaced to the Host  
**And** no incomplete extracted-text path is treated as ready.

**Given** the API process restarts while extraction is in progress  
**When** startup recovery runs  
**Then** a Content row in `extracting` is reset to its recorded `prior_pipeline_state`  
**And** the Host can retry without a fabricated predecessor assumption.

**Given** a Rulebook is re-uploaded  
**When** the replacement succeeds  
**Then** the old extracted-text cache is removed  
**And** only the replacement Rulebook’s extracted path can be used for future generation.

### Story 2.3: Generate Draft Content from a Rulebook

As the Host,
I want to generate a Quick-start Guide and Cheat Sheet from extracted Rulebook text,
So that I can review useful game-night content before showing it to Guests.

**Acceptance Criteria:**

**Given** a Game has a Rulebook with completed extraction and a configured API key  
**When** I choose “Generate content” and confirm the cloud API call  
**Then** the server transitions Content to `generating` through the Content service  
**And** an asynchronous in-process generation task starts  
**And** the request returns without blocking on the cloud response.

**Given** Content is already in `draft` or `published` state  
**When** I request a new generation  
**Then** the Host receives a clear warning that the Draft will be replaced  
**And** the existing Published Content remains available while the new Draft is being generated.

**Given** generation starts  
**When** the LLM request is built  
**Then** it reads extracted text exclusively from `Rulebook.extracted_text_path`  
**And** only extracted Rulebook text is sent to the configured provider  
**And** the API key is supplied server-side and never exposed to the frontend.

**Given** the provider returns valid generated output  
**When** the generation task persists the result  
**Then** exactly one Content row for the Game contains both Draft Quick-start Guide and Draft Cheat Sheet Markdown  
**And** the pipeline transitions to `draft`  
**And** the Host can see a “Needs review” state.

**Given** the provider call fails or returns invalid output  
**When** the generation task handles the failure  
**Then** the pipeline transitions back to the recorded predecessor state  
**And** the Host sees a clear error  
**And** existing Published Content remains unchanged.

**Given** the API process restarts while generation is in progress  
**When** startup recovery runs  
**Then** the Content row is reset to its recorded `prior_pipeline_state`  
**And** the Host can explicitly trigger generation again.

**Given** a Game has no Rulebook, incomplete extraction, or no configured API key  
**When** I view Game Detail  
**Then** generation is disabled with a specific reason  
**And** the server rejects any direct trigger with a standard validation or conflict error.

### Story 2.4: Review, Reject, and Publish Draft Content

As the Host,
I want to review generated Draft Content and publish or reject it,
So that Guests only see content I have approved.

**Acceptance Criteria:**

**Given** a Game has Draft Quick-start Guide and Cheat Sheet content  
**When** I open the Content Review route  
**Then** both documents are rendered as sanitized Markdown  
**And** they appear side by side on desktop and stacked on narrower screens  
**And** the content is read-only in the Review screen.

**Given** I am reviewing a Draft  
**When** I choose “Publish”  
**Then** the paired Draft fields are copied to the Published fields atomically  
**And** the Draft fields are cleared  
**And** the Content pipeline transitions from `draft` to `published` through the Content service  
**And** the Game status becomes “Ready to play”.

**Given** I am reviewing a Draft  
**When** I choose “Reject” and confirm the destructive dialog  
**Then** both Draft fields are cleared  
**And** the Content pipeline transitions from `draft` to `rejected`  
**And** the Host can trigger a new generation.

**Given** I open the Reject action  
**When** the confirmation dialog is displayed  
**Then** it explains that rejection clears the Draft and permits regeneration  
**And** Cancel leaves the Draft and pipeline state unchanged.

**Given** a Game has Published Content and a new Draft is generated  
**When** I reject the new Draft  
**Then** the previously Published Content remains available  
**And** only the new Draft is cleared.

**Given** the Draft is incomplete or the pipeline state is not `draft`  
**When** I request Publish or Reject  
**Then** the server rejects the action with the standard validation or `409` conflict response  
**And** no partial content mutation occurs.

**Given** the Review screen updates asynchronously  
**When** the pipeline state changes  
**Then** the status is communicated with text and accessible live semantics  
**And** loading and errors remain inline rather than blocking the full application.

### Story 2.5: Preview Published Content Without a Session

As the Host,
I want to preview Published Content from Game Detail,
So that I can verify the Guest-facing reference without starting a Session.

**Acceptance Criteria:**

**Given** a Game has Published Quick-start Guide and Cheat Sheet content  
**When** I choose “Preview” from Game Detail  
**Then** the Host Preview route opens without creating a Session or Room  
**And** it displays the same published pair that an active Guest Room would receive.

**Given** I view Host Preview  
**When** the content is rendered  
**Then** it uses the shared sanitized Markdown renderer  
**And** the Quick-start Guide and Cheat Sheet use the prescribed content presentation  
**And** no edit, Publish, Reject, or generation control is presented as part of the read-only preview.

**Given** the Game has no Published Content  
**When** I open or request Host Preview  
**Then** the route shows a clear unavailable state or returns a standard `404` resource error  
**And** it does not display Draft or Rejected Content as if it were published.

**Given** the Host Preview loads  
**When** the application serves the content  
**Then** the response is read from local SQLite storage  
**And** no cloud provider call is made.

**Given** I am unauthenticated or accessing as a Guest  
**When** I request Host Preview  
**Then** the request is rejected or redirected through Authentik  
**And** Guest access is available only through an active Session Room route.

## Epic 3: Run a Game Night with Guest Rooms

The Host can start a Session for a ready Game, display a scannable QR Room, and end the Session. Guests can anonymously access a mobile-optimized Room with local Published Content and receive the ended-state notice in real time.

**FRs covered:** FR-10, FR-11, FR-12, FR-13, FR-14

**Relevant architecture constraints:** Host-only Session routes, open Guest Room routes, local Published Content serving, unique Room slug generation, one active Session per Game, SSE only for Session-end notifications, no Guest data persistence, and server-owned Session state changes.

**Relevant UX requirements:** QR Reveal full-screen treatment, Room mobile layout and tabs, no Guest chrome or prompts, accessible QR semantics, URL copy feedback, ended-state live announcement, responsive touch targets, and calm microcopy.

### Story 3.1: Start a Session for a Ready Game

As the Host,
I want to start a Session for a Game with Published Content,
So that Guests can join a live Room for game night.

**Acceptance Criteria:**

**Given** a Game has Published Content and no active Session  
**When** I choose “Start session”  
**Then** a Session is created with a UUID, game reference, title snapshot, and ISO 8601 UTC `started_at` timestamp  
**And** a unique Room slug is generated  
**And** the active Session is persisted immediately in the SQLite database on the configured TrueNAS dataset.

**Given** a Game has no Published Content  
**When** I view Game Detail  
**Then** “Start session” is disabled  
**And** the interface explains that Published Content is required.

**Given** a Game already has an active Session  
**When** I request another Session  
**Then** the action is disabled or rejected with HTTP `409`  
**And** the existing active Room remains unchanged.

**Given** I am unauthenticated or accessing as a Guest  
**When** I request Session creation  
**Then** the request is rejected or redirected through Authentik  
**And** Guest routes cannot create or mutate Sessions.

**Given** Session creation fails  
**When** the database or slug operation reports an error  
**Then** the failure is surfaced clearly  
**And** no success-shaped QR or Room state is shown for an unpersisted Session.

### Story 3.2: Reveal and Share a Session QR Room

As the Host,
I want to display a unique QR code and short Room URL,
So that Guests can join the Session with any phone camera or by typing the URL.

**Acceptance Criteria:**

**Given** an active Session has been created  
**When** the QR Reveal route opens  
**Then** it displays a scannable QR code encoding the active Room URL  
**And** the QR is rendered at the prescribed 280px size with an accessible alt description  
**And** the Game title and short human-readable Room URL are visible.

**Given** Guests scan the QR code using standard iOS or Android camera software  
**When** they follow the encoded URL on the LAN  
**Then** the active Room route opens without requiring an app install or account.

**Given** a Guest cannot scan the QR code  
**When** they type the displayed Room URL  
**Then** the same active Room resolves  
**And** the URL is short enough to read aloud and enter manually.

**Given** I click or tap the displayed Room URL  
**When** the copy action succeeds  
**Then** the URL is copied to the clipboard  
**And** the control changes from “Copy” to “Copied” for 1.5 seconds.

**Given** I view QR Reveal  
**When** the surface enters or exits  
**Then** it uses the prescribed full-screen cover-art backdrop, single primary glow, and 300ms fade  
**And** the sidebar and Host navigation are hidden  
**And** reduced-motion preferences remove the transition.

**Given** the Session is active  
**When** I exit QR Reveal and later return to it  
**Then** the same Room URL and QR code remain valid  
**And** exiting does not end the Session.

**Given** the Session is not successfully persisted  
**When** QR Reveal would otherwise open  
**Then** it does not display an apparently valid QR code  
**And** the Host sees the creation failure instead.

### Story 3.3: Access the Guest Room Anonymously

As a Guest,
I want to open the active Room from a QR code or URL and optionally choose an alias,
So that I can consult the game reference and be identifiable to other people at the table without creating an account.

**Acceptance Criteria:**

**Given** a Session is active and has Published Content  
**When** I open its Room URL  
**Then** the Room loads without authentication, account creation, app installation, push-notification prompts, or cookie-consent banners  
**And** the Guest may enter an alias before viewing the Room  
**And** the response is served from the local application.

**Given** a Guest enters an alias  
**When** the alias is submitted  
**Then** the alias is visible to the Host and other Guests in the active Room  
**And** it is held only in memory for the active Room connection  
**And** it is not written to SQLite, browser storage, cookies, logs, analytics, or external services.

**Given** a Guest leaves or refreshes the Room  
**When** the prior connection ends  
**Then** its alias is removed from the active in-memory presence list  
**And** the Guest must enter it again if the Room requires a new connection.

**Given** I am viewing an active Room  
**When** the page renders  
**Then** it shows the Game title, Quick-start Guide, and Cheat Sheet  
**And** no Host sidebar, navigation, management action, or unrelated chrome is displayed.

**Given** multiple Guests open the same active Room  
**When** they browse the page  
**Then** each receives the same Published Content  
**And** the application supports up to 8 simultaneous Guests without collecting Guest identity.

**Given** a Guest accesses an unknown, malformed, or inactive Room slug  
**When** the request is handled  
**Then** the Guest receives a clear unavailable or ended Room state  
**And** no Draft, Rejected, or unpublished Content is exposed.

**Given** a Guest loads or uses the Room  
**When** the application handles the request  
**Then** it does not persist or log IP address, device information, usage events, or aliases  
**And** no external runtime service is contacted.

**Given** the Room loads on a LAN connection  
**When** the Guest opens it on a supported mobile browser  
**Then** it becomes interactive within the NFR-1 target  
**And** content remains usable without horizontal scrolling at a 375px viewport.

### Story 3.4: Use the Mobile Guest Room

As a Guest,
I want to switch between the Quick-start Guide and Cheat Sheet on my phone,
So that I can silently find the rule information I need during play.

**Acceptance Criteria:**

**Given** I have joined an active Room  
**When** the Room page renders  
**Then** it uses a centered single-column layout with a maximum width of 640px  
**And** it shows the Game title, minimal to-board wordmark, and no Host chrome.

**Given** the Room has Published Quick-start Guide and Cheat Sheet content  
**When** I select either sticky tab  
**Then** the selected section is shown immediately without navigation or pagination  
**And** the active tab uses the prescribed text and indicator treatment.

**Given** I read either content section on a 375px-wide viewport  
**When** the content contains long prose, lists, or headings  
**Then** it remains readable  
**And** no horizontal scrolling is required.

**Given** I use the Room on a touch device  
**When** I interact with tabs or other controls  
**Then** interactive targets meet the 44px minimum  
**And** the layout supports comfortable one-handed scrolling.

**Given** the Room renders Markdown content  
**When** content is inserted into the page  
**Then** the shared Markdown renderer sanitizes it before HTML rendering  
**And** unsafe markup cannot execute in the Guest browser.

**Given** the Room content is unavailable or incomplete  
**When** the page loads  
**Then** it shows a clear unavailable state  
**And** it never substitutes Draft or Rejected Content for Published Content.

### Story 3.5: End a Session and Notify Guests

As the Host,
I want to end an active Session,
So that the Room closes consistently and Guests know the game night is over.

**Acceptance Criteria:**

**Given** a Session is active  
**When** I choose “End session”  
**Then** a destructive confirmation dialog explains that the Room will close for all Guests  
**And** Cancel leaves the Session and Room unchanged.

**Given** I confirm ending the Session  
**When** the operation succeeds  
**Then** the Session receives an ISO 8601 UTC `ended_at` timestamp  
**And** the Room URL resolves to the ended state  
**And** new Room requests cannot access Published Content through that Session  
**And** the QR code is inactive.

**Given** Guests are connected to the active Room  
**When** the Host ends the Session  
**Then** the server sends an SSE `session-ended` event to each connected Guest  
**And** closes each SSE stream  
**And** the Guest page replaces the content without requiring a refresh.

**Given** a Guest receives the end event  
**When** the Room content is replaced  
**Then** the page announces “This session has ended.” through an `aria-live="polite"` region  
**And** it shows the Game title and minimal Guest-facing ended state  
**And** no Draft or Published content remains visible.

**Given** no Guest is connected when the Session ends  
**When** a Guest later opens the Room URL  
**Then** the ended state is shown immediately  
**And** no SSE connection is required to determine the closed state.

**Given** the end operation fails  
**When** the server reports the failure  
**Then** the Host sees a clear error  
**And** the Session is not presented as ended unless the persisted state confirms it.

## Epic 4: Preserve and Review Game-Night History

The Host can rely on automatic Session persistence, add players and outcomes, browse historical Sessions, filter by Game, and retain useful records even when a Game is deleted.

**FRs covered:** FR-15, FR-16, FR-17, FR-18

**Relevant architecture constraints:** SQLite/SQLModel Session storage, TrueNAS dataset durability, title snapshots for deleted Games, ISO 8601 UTC timestamps, Host-only Session management, and no Guest identity persistence.

**Relevant UX requirements:** Session Log and Session Detail routes, reverse-chronological presentation, calm status and empty-state copy, destructive End Session confirmation, accessible forms, responsive Host navigation, and preserved historical context.

### Story 4.1: Persist Session Records Reliably

As the Host,
I want each started Session to be persisted immediately,
So that my game-night history survives interruptions and infrastructure updates.

**Acceptance Criteria:**

**Given** the Host starts a valid Session  
**When** Session creation succeeds  
**Then** the record stores the Session UUID, Game reference, Game title snapshot, and ISO 8601 UTC `started_at` timestamp  
**And** it is written to the SQLite database under the configured TrueNAS dataset before success is returned.

**Given** the API container restarts after a Session has started  
**When** the application starts with the same dataset mounts  
**Then** the Session record is available with its original start data  
**And** an active Session remains identifiable as active.

**Given** the TrueNAS SCALE host or container stack is updated  
**When** the stack is restored with the same named dataset mounts  
**Then** Session records remain available  
**And** no Docker-managed volume is required for their persistence.

**Given** a Session references a Game that is later deleted  
**When** the Session is read  
**Then** its Game title snapshot remains available  
**And** the historical record does not require the deleted Game row to render.

**Given** persistence fails while starting a Session  
**When** the database reports an error  
**Then** Session creation fails explicitly  
**And** no QR Room or active Session state is presented for an unpersisted record.

### Story 4.2: Record Players and Outcomes

As the Host,
I want to add player names and multiple ordered outcomes to a Session,
So that a game night with repeated plays is recorded accurately.

**Acceptance Criteria:**

**Given** I am authenticated and viewing Session Detail  
**When** I enter player names and zero or more ordered outcome entries and save  
**Then** the Session record stores the values in persistent SQLite storage  
**And** the updated values are shown on Session Detail in their saved order.

**Given** I enter up to 12 free-text player names  
**When** I save the Session  
**Then** each name is retained as entered after normal validation  
**And** the system does not require player accounts or profile links.

**Given** I enter up to 20 ordered free-text outcome entries such as “Alex won” and “Jordan won”  
**When** I save the Session  
**Then** every entry is stored and displayed as Session metadata in order  
**And** entries can represent repeated plays without creating a new Session  
**And** zero outcome entries remains allowed.

**Given** the Session has ended  
**When** I edit players or add, remove, or reorder outcome entries  
**Then** the update succeeds without reopening the Session or Room  
**And** the historical Session remains in its ended state.

**Given** I submit invalid input, exceed the configured player limit, or add more than 20 outcome entries  
**When** the update is validated  
**Then** the server returns a clear `422` response  
**And** the previous persisted values remain unchanged.

**Given** I am unauthenticated or accessing as a Guest  
**When** I request or mutate Session metadata  
**Then** the request is rejected or redirected through Authentik  
**And** Guest Room access cannot edit players or outcomes.

### Story 4.3: Browse and Filter Session History

As the Host,
I want to browse past Sessions and filter them by Game,
So that I can review our game-night history.

**Acceptance Criteria:**

**Given** I am authenticated and open Session Log  
**When** the page loads  
**Then** Sessions are listed in reverse chronological order by start time  
**And** each entry shows Game title, date, player names when present, outcome entries when present, and active or ended state.

**Given** I choose a Game filter  
**When** the filter is applied  
**Then** only Sessions for that Game are shown  
**And** clearing the filter restores the complete reverse-chronological list.

**Given** a Session has multiple outcome entries  
**When** it appears in the Session Log or Session Detail  
**Then** the entries are displayed in their saved order  
**And** the history does not collapse them into one value or discard repeated plays.

**Given** a Game referenced by a historical Session has been deleted  
**When** I open Session Log  
**Then** the Session displays its preserved title snapshot  
**And** the entry remains filterable and readable without the deleted Game record.

**Given** no Sessions exist or the selected filter has no matches  
**When** I view Session Log  
**Then** the interface shows a calm, specific empty state  
**And** it does not present a broken table or misleading success state.

**Given** I am unauthenticated or accessing as a Guest  
**When** I request Session Log data  
**Then** the request is rejected or redirected through Authentik  
**And** Guest Room routes do not expose Host Session history.

### Story 4.4: Present a Durable Session History Experience

As the Host,
I want Session Log and Session Detail to remain usable across responsive layouts,
So that I can review and update game-night records from the supported Host devices.

**Acceptance Criteria:**

**Given** I open Session Log or Session Detail on a desktop, tablet, or mobile Host viewport  
**When** the page renders  
**Then** it uses the shared Host navigation and responsive layout rules  
**And** the primary Session information remains readable without unintended horizontal scrolling.

**Given** a Session row or detail action receives keyboard focus  
**When** I navigate with the keyboard  
**Then** focus order follows the DOM order  
**And** the focused control has the prescribed visible primary-color focus ring  
**And** actions have accessible names.

**Given** the Session Log or Detail is loading  
**When** data is being retrieved  
**Then** progressive skeleton or inline loading indicators are used  
**And** the application does not block the full screen with a loading overlay.

**Given** a Session update succeeds or fails  
**When** the result is shown  
**Then** the interface uses calm, specific microcopy  
**And** it does not use exclamation marks, emoji, or misleading success feedback.

**Given** the Session history contains active and ended Sessions  
**When** I inspect the list  
**Then** each state is communicated with text and accessible semantics  
**And** no state depends on color alone.
