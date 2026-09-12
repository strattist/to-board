---
name: to-board
status: final
created: 2026-09-04
updated: 2026-09-04
sources:
  - _bmad-output/planning-artifacts/briefs/brief-to-board-2026-09-03/brief.md
  - _bmad-output/planning-artifacts/prds/prd-to-board-2026-09-03/prd.md
---

# to-board — Experience Spine

## Foundation

**Host surface:** web browser on desktop or laptop (primary); tablet acceptable. No native app. Single authenticated user (Baptiste).

**Guest surface:** mobile browser — iOS Safari and Android Chrome. Minimum viewport 375px wide (iPhone SE baseline). No install, no account, no authentication.

**Auth:** Authentik OIDC SSO. to-board has no login screen. The Host arrives pre-authenticated via OIDC redirect from Authentik. Unauthenticated requests to Host routes redirect to the Authentik login page. Guest routes (`/room/:slug`) require no authentication.

**UI system:** none — custom components. `DESIGN.md` is the visual identity reference for all visual decisions. This spine specifies behavior only.

**Platform context:** Docker Compose on TrueNAS SCALE, served on the local network. Guests must be on the same LAN. No internet access required at runtime (only during AI content generation, which is a Host-only action).

**Play Mode:** deferred to v1.1. No Play Mode surfaces in v1.

---

## Information Architecture

### Host surfaces

| Surface | Route | Reached from | Purpose |
|---|---|---|---|
| Collection | `/` | Default landing | Jellyfin-style game poster grid — home |
| Game Detail | `/games/:id` | Card tap | Game overview, pipeline status, all actions |
| Content Review | `/games/:id/review` | Game Detail "Review" button | Read Draft content; Publish or Reject |
| Host Preview | `/games/:id/preview` | Game Detail "Preview" button | Read-only Published content (no session needed) |
| PDF Viewer | `/games/:id/pdf` | Game Detail "View rulebook" button | In-browser PDF reader |
| QR Reveal | `/session/:id` | Game Detail "Start session" | Full-screen cinematic QR display |
| Session Log | `/sessions` | Sidebar | Reverse-chronological session history |
| Session Detail | `/sessions/:id` | Session Log row | Add players, outcome; end active session |
| Settings | `/settings` | Sidebar | API key configuration, Authentik status |

### Guest surfaces

| Surface | Route | Reached from | Purpose |
|---|---|---|---|
| Room Page | `/room/:slug` | QR code scan | Published content — Quick-start + Cheat Sheet |
| Room Closed | `/room/:slug` (ended state) | Same URL after session ends | "This session has ended" notice |

→ Mockup references: `mockups/mock-collection.html` (Collection), `mockups/mock-qr-reveal.html` (QR Reveal), `mockups/mock-room-page.html` (Room Page), `mockups/mock-content-review.html` (Content Review). Spines win on conflict.

### Navigation structure

Persistent left sidebar (Host only) with three items: **Collection**, **Session Log**, **Settings**. Sidebar collapses to icon-only strip (60px) at user preference; preference persisted in `localStorage`. Toggle: click the chevron button at sidebar bottom, or `Cmd/Ctrl+B`.

At viewports under 768px, the sidebar becomes a slide-in drawer overlay rather than a persistent column.

The sidebar is **hidden entirely** during the QR Reveal — the full-screen surface owns the viewport.

---

## Voice and Tone

Calm and purposeful. The app supports the game; it does not narrate itself.

| Do | Don't |
|---|---|
| "Ready to play." | "Content published successfully!" |
| "Needs review." | "Your AI content is waiting for approval." |
| "Generating…" | "Hang tight while we cook up your content!" |
| "API key is missing — add one in Settings." | "Oops! Something went wrong." |
| "This session has ended." | "Looks like the host has wrapped things up!" |
| Short, complete sentences with no trailing filler. | Exclamation marks, emoji in system states, marketing language. |

Status labels are the status. "Ready to play" means the game has Published content and a session can start. "Needs review" means there is a Draft waiting. These labels appear in badges and in empty states — they are the single source of state truth, not supporting copy.

Guest Room page: no microcopy at all beyond content section headings ("Quick-start Guide", "Cheat Sheet") and the session-ended notice. The content is the page.

---

## Component Patterns

Behavioral. Visual specs — colors, radii, typography, elevation — live in `DESIGN.md.Components`.

### Game Card

The primary unit of the Collection. Tapping navigates to Game Detail.

- **Cover art:** fills the card container (2:3 aspect ratio). Cover art is Host-uploaded or placeholder (game initials on surface-raised).
- **Overlay:** gradient overlay from transparent to near-opaque at the bottom. On pointer devices: hidden at rest, appears on hover (200ms transition). On touch devices: always visible.
- **Title:** appears inside the overlay at the bottom-left. Truncated to one line with ellipsis if longer than card width.
- **Status badge:** bottom-left of the overlay, above the title. Always visible (not hidden on hover). One badge per card — the current pipeline state.
- **Keyboard:** focusable; `Enter` or `Space` navigates to Game Detail. Focus ring uses `{colors.primary}`.

### Status Badge

Pipeline state indicator. Always shown as color + text (never color alone).

| State | Label | Visual |
|---|---|---|
| No rulebook uploaded | "No content yet" | Muted text, no fill |
| Extracting text | "Preparing…" | Muted text, spinner icon |
| Ready to generate | "Ready to generate" | Muted text |
| Generating | "Generating…" | Muted text, spinner icon |
| Draft ready | "Needs review" | Amber badge |
| Published | "Ready to play" | Mint badge |
| Rejected | "Rejected" | Red badge |

### Sidebar

Persistent left navigation for Host surfaces. Collapsed: 60px wide, icons only (24×24px, centered, with tooltip on hover showing label). Expanded: 240px, icons (20×20px) + labels. Active item highlighted with surface-raised background and primary-color icon/label. Toggle is a chevron icon at the sidebar bottom; `Cmd/Ctrl+B` also toggles.

At `< 768px`: renders as a hamburger-triggered slide-in overlay drawer (full height, 240px wide, `background: {colors.surface}`). The rest of the viewport is covered by a translucent backdrop; tap outside to close.

Hidden (`display: none`, not just collapsed) during QR Reveal.

### Content Review

Two-panel read-only display of Draft content: Quick-start Guide (left or top) and Cheat Sheet (right or bottom), depending on viewport. On desktop: side-by-side columns separated by a 1px border. On tablet: stacked.

Content is rendered as styled prose — not a raw text area. The Host cannot edit inline (Option A decision). Content is read-only.

Action bar at the bottom of the screen (sticky): two buttons — **Reject** (danger/ghost style, left) and **Publish** (primary style, right). A confirmation dialog appears before Reject ("Reject this draft? You can regenerate after."). Publish has no additional confirmation — it is the primary intended action.

### PDF Viewer

Embedded PDF.js renderer. Full-width within the main content area. Controls: zoom in/out, page number input, previous/next page, table of contents drawer (if PDF has one). Rendered consistently across browsers — no reliance on the browser's native PDF plugin.

No sidebar chrome visible in the PDF Viewer; the sidebar collapses to icon-only automatically on navigation to `/games/:id/pdf`, restoring on exit.

### QR Reveal

Full-screen overlay. Sidebar hidden. No other nav chrome.

- **Background:** the game's cover art, rendered full-bleed and blurred (see `DESIGN.md.Components.qr-reveal` for visual spec). The image scales with `object-fit: cover` and `transform: scale(1.1)` to fill the viewport without bleed-edge artifacts from the blur.
- **Panel:** centered vertically and horizontally. Contains (top to bottom): QR code (280×280px), game title (`display` typography), Room URL (`mono` caption, copyable via tap/click).
- **Exit:** a single `×` ghost button, top-right of the viewport. Clicking exits the QR Reveal: sidebar reappears, route returns to Game Detail. Fades in with the rest of the overlay (300ms); never disappears during the session.
- **Session state:** the QR Reveal surface stays on this route for as long as the session is active. The Host can exit and return; the QR code remains valid.
- **Entry transition:** the QR Reveal fades in over 300ms on "Start session". No slide or push — a dissolve.

### Room Page (Guest)

Single-column, max-width 640px, centered. Mobile-first. No Host chrome of any kind.

- **Header:** game title (`heading-md`) and a subtle "to-board" wordmark in the top-right (caption weight, muted color — the only branding visible to Guests).
- **Tabs:** two sticky tabs: "Quick-start Guide" and "Cheat Sheet". Sticky below the header. Tab switching does not navigate; it reveals/hides content sections via `display` toggle (no animation needed — content is long and tabs should feel instant).
- **Content:** prose sections rendered from Published content. Quick-start Guide is narrative text (paragraphs). Cheat Sheet is structured content (lists, headers). Both are readable on a 375px viewport without horizontal scroll.
- **Session ended state:** if the session ends while a Guest is on the Room page, the server pushes a close event (SSE). The page replaces content with a centered notice: game title, "This session has ended.", and the to-board wordmark. No reload required.

---

## State Patterns

### Game pipeline

```
[No rulebook]
      ↓ Host uploads PDF
[Preparing…]      ← async text extraction, Host not blocked
      ↓ extraction complete
[Ready to generate]
      ↓ Host triggers generation (requires API key)
[Generating…]     ← async, cannot start session during this state
      ↓ generation complete
[Needs review]
      ↓ Host clicks Publish        ↓ Host clicks Reject
[Ready to play]               [Rejected]
      ↑ Host triggers regen          ↓ Host triggers regeneration
                              [Generating…] → [Needs review] → …

Note: Host can trigger regeneration from [Ready to play] too.
A new Draft is created; the existing Published content remains
served until the new Draft is explicitly published.
```

State is always reflected on the Game Card badge (Collection) and on the Game Detail screen header. It is never inferred — the app shows the current state at all times.

### Session

| State | Behavior |
|---|---|
| Active | QR code displayed. Room URL resolves to Published content. SSE connection open for Guest close events. |
| Ended | Room URL transitions to "session ended" state. Guests receive close event via SSE. QR code becomes inactive. Session record persists in log. |

Only one session can be active per game at a time. "Start session" is disabled if a session is already active for that game.

### API key

| State | Behavior |
|---|---|
| Present and valid | Generation enabled. No indicator shown in normal flow. |
| Missing | Generation button disabled on all Game Detail screens. Settings badge shows "Action required". |
| Invalid (provider returns error) | Generation shows inline error with the provider's error message. Settings surfaces the specific failure. |

---

## Interaction Primitives

- **Primary input:** click/tap. No drag-and-drop in v1 (game ordering, if needed, is deferred).
- **Keyboard:** full tab-order navigation. Interactive elements have visible focus rings (`{colors.primary}`, 2px, 2px offset). `Cmd/Ctrl+B` toggles sidebar. `Escape` closes modals and the QR Reveal exit is also reachable by `Escape`.
- **File upload:** native `<input type="file" accept=".pdf">`. No drag-target in v1.
- **Copy to clipboard:** Room URL in QR Reveal panel has a copy-on-click behavior. Feedback: button label changes from "Copy" to "Copied" for 1.5s.
- **Confirmation dialogs:** used for destructive actions only (Reject draft, Delete game, End session). Modal overlay, two buttons: confirm (danger) + cancel (ghost). No confirmations for non-destructive primary actions (Publish, Add game, Generate).
- **Loading states:** skeleton loaders for the Collection grid on first load. Inline spinners (16px) for async operations within a card or detail screen. Full-screen loading states are not used — the app loads progressively.
- **Banned interactions:** carousels, infinite scroll (the collection is finite), push notifications, badge counts on nav items, hero animations on page load.

---

## Responsive & Platform

### Host (Desktop / Tablet)

| Viewport | Sidebar | Collection grid | Notes |
|---|---|---|---|
| ≥ 1200px | Expanded (240px) default | 5–6 columns | Comfortable shelf |
| 900–1199px | Collapsed (60px) default | 4–5 columns | Sidebar auto-collapses |
| 768–899px | Collapsed (60px) | 3–4 columns | |
| < 768px | Drawer (hidden at rest) | 2–3 columns | Hamburger trigger |

The sidebar collapse state at load is: expanded if viewport ≥ 900px, collapsed otherwise. User overrides persist via `localStorage`.

### Guest (Mobile)

375px minimum. Single-column. No sidebar. Tab bar for content sections. The Room page must be fully usable with one hand — sticky tab bar and scrollable content sections below.

---

## Accessibility Floor

Behavioral. Visual contrast ratios live in `DESIGN.md.Colors`.

- **Color + text always together:** status badges never rely on color alone. Every badge includes a text label.
- **Focus:** all interactive elements are keyboard reachable. Focus ring: 2px outline, `{colors.primary}`, 2px offset. Focus order follows DOM reading order.
- **Alt text:** game cover art has `alt` set to the game title. QR code image has `alt="QR code for [Game Title] room — URL: [room-url]"`.
- **ARIA:** sidebar toggle has `aria-expanded` and `aria-label`. Collapsible sidebar items in icon-only mode have `aria-label` (the nav item name) and tooltip on hover/focus. Status badges use `role="status"` where they update live. QR Reveal is a `role="dialog"` with `aria-label="Game night session for [Game Title]"`.
- **Minimum tap target:** 44×44px for all interactive elements on touch surfaces (Guest Room page and mobile Host view).
- **Reduce motion:** the QR Reveal fade transition (300ms) is reduced to 0ms when `prefers-reduced-motion: reduce` is set. Card hover overlays appear without transition.
- **Screen reader — session ended:** when the SSE close event fires on the Room page, the replaced content is announced via `aria-live="polite"` region update.

---

## Key Flows

### Flow 1 — Baptiste prepares Wingspan for game night (UJ-1)

Protagonist: Baptiste, relaxed at his desk. Wingspan is a new purchase.

1. Baptiste opens to-board. Collection loads: existing games as a poster grid.
2. Taps "Add game". A modal appears: single text input for game title. He types "Wingspan" and confirms.
3. A new card appears in the Collection: "Wingspan", cover art placeholder (initials), badge "No content yet."
4. He taps the Wingspan card → Game Detail.
5. On Game Detail: "Upload rulebook" button. He clicks, selects the Wingspan PDF.
6. Badge transitions to "Preparing…" with a spinner. Baptiste doesn't wait — he navigates back to Collection.
7. Some time later, the badge updates to "Ready to generate." He returns to Game Detail.
8. He clicks "Generate content." A confirmation dialog warns that this will call the cloud API. He confirms.
9. Badge: "Generating…" (spinner). Generation runs in the background — Baptiste can navigate freely.
10. Notification: a subtle non-modal indicator on the Wingspan card updates to "Needs review." He navigates to the Review screen.
11. The Review screen shows two panels: Quick-start Guide and Cheat Sheet. He reads through.
12. The VP scoring section is garbled. He clicks "Reject." Confirmation: "Reject this draft? You can regenerate after." He confirms.
13. Badge returns to "Ready to generate." He clicks Generate again. Second generation is clean.
14. Back on the Review screen: "Publish." No confirmation — Publish is the intended action.

**Climax:** Wingspan's badge turns mint — "Ready to play." The card on the Collection glows with readiness. Game night can happen.

Failure path — API key missing: "Generate content" is disabled. The Game Detail screen shows an inline notice: "API key is missing — add one in Settings." Settings link inline.

---

### Flow 2 — Baptiste starts game night and reveals the QR code (UJ-2)

Protagonist: Baptiste, three friends arriving for a first Wingspan session.

1. Baptiste opens Collection. Wingspan: "Ready to play."
2. Taps Wingspan → Game Detail. "Start session" button is active (Published content exists).
3. Taps "Start session."
4. The viewport fades (300ms) to the QR Reveal: full-screen, Wingspan's cover art blurred behind a glowing panel, the QR code centered, "Wingspan" in display type, the Room URL in monospace below.
5. Baptiste turns the laptop to face his friends — or casts the tab to the TV.
6. Friends scan the QR with their phone cameras. Each arrives at the Wingspan Room page.
7. Baptiste taps `×` (top-right). The QR Reveal fades out (300ms); sidebar and Game Detail chrome return.
8. The session is active. Guests can continue using their Room pages; the QR code is still live.

**Climax:** in under 30 seconds, four phones are on the Wingspan Room page and the game explanation begins.

Failure path — Guest can't scan QR: Baptiste reads the Room URL aloud. It's short and pronounceable (`/room/wingspan-3f2a`). The Guest types it in their browser's address bar.

---

### Flow 3 — Alex looks up the egg cost rule mid-game (UJ-3)

Protagonist: Alex, first-time Wingspan player, mid-game, doesn't want to pause the table.

1. Alex is on the Wingspan Room page (joined via QR during Flow 2). Game is in progress.
2. Taps the "Cheat Sheet" tab. Content scrolls to the Cheat Sheet section.
3. Scrolls to "Egg costs." Reads the clarification.
4. Puts phone face-down and plays their turn.

**Climax:** question answered in under 10 seconds. No one at the table noticed.

---

### Flow 4 — Baptiste logs the session after game night (UJ-4)

Protagonist: Baptiste, friends are getting their coats.

1. Baptiste navigates to Session Log (sidebar). The active Wingspan session is at the top, marked "Active."
2. Taps the session row → Session Detail.
3. Taps "End session." Confirmation dialog: "End this session? The room will close for all guests." He confirms.
4. Session status changes to "Ended." The QR code is now inactive. Guests on the Room page see "This session has ended."
5. Baptiste adds player names: "Alex, Camille, Jordan" (free text, comma-separated).
6. Adds outcome: "Jordan won."
7. Saves. No toast, no animation — the detail screen updates quietly.

**Climax:** the session appears in the log with game, players, date, and outcome. The evening is captured.

---

## Inspiration & Anti-patterns

**Lifted from Jellyfin:** poster-wall collection grid. The covers are the navigation — browse by recognising the box art, not by reading a list.

**Lifted from cinema / home screening:** the QR Reveal as a moment of ceremony. Opening a board game is a ritual; the app should honor it rather than treating "start session" as a form submission.

**Rejected — inline content editing (PRD Q1 Option B):** editing Draft content inside the Review screen adds UI complexity (toolbar, edit/save state, "manually edited" tracking) for a marginal benefit. The Host's trust signal is binary: this content is good enough to show my friends, or it isn't. Reject and regenerate is the cleaner model.

**Rejected — nav badge counts:** a "3 games need review" badge on the sidebar is noise. Baptiste manages a personal collection — he knows his own games. Status lives on the cards, not in the nav.

**Rejected — persistent loading indicators:** the app does not block the Host while generation or extraction runs. These are background jobs. State updates arrive as badge changes — no progress screen to sit in front of.
