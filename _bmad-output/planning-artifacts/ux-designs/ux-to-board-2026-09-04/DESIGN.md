---
name: to-board
description: Self-hosted board game night companion. Dark, cozy, content-first. Game cover art is the primary visual element.
status: final
created: 2026-09-04
updated: 2026-09-04
colors:
  background: '#15141b'
  surface: '#1e1c27'
  surface-raised: '#29263c'
  surface-overlay: '#1e1c27e6'
  foreground: '#edecee'
  foreground-muted: '#6d6d6d'
  primary: '#a277ff'
  primary-dim: '#3d375e'
  primary-glow: '#a277ff33'
  success: '#61ffca'
  success-dim: '#61ffca1a'
  warning: '#ffca85'
  warning-dim: '#ffca851a'
  error: '#ff6767'
  error-dim: '#ff67671a'
  accent-pink: '#f694ff'
  accent-blue: '#82e2ff'
  border: '#29263c'
  border-subtle: '#1e1c27'
typography:
  display:
    fontFamily: "'DM Sans', sans-serif"
    fontSize: 48px
    fontWeight: '600'
    lineHeight: '1.1'
    letterSpacing: '-0.02em'
  heading-lg:
    fontFamily: "'DM Sans', sans-serif"
    fontSize: 32px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: '-0.01em'
  heading-md:
    fontFamily: "'DM Sans', sans-serif"
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.3'
  heading-sm:
    fontFamily: "'DM Sans', sans-serif"
    fontSize: 18px
    fontWeight: '600'
    lineHeight: '1.4'
  body-lg:
    fontFamily: "'DM Sans', sans-serif"
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: "'DM Sans', sans-serif"
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.6'
  label:
    fontFamily: "'DM Sans', sans-serif"
    fontSize: 13px
    fontWeight: '500'
    lineHeight: '1.4'
  caption:
    fontFamily: "'DM Sans', sans-serif"
    fontSize: 12px
    fontWeight: '400'
    lineHeight: '1.4'
    letterSpacing: '0.02em'
  mono:
    fontFamily: "'DM Mono', 'Fira Code', monospace"
    fontSize: 13px
    fontWeight: '400'
    lineHeight: '1.5'
rounded:
  sm: 6px
  md: 10px
  lg: 16px
  xl: 20px
  full: 9999px
spacing:
  '1': 4px
  '2': 8px
  '3': 12px
  '4': 16px
  '5': 24px
  '6': 32px
  '7': 48px
  '8': 64px
  sidebar-expanded: 240px
  sidebar-collapsed: 60px
components:
  game-card:
    background: '{colors.surface}'
    border-radius: '{rounded.xl}'
    aspect-ratio: '2/3'
    cover-overlay: 'linear-gradient(to top, rgba(21,20,27,0.92) 0%, rgba(21,20,27,0) 50%)'
    title-color: '{colors.foreground}'
    title-typography: '{typography.label}'
  status-badge:
    border-radius: '{rounded.full}'
    padding: '3px 8px'
    typography: '{typography.caption}'
    ready-to-play-bg: '{colors.success-dim}'
    ready-to-play-color: '{colors.success}'
    needs-review-bg: '{colors.warning-dim}'
    needs-review-color: '{colors.warning}'
    rejected-bg: '{colors.error-dim}'
    rejected-color: '{colors.error}'
    no-content-bg: 'transparent'
    no-content-color: '{colors.foreground-muted}'
    generating-color: '{colors.foreground-muted}'
  sidebar:
    background: '{colors.surface}'
    width-expanded: '{spacing.sidebar-expanded}'
    width-collapsed: '{spacing.sidebar-collapsed}'
    border-right: '1px solid {colors.border}'
    active-bg: '{colors.surface-raised}'
    active-color: '{colors.primary}'
    inactive-color: '{colors.foreground-muted}'
    transition: '200ms ease'
  button-primary:
    background: '{colors.primary}'
    color: '{colors.background}'
    border-radius: '{rounded.md}'
    padding: '10px 20px'
    typography: '{typography.label}'
    font-weight: '600'
    hover-background: '#b899ff'
  button-ghost:
    background: 'transparent'
    color: '{colors.foreground-muted}'
    border: '1px solid {colors.border}'
    border-radius: '{rounded.md}'
    padding: '10px 20px'
    typography: '{typography.label}'
    hover-color: '{colors.foreground}'
    hover-border: '{colors.foreground-muted}'
  button-danger:
    background: 'transparent'
    color: '{colors.error}'
    border: '1px solid {colors.error-dim}'
    border-radius: '{rounded.md}'
    padding: '10px 20px'
    typography: '{typography.label}'
    hover-background: '{colors.error-dim}'
  qr-reveal:
    backdrop: 'cover art blurred — backdrop-filter: blur(40px) brightness(0.35) + scale(1.1)'
    panel-background: 'rgba(21, 20, 27, 0.75)'
    panel-border: '1px solid {colors.primary-dim}'
    panel-border-radius: '{rounded.xl}'
    panel-glow: '0 0 48px {colors.primary-glow}, 0 0 120px {colors.primary-glow}'
    qr-size: 280px
    qr-background: '{colors.foreground}'
    qr-foreground: '{colors.background}'
  room-page:
    background: '{colors.background}'
    max-width: 640px
    tab-active-color: '{colors.primary}'
    tab-inactive-color: '{colors.foreground-muted}'
    tab-indicator: '{colors.primary}'
    section-heading-color: '{colors.foreground}'
    body-color: '{colors.foreground}'
---

## Brand & Style

to-board is a space that prepares for game night. Before the first guest arrives, before the box is opened, the app is already doing its work — covers arranged on the shelf, content ready, a QR code waiting to be revealed.

The aesthetic borrows from Jellyfin's media library instinct: the collection *is* the UI. Game cover art carries the visual weight; the chrome stays out of its way. Dark surfaces (`#15141b`) create the atmosphere of a dimmed room — an invitation to settle in, not a form to fill out.

The palette is Aura: deep near-black backgrounds, a vivid purple brand identity, mint for readiness, amber for attention, red for error. These are not decorative — each color has exactly one job. The purple glows; it should feel like something is alive on the screen.

Microcopy is calm and purposeful. No exclamation marks. States are described plainly ("Ready to play", not "Content published successfully!"). The app doesn't celebrate itself — it gets out of the way so the game can happen.

Guest surfaces (the Room page) are even more stripped. A Guest landed via QR code; they want a cheat sheet, not an app. Maximum content, zero chrome.

## Colors

The palette is Aura Dark, mapped to semantic roles. Every color has a single job; none are used decoratively outside their role.

- **Background (`#15141b`)** — the primary canvas. Near-black with a purple undertone. All surfaces sit above this. Never use as text color.
- **Surface (`#1e1c27`)** — cards, panels, the sidebar. One step above background. The shelf where covers rest.
- **Surface-raised (`#29263c`)** — hover states, active sidebar items, elevated interactive areas. Two steps above background.
- **Foreground (`#edecee`)** — primary text. Slightly warm off-white. All body copy, headings, labels.
- **Foreground-muted (`#6d6d6d`)** — secondary text, captions, inactive sidebar labels, placeholder states.
- **Primary (`#a277ff`)** — brand purple. Interactive affordances, focus rings, active states, the QR panel glow. The one color that feels alive.
- **Primary-dim (`#3d375e`)** — subtle primary tints for backgrounds. Used in the sidebar active state behind the primary-colored icon.
- **Success (`#61ffca`)** — mint. "Ready to play" badges and indicators only. Do not use for general confirmations.
- **Warning (`#ffca85`)** — amber. "Needs review" badges and states only.
- **Error (`#ff6767`)** — red. "Rejected" badges and destructive confirmations only.
- **Accent-pink (`#f694ff`) and accent-blue (`#82e2ff`)** — reserved for future use. Do not introduce in v1 without a defined semantic role.
- **Border (`#29263c`)** — default hairline between surfaces. 1px solid.

Avoid: gradient fills on interactive elements, using success/warning/error colors outside their defined state, using primary for decorative accents unrelated to interactivity.

## Typography

DM Sans throughout. Slightly rounded letterforms reinforce the cozy posture without feeling playful. The scale moves from 12px captions to 48px display (used only in the QR Reveal game title).

- **Display (48px/600)** — game title on the QR Reveal screen only. Full cinematic weight.
- **Heading-lg (32px/600)** — section headers, game detail title.
- **Heading-md (24px/600)** — screen-level headings (Collection, Session Log, Settings).
- **Heading-sm (18px/600)** — subsection headings, content section titles on the Room page.
- **Body-lg (16px/400)** — primary body text. Quick-start guide prose, cheat sheet content, session log entries.
- **Body-md (14px/400)** — secondary body text, sidebar labels when expanded, form field content.
- **Label (13px/500)** — badge text, button labels, input labels, nav item labels.
- **Caption (12px/400)** — timestamps, metadata, URL display under QR code.
- **Mono (13px/400)** — Room URL display under the QR code. Makes the URL scannable for manual entry.

Load DM Sans from Google Fonts (weights 400, 500, 600). DM Mono for the monospace role.

## Layout & Spacing

Base unit: 4px. Scale: 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64px.

**Host layout:** sidebar (240px expanded, 60px collapsed) + main content area. Main content has a minimum 32px horizontal padding and centers at a comfortable max-width of 1400px on very wide screens. The collection grid fills the available width.

**Collection grid:** responsive card grid. Card aspect ratio 2:3 (portrait — board game box art is always portrait). Minimum card width 160px, preferred 200px, maximum 260px. Gap: 16px. `grid-template-columns: repeat(auto-fill, minmax(160px, 1fr))`. Cards breathe; the grid adjusts to viewport without pagination.

**Guest (Room page):** single-column, max-width 640px, centered. 20px horizontal padding on mobile. Content sections separated by 32px. No sidebar, no host chrome.

**Vertical rhythm:** 24px between related elements (label → content), 48px between sections.

## Elevation & Depth

to-board avoids box shadows as an elevation signal — they read as "web UI" on a dark background. Elevation is communicated through surface color steps alone:

- Level 0: `background` (`#15141b`)
- Level 1: `surface` (`#1e1c27`) — cards, sidebar
- Level 2: `surface-raised` (`#29263c`) — hover states, active areas, dropdowns

The single exception is the QR Reveal panel: a `box-shadow: 0 0 48px {colors.primary-glow}, 0 0 120px {colors.primary-glow}` glow effect. This is intentional and cinematic — it is the only moment where a glow is used, and it must feel earned.

Borders are 1px `{colors.border}` (`#29263c`). Use only where surface color alone is insufficient to separate elements (e.g., sidebar edge against the main content area).

## Shapes

- `rounded/sm` (6px) — input fields, small interactive elements, icon buttons.
- `rounded/md` (10px) — buttons, dropdowns, tooltips.
- `rounded/lg` (16px) — modals, drawers, larger panels.
- `rounded/xl` (20px) — game cards, the QR reveal panel.
- `rounded/full` (9999px) — status badges, pill labels.

Game cards are `rounded/xl`. Cover art fills the card and clips to the same radius (`overflow: hidden`). The radius softens the shelf feel — these are boxes, not rectangles.

## Components

**Game Card**
The primary visual unit. Cover art fills a 2:3 portrait container, clipped to `rounded/xl`. A linear gradient overlay runs from transparent (top 50%) to near-opaque `rgba(21,20,27,0.92)` at the bottom — game title and status badge appear against this gradient on hover/focus. The title is `label` weight; the badge sits to the left of the title in the bottom-left area. On pointer devices, the overlay is hidden at rest and appears on hover (200ms opacity transition). On touch devices, the overlay is always visible. Cards without cover art show game initials centered in `heading-md` weight on `surface-raised` background.

**Status Badge**
Pill shape (`rounded/full`). Color pairs: mint background-dim + mint text ("Ready to play"), amber-dim + amber ("Needs review"), red-dim + red ("Rejected"), transparent + muted ("No content yet"), muted text only with a spinner icon ("Generating…"). Always includes text — never color alone.

**Sidebar**
`surface` background with a 1px right border. 240px expanded, 60px collapsed. Collapsed shows icons only (24×24px), centered. Expanded shows icons (20×20px) + labels in `body-md`. Active item: `surface-raised` background, primary color icon and label. Toggle: a chevron button at the bottom of the sidebar. Transition: `width 200ms ease`. At `< 768px` viewport, the sidebar becomes a slide-in drawer overlay rather than a persistent sidebar.

**Buttons**
Three variants: Primary (solid purple fill, dark text), Ghost (transparent, muted border), Danger (transparent, red border/text). All use `rounded/md`, `label` typography, 10px/20px padding. Hover states: Primary lightens (`#b899ff`), Ghost gains foreground color, Danger gains red background-dim fill. Focus: 2px offset outline in `{colors.primary}`.

**QR Reveal Overlay**
Full-screen. Sidebar and nav chrome are hidden (`display: none`). The game's cover art is positioned as a full-bleed background image with `backdrop-filter: blur(40px) brightness(0.35)` and `transform: scale(1.1)` (to prevent blur edge artifacts). A semi-transparent panel (75% opaque background, `rounded/xl`, primary-dim border) is centered, containing: the QR code (280×280px, white modules on dark background), the game title in `display` typography, the Room URL in `mono` caption. The panel casts the `primary-glow` box-shadow. An `×` exit button (ghost, top-right of the viewport, not the panel) returns to normal chrome with a 300ms fade.

**Room Page Tabs**
Two tabs: "Quick-start" and "Cheat Sheet". Sticky below the game title header. Inactive: `foreground-muted` color. Active: `primary` color with a 2px bottom border indicator in `primary`. Tab content is a full scrollable section — no pagination, no fixed-height containers.

## Do's and Don'ts

| Do | Don't |
|---|---|
| Use cover art as the primary visual identity for each game | Use placeholder icons or generic game illustrations |
| Keep the sidebar chrome invisible — surface colors only | Add decorative borders, dividers, or shadows to sidebar items |
| Use exactly one glow effect: the QR Reveal panel | Apply glows, blurs, or gradients elsewhere |
| Status badges: always color + text together | Use color alone to communicate state |
| Keep the Room page free of all Host chrome | Show sidebar, nav, or actions on the Guest Room page |
| Transition the QR Reveal with a fade (300ms) | Animate with slides, bounces, or spring physics |
| Inactive states: muted gray, no tint | Use amber/red for things that are merely inactive |
| Monospace for the Room URL | Use body font for URLs — scannability matters |
