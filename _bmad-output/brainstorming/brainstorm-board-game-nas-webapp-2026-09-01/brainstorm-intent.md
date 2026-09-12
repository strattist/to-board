# Intent: Board Game NAS Web App

## What this is

A self-hosted web app, living on a personal NAS, that centralises everything needed for game night: rulebooks (official PDFs), AI-generated quick-starts and cheat sheets, session history, and a QR-based room system so friends can join instantly. The primary goal is to get everyone playing as fast as possible, with as little friction as possible.

---

## Core design principles

- **Solo-first, opt-in sharing.** The app is Baptiste's personal tool. Nothing is forced on guests; they join when invited via QR.
- **Unobtrusive.** The app assists the game — it never interrupts or hijacks it.
- **Official PDF is authoritative.** AI content supplements; it never replaces the rulebook.
- **Layered depth.** Simple view first, drill deeper on demand (cheat sheet → full rule section).
- **App learns through use.** Every session and every content review makes the app smarter — history and quality both improve over time via the same feedback loop.

---

## Must have

- Game collection with PDF rulebook storage and viewer (zoom, page flip, section jump, screen-stay-awake mode)
- AI-generated quick-start guide and cheat sheet per game, with a draft → review → publish pipeline
- Session log (game played, players, date, outcome)
- QR room flow: host picks game, QR appears, guests scan and land directly in the correct game room

---

## Should have

- Content quality voting — bad AI content triggers regeneration
- Cheat sheet items deep-link to the relevant rule section in the full PDF
- Private phone view — guests can quietly look up rules on their own screen without asking aloud
- Solo mode — full app usable without any guests present
- Session photos — players can attach photos to a session
- Play mode — screen stays awake, tap-to-advance during rule explanation (cook-mode UX)

---

## Could have

- Interactive scorecards per game
- Adaptive quick-start — detects experienced players in the room and auto-skips rules they already know
- AI card lookup — search by text or submit a photo; AI answers in game context
- Rule bookmarks within PDFs
- Friendship / history chronicle view — the group's gaming life over time
- First-player randomiser with fun/silly methods

---

## Won't have (for now)

- Nostalgia / "on this day" push notifications
- Year-in-review analytics
- BGG-powered game recommendations
- Wishlist / want-to-play list
- AI text-to-speech rule narration

---

## Key synthesis insights

1. **One learning loop, two surfaces.** Session history improves adaptive quick-start; content reviews improve AI quality. These are not two features — they are the same feedback loop applied to different data.
2. **The unified personal window.** Private phone view, interactive scorecards, and AI card lookup are three facets of one concept: each player's personal, silent reference during a live game. They should share a single UX surface.
3. **QR is a session artefact, not a permanent fixture.** The host generates a QR per session after selecting the game; no permanent stickers or pre-assigned codes. This keeps the flow lightweight and removes any setup burden from guests.

---

## Suggested next step

Run `bmad-product-brief` to expand this intent into a structured product brief, or `bmad-prd` to go straight to requirements.
