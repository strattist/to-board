---
title: "Addendum: to-board"
status: draft
created: 2026-09-03
updated: 2026-09-03
---

# Addendum: to-board

Supporting depth for the brief. Each section is annotated with its intended downstream consumer.

---

## Landscape Context

*For: PRD framing, architecture positioning*

From discovery research (September 2026):

- **No self-hosted board game companion app** (collection + rulebook PDFs + session logging, Docker-deployable) appears in the TrueNAS, Unraid, or CasaOS catalogs. This is a genuine gap. Two early-stage GitHub projects (cardboard-v2, Collecter) appeared in early 2026 with low traction; neither includes AI content generation or a session room flow.
- **Cloud companion apps exist** (Board Game Now, TableTopSage, BoardHub) but require accounts and internet access, and offer no PDF ownership model. None is self-hostable.
- **AI rules lookup tools exist** (Game Guru, BoardTruth, RulesBot, BoardGame Librarian) but are all cloud-hosted, subscription or freemium, and not integrated with a personal collection or session history. Page-level citations are now table stakes in this space.
- **The homelab mental model** for this product is Paperless-NGX (document management) + Jellyfin (personal media library) — fused and scoped to board games. That framing is immediately recognisable to the self-hosted community.
- **BGG is the only comprehensive game database.** Every competitor is a layer on top of it. to-board deliberately avoids BGG dependency for v1 — manual PDF upload keeps scope clean and avoids API rate limits and data freshness concerns.

---

## Full MoSCoW Scope Breakdown

*For: PRD backlog, sprint planning*

### Must Have (v1)

- Game collection with PDF rulebook storage and viewer (zoom, page flip, section jump, screen-stay-awake)
- AI-generated quick-start guide and cheat sheet per game, with draft → review → publish pipeline
- Session log: game played, players, date, outcome
- QR room flow: host picks game, QR appears, guests scan and land directly in the correct game room

### Should Have (v1.1 candidates)

- Content quality voting — bad AI content triggers regeneration
- Cheat sheet items deep-link to the relevant rule section in the full PDF
- Private phone view — guests can quietly look up rules on their own screen without asking aloud
- Session photos — players can attach photos to a session
- Play mode — screen stays awake, tap-to-advance during rule explanation (cook-mode UX)

Note: "solo mode" (full app without guests) is not a should-have feature — it is a fulfilment of Design Philosophy principle #1 (solo-first) and must hold from v1. It is not an add-on.

### Could Have (future)

- Interactive scorecards per game
- Adaptive quick-start — detects experienced players in the room and auto-skips rules they already know
- AI card lookup — search by text or submit a photo; AI answers in game context
- Rule bookmarks within PDFs
- Friendship / history chronicle view — the group's gaming history over time
- First-player randomiser with fun/silly methods

### Won't Have (explicitly deferred — not just deprioritised)

- Nostalgia / "on this day" push notifications
- Year-in-review analytics
- BGG-powered game recommendations
- Wishlist / want-to-play list
- AI text-to-speech rule narration

---

## Key Design Synthesis

*For: PRD feature design, UX architecture*

Three structural insights from the brainstorm that inform PRD and UX decisions, split by release horizon:

### v1 implications

**QR is a session artefact, not a permanent fixture.**
The host generates a QR per session after selecting the game — no permanent stickers, no pre-assigned codes. The QR lifecycle (generate → active during session → expire) should be modelled explicitly in the data model. A session without a QR is valid (solo mode); a QR without a session is not.

### v1.1+ implications

**The unified personal window.**
Private phone view, interactive scorecards, and AI card lookup are three facets of one concept: each player's personal, silent reference during a live game. They should share a single UX surface. Designing them as separate features risks fragmented UX and duplicated architecture. Establish the surface in v1.1 with private phone view; extend it in later iterations.

**One learning loop, two surfaces.**
Session history improves adaptive quick-start; content reviews improve AI quality. These are not two features — they are the same feedback loop applied to different data. The PRD should model this as a single mechanism, not two separate systems.

---

## AI Content Pipeline — Architecture Notes

*For: architecture doc, technical design*

### Generation

- Trigger: host manually initiates generation per game, after uploading the rulebook PDF
- Input: PDF extracted to text locally; chunked if needed; sent to cloud LLM with a structured prompt
- Output: quick-start guide (narrative walkthrough, ~5-minute read) + cheat sheet (structured key rules, turn sequence, gotchas)
- Pipeline state: `draft` → `reviewed` → `published`; bad output → `rejected` → regeneration

### Storage

- Generated content stored as structured data on the NAS (Markdown or JSON in a local DB)
- PDF stored as the uploaded file; text extraction cached separately
- No content is fetched from the cloud at runtime — all serving is local

### Cloud API sizing

| Model | Input price | 40K-token rulebook cost | Notes |
|---|---|---|---|
| Claude Haiku 4.5 | ~$1/M tokens | ~$0.04 | Recommended default |
| Gemini 2.5 Flash | ~$0.075/M tokens | ~$0.003 | Cheapest viable option |
| GPT-4o mini | ~$0.15/M tokens | ~$0.006 | Good fallback |

BYOK: the app ships with no default key. Baptiste supplies their own API key at setup; the key is stored locally. No key is required at game night runtime.

### Offline resilience

- Content generation requires internet (cloud API call) — expected, infrequent
- Everything else (PDF serving, cheat sheet display, QR room, session log) works fully on LAN with no internet
- If internet drops mid-session: no impact on anything already generated and published
