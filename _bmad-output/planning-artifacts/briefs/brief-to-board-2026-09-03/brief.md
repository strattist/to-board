---
title: "Product Brief: to-board"
status: draft
created: 2026-09-03
updated: 2026-09-03
---

# Product Brief: to-board

## Executive Summary

to-board is a self-hosted web app that lives on a personal NAS and centralises everything needed for board game night: official PDF rulebooks, AI-generated quick-start guides and cheat sheets, a session history log, and a QR-based room system that gets guests into the right game in seconds. It is deployed once, runs entirely on the local network, and requires nothing from guests except a phone camera.

The core problem it solves is the dead time between opening a box and actually playing. Rules need to be explained from memory or hunted through a PDF on someone's phone, cheat sheets are improvised or nonexistent, and the evening's history evaporates when everyone goes home. to-board closes that gap: the host picks a game, a QR code appears, guests scan in, and a prepared quick-start guide is already waiting.

It is Baptiste's personal tool first. The design reflects that — nothing is forced on guests, the app assists the game rather than hijacking it, and the official PDF is always the authoritative source. AI-generated content supplements; it never replaces.

---

## The Problem

Game nights lose their energy in setup. The rulebook PDF is on someone's phone in a folder no one can find. Rule disputes interrupt flow — someone has to scroll through 40 pages while the table waits. Experienced players remember the rules but struggle to explain them concisely to newcomers. And once the night is over, it is over: no record of who played, who won, no memory of that three-hour epic from six months ago.

The existing solutions are all compromises. Cloud companion apps require everyone to create an account and install something before the first game. BGG is comprehensive but built for collectors and researchers, not for a table mid-play. Physical cheat sheets exist for popular games but are generic and never cover a specific collection. Rulebook PDFs are authoritative but hostile to quick reference.

See addendum §Landscape Context for competitive detail and research sources.

[ASSUMPTION: the pain points above are inferred from the design principles and feature set — not from user research. Flag if this section will be read by anyone other than Baptiste.]

---

## Who This Serves

**Primary: Baptiste (the host).** Owns the collection, manages the content pipeline, controls the session. Wants game nights to start smoothly and leave a record. Technical enough to run Docker on a NAS; not interested in maintaining a complex system. Uses the app before, during, and after every game night.

**Secondary: guests.** Friends at the table — casual players, mixed experience levels, non-technical. They join via QR, use the quick-start and cheat sheet on their phone, look up rules quietly without interrupting the game. They bring no setup burden and leave nothing behind.

[ASSUMPTION: guest profile is inferred. If a regular co-host or highly experienced returning player exists, that persona may deserve explicit treatment in the PRD.]

---

## Design Philosophy

These five principles are invariants. They apply to every feature decision and flow through to the PRD and architecture.

1. **Solo-first, opt-in sharing.** to-board is Baptiste's personal tool. The full app is usable with no guests present. Guests are welcome, but nothing is forced on them.

2. **Unobtrusive.** The app assists the game — it never interrupts it. UI chrome and prompts are minimised during active play.

3. **Official PDF is authoritative.** AI content supplements; it never replaces the rulebook. When there is a conflict, the PDF wins.

4. **Layered depth.** Simple view first, drill deeper on demand. A guest sees the cheat sheet; the full rule section is one tap away.

5. **The app learns through use.** Session history and content quality reviews feed the same loop: more play data improves adaptive features; more reviews improve AI content quality.

---

## v1 Scope

v1 is done when a real game night runs on it from end to end.

**In:**
- Game collection with PDF upload, storage, and viewer (zoom, page navigation, screen-stay-awake)
- AI-generated quick-start guide and cheat sheet per game, with draft → review → publish pipeline
- QR room flow: host picks game, QR appears, guests land in the correct game room
- Session log: game, players, date, outcome

**Deferred — strong candidates for v1.1:**
- Content quality voting (bad AI output triggers regeneration)
- Deep-linked cheat sheet items (tap to jump to relevant PDF page)
- Private phone view (guests look up rules silently)
- Session photos
- Play mode (screen stays awake, tap-to-advance during rule explanation)

**Won't have:**
- Interactive scorecards
- Adaptive quick-start (experience detection)
- AI card lookup / photo search
- BGG integration of any kind
- Push notifications, analytics, year-in-review
- AI text-to-speech

---

## Success Criteria

**User success:**
- A game night runs start-to-finish using to-board: host selects game, guests join via QR, cheat sheet is used at the table, session is logged.
- Guests join without asking for help.
- The host does not reach for their phone to look up a rule during the session.
- AI-generated content for at least one game reaches published state after one review pass.

**Non-functional targets (for architecture):**
- Page load on LAN: < 3 seconds for any screen under normal use
- Concurrent guests: supports up to 8 simultaneously connected guests
- Data durability: session log and generated content survive container restarts and TrueNAS SCALE updates without loss
- NAS resource ceiling: < 2 GB RAM and negligible CPU at idle; < 4 GB RAM under active session load
- Generation cost: < $0.10 per game rulebook at setup time (cloud API call, BYOK)

---

## Technical Context

**Platform:** TrueNAS SCALE, deployed via Docker Compose. LAN-served; internet is available for generation API calls.

**AI generation:** Cloud BYOK (bring your own key) at content generation time — Claude Haiku or Gemini Flash, costing approximately $0.01–0.05 per rulebook. Generated content is stored on the NAS. No cloud calls occur during a game night. The NAS is not expected to run local inference.

**PDF handling:** Rulebooks are uploaded by the host, stored on the NAS, and served directly to clients. PDF text is extracted locally for AI input — no rulebook content leaves the home network beyond what is sent to the generation API when the host explicitly triggers generation.

**Deployment:** Single Docker Compose stack. Persistent data (PDFs, generated content, session log) maps to a TrueNAS dataset — not a Docker volume — to survive container rebuilds and OS updates.

---

## Constraints and Risks

**Constraints:**
- The NAS is not expected to run local LLM inference; AI generation always goes through the cloud API
- No GPU available; the stack is CPU and storage only
- Single host user; up to ~8 concurrent guest readers
- All runtime serving must work on LAN without internet (internet required only for generation)
- Deployment must be a single Docker Compose stack — no Kubernetes, no external runtime dependencies

**Risks:**

| Risk | Impact | Mitigation |
|---|---|---|
| Cloud API key expires or is revoked | New game content generation blocked; existing content unaffected | App degrades gracefully: serve existing content, surface a setup warning |
| PDF extraction quality is poor (tables, sidebars, multi-column) | Bad AI input → low-quality first draft | Review pipeline is the guardrail; regeneration is cheap |
| TrueNAS update breaks Docker volume mounts | Data loss | Map all persistent data to a named TrueNAS dataset |
| AI hallucination in published content | Incorrect rules served at the table | Draft → review → publish enforced; explicit "PDF is authoritative" UI cue |

---

## Open Questions

These assumptions are embedded in the brief. They are not blockers for the PRD but should be confirmed before the UX design phase.

- **[ASSUMPTION] The Problem section** — game night friction (PDF hunting, rule disputes, no shared history) is inferred, not validated. Confirm this matches lived experience.
- **[ASSUMPTION] Guest persona** — guests are assumed to be casual, non-technical, zero-setup-tolerance. If a regular experienced co-host exists, that persona may need explicit design treatment.

---

## Vision

to-board becomes the host's quiet infrastructure — always there, always ready, accumulating the group's gaming history over time. The session log grows into a chronicle: who plays most, which games come out most, that three-hour session from three years ago.

The personal-tool constraint is deliberate, not incidental. No accounts, no subscriptions, no data leaving the house. If it works well, it is a natural fit for the self-hosted and homelab community, where a polished board game companion app with Docker Compose deployment is a genuine gap. But that is a future decision, not a present commitment.
