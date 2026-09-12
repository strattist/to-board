---
title: "Reconciliation: Brief → PRD (to-board 2026-09-03)"
created: 2026-09-03
---

# Reconciliation: Brief → PRD

## Summary

The PRD covers all four v1 feature areas and the five design invariants faithfully. The main losses are architectural: two explicit design synthesis conclusions from the addendum — "one learning loop, two surfaces" and the "unified personal window" — are absent from the PRD entirely, despite the addendum directing that the PRD should model them. Several qualitative tonal signals (unobtrusive-as-acceptance-criterion, solo mode as invariant rather than feature) are present as principles but never land as testable constraints in any FR.

---

## Gaps (things in brief/addendum not in PRD)

- **[HIGH]** **"One learning loop, two surfaces" design synthesis** — Addendum §Key Design Synthesis explicitly states: *"The PRD should model this as a single mechanism, not two separate systems."* Session history (adaptive quick-start) and content reviews (AI quality) are the same feedback loop applied to different data. PRD splits them into two unconnected feature sections (§4.2 and §4.4) with no mention of the shared mechanism. — **Fix:** add a sub-section to §4 or §6.2 naming the learning-loop as a unified architectural concern; reference it from both the content pipeline and session log sections.

- **[HIGH]** **"Unified personal window" concept dropped** — Addendum §Key Design Synthesis says private phone view, interactive scorecards, and AI card lookup are "three facets of one concept" sharing a single UX surface, and that "designing them as separate features risks fragmented UX and duplicated architecture." PRD §6.2 lists them as three independent deferred items with no mention of this coupling. — **Fix:** add a note under Private phone view in §6.2 referencing the unified-personal-window concept and the intent to establish the shared surface in v1.1.

- **[MED]** **Solo mode is an invariant, not a feature** — Addendum explicitly flags: *"'solo mode' is NOT a should-have feature — it is a fulfilment of Design Philosophy principle #1 (solo-first) and must hold from v1. It is not an add-on."* PRD implies solo use works (the host can use the app without guests) but never states this as a hard constraint on any FR. Nothing prevents an implementation from accidentally gating core flows on an active Session. — **Fix:** add a sentence to §6.1 or under FR-10 making it explicit that a Game can be viewed, its Rulebook read, and its Content accessed by the Host without starting a Session.

- **[MED]** **QR-less session explicit in data model** — Addendum: *"A session without a QR is valid (solo mode); a QR without a session is not."* This constraint is implied but not enforced anywhere in the FRs or glossary. The Session definition in §3 and FR-10 always generates a QR on start, which silently breaks the solo-mode use case. — **Fix:** either allow Session start without QR generation (solo toggle), or decouple Session creation from QR generation in FR-10's consequences.

- **[MED]** **"Page-level citations are table stakes" competitive signal** — Addendum §Landscape Context: *"Page-level citations are now table stakes in this space"* for AI rules tools. PRD defers Cheat Sheet deep-links to v1.1 without acknowledging this competitive gap. Readers making prioritisation calls won't see why v1.1's deep-links matter strategically. — **Fix:** add one sentence in §6.2 under "Cheat Sheet deep-links" citing this landscape observation.

- **[MED]** **Generation cost ceiling as success criterion** — Brief §Success Criteria states: *"< $0.10 per game rulebook at setup time."* PRD §8 mentions estimated costs (~$0.01–0.05) as context but never formalises the ceiling as a success metric. SM-2 validates pipeline quality; nothing validates cost. — **Fix:** add SM-6 or a cost NFR: *Generation cost per Rulebook must not exceed $0.10 at the recommended model tier.*

- **[LOW]** **Pipeline state naming discrepancy** — Addendum uses `draft → reviewed → published`; PRD glossary uses `Draft → Published → Rejected` with no intermediate "reviewed" state. If "reviewed" was intentional (a state between human review and publish confirmation), the PRD has collapsed it silently. — **Fix:** confirm with author whether "reviewed" was a distinct state or just narrative shorthand; update glossary accordingly.

- **[LOW]** **First-player randomiser and chronicle view missing from PRD Could Have** — Addendum §MoSCoW lists "Friendship/history chronicle view" and "First-player randomiser" under Could Have. PRD §6.2 Out of Scope does not mention them. The PRD's non-goals only cover Won't Have items; Could Have items beyond the v1.1 tier are invisible. — **Fix:** either add a "Future / Could Have" subsection to §6.2, or note that the addendum MoSCoW is the canonical Could Have reference.

---

## Qualitative losses (tone, feel, design intent the FR structure silently drops)

- **"The app assists the game — it never interrupts it"** — Brief Design Philosophy #2 is listed once in §1 but no FR translates it into an acceptance criterion. The Room page, the end-session flow, and host notifications all have potential to intrude at the table. There is no FR that says "no unsolicited prompts, alerts, or banners during an active Session."

- **"Layered depth" as a structural UX constraint** — Brief principle #4 (*"simple view first, drill deeper on demand; a guest sees the cheat sheet; the full rule section is one tap away"*) shapes the Room page hierarchy. FR-13 lists display requirements but does not mandate that the Cheat Sheet is the default/top-level view and the Quick-start Guide is secondary. A developer could reasonably place them as equal-weight tabs and not violate FR-13.

- **"Quiet infrastructure" feel** — The brief's vision of to-board as always-there, always-ready, accumulating history "without demanding attention" is well captured in §1 but evaporates in the FR list. None of the FRs contain acceptance criteria about the host-facing dashboard being calm and low-chrome outside of Play Mode. The risk is an app that feels like a management console rather than background infrastructure.

- **Personal-tool deliberateness** — Brief §Vision: *"The personal-tool constraint is deliberate, not incidental."* This framing signals that future homelab-community expansion is possible but not yet committed to, and that no current decision should be made to accommodate it. The PRD's §5 Non-Goals and §9 Platform section don't carry this forward explicitly. The risk is premature generalisation (multi-user scaffolding, configurable multi-game rooms, etc.) creeping in during architecture without the brief's explicit permission to stay small.

- **"Unobtrusive" applied to AI content UI cues** — Brief principle #3 includes: *"explicit 'PDF is authoritative' UI cue."* This is mentioned in the risks table of the brief but absent from FR-13 (Room page) and FR-7 (review screen). There is no FR requiring the UI to carry the "PDF is authoritative" signal to guests.

---

## Confirmed coverage (brief items well-represented in PRD)

- Five design invariants named and referenced in §1
- BYOK AI generation model; no default key; stored locally
- PDF text extracted locally; no raw PDF bytes leave the network
- All content served from LAN at runtime; generation is the only cloud-touching step
- TrueNAS dataset mapping (not Docker volume) for data durability — FR-2, FR-18, NFR-4
- Guest anonymity: no data persisted, no login, no cookie banner — FR-12
- QR as session artefact (per-session, not permanent) — FR-11 glossary
- Draft → review → publish pipeline with rejection and regeneration — FR-5 through FR-7
- Session log structure (game, players, date, outcome) — FR-15 through FR-17
- Play Mode defined (screen stay-awake + minimised chrome; tap-to-advance deferred) — FR-3, §6.2
- NFR targets: 3s LAN page load, 8 concurrent guests, 2 GB / 4 GB RAM ceiling — NFR-1 through NFR-5
- BGG exclusion explicit — §5
- Generation cost range stated — §8
- All Won't Have items from brief covered in §5 and §6.2
- Open Question Q2 (session start without published content) acknowledges the potential early-adoption blocker
