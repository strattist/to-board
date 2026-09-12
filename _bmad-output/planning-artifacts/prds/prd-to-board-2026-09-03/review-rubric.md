# PRD Quality Review — to-board

**Reviewed:** `prd-to-board-2026-09-03/prd.md`
**Reviewer context:** Solo personal project, intermediate rigor (feeds architecture + epics)
**Date:** 2026-09-03

---

## Overall verdict

A well-formed PRD that is notably above-average on NFR concreteness and scope honesty. Its two real structural gaps are: (1) a hidden real-time push requirement buried in FR-14 consequences that will blindside architecture, and (2) design invariants declared as first-class constraints in §1 but left completely untraceable through FRs and SMs — making them decorative rather than operative. Fix those two and this PRD is architecture-ready.

---

## 1. Decision-readiness — adequate

The six open questions are genuinely open (not rhetorical placeholders), and three of them (OQ-1, OQ-2, OQ-5) directly affect architecture or UX scope. However, only OQ-1 has an explicit "Decision needed before [milestone]" gate — the other five float free, which risks them staying unresolved until they block implementation mid-sprint.

Trade-off surfacing is implicit at best. The BYOK / cloud-LLM choice, the push vs. polling decision for FR-14, and the PDF.js dependency are stated as assumptions but no rationale or alternative is weighed. For a solo project this is acceptable in isolation, but it means the architecture phase will need to reconstruct context that could have been captured here cheaply.

### Findings

- **high** OQ-2 lacks a resolution gate (§11 Q2) — "Should the Host be able to start a session without Published Content?" could block early-sprint decisions on the Session start flow. *Fix:* add "Decision needed before FR-10 implementation" and make a provisional call inline.
- **high** OQ-4 lacks a resolution gate (§11 Q4) — "Is Play Mode meaningful enough to ship in v1?" is a scope decision. If the answer is no, FR-13's screen-stay-awake consequence and §6.1's Play Mode bullet become noise. *Fix:* add "Decision needed before §4.3 implementation; default: ship v1 Play Mode as scoped."
- **medium** OQ-5 lacks a resolution gate (§11 Q5) — auth mechanism affects deployment setup notes and first-run UX. *Fix:* add "Decision needed before architecture §deployment."
- **low** OQs 3 and 6 lack resolution gates but are lower-stakes (URL format, PDF-replace behavior). *Fix:* same pattern — add "Decision needed before X."

---

## 2. Substance over theater — strong

This is the PRD's clearest strength. NFRs are uniformly concrete: 3s page load, 2s PDF first render for PDFs ≤50 MB, 8-Guest ceiling, 2 GB RAM idle / 4 GB under load, < 5% CPU idle. No "scalable," "secure," or "performant" boilerplate anywhere.

The JTBD are specific and grounded. User Journeys carry named personas, precise entry states, edge cases, and resolution states — not just happy paths. The counter-metric SM-C1 ("app management time does not exceed play time") is exactly the right kill-switch for a personal-tool PRD.

One minor concern: the five design invariants (§1: solo-first, unobtrusive, PDF-authoritative, layered depth, learning through use) are declared as constraints that govern every feature decision — but they never appear again. No FR cites them, no SM validates them. "Learning through use" and "layered depth" especially feel like they should generate at least one testable consequence somewhere.

### Findings

- **medium** Design invariants are decorative (§1) — "layered depth" and "learning through use" are stated as operative constraints but generate zero FRs or SMs. Either trace them to concrete behavior (e.g., "layered depth → Cheat Sheet has a 'more detail' expand per rule that shows the Rulebook excerpt") or demote them to "design philosophy" phrasing so readers don't expect traceable consequences. *Fix:* add one FR or NFR consequence per invariant, or relabel them as philosophy, not constraints.
- **low** §0 references a "full MoSCoW breakdown" in the brief addendum, but the addendum is in the brief file, not here. This is fine given the explicit forward-reference model, but a one-line summary of the MoSCoW disposition in §6.2 would make Out of Scope more self-contained. *Fix:* optional — add "(Could Have per brief MoSCoW)" labels to §6.2 items that don't already have them.

---

## 3. Strategic coherence — adequate

The thesis ("close the gap between opening a box and actually playing") is crisp and the feature arc is coherent: Collection → Generation Pipeline → QR Room → Session Log. Each section directly serves the thesis.

SM-4 ("Host does not consult external rulebooks during play") is the best metric in the document — it directly validates the core proposition in observable behavior. SM-C1 as a counter-metric is excellent. SM-2 ("Content reaches Published state after one review pass") is the weakest: "achieved for at least one game" is a floor so low it validates nothing about typical pipeline quality.

The design invariants (§1) are not validated by any SM, which means they cannot be falsified. If "PDF-authoritative" is a real constraint, there should be at least one metric or consequence that would fail if it were violated.

### Findings

- **medium** SM-2 target is too weak (§10) — "achieved for at least one game in the collection" means a single lucky generation validates the pipeline. *Fix:* raise to "at least 3 of 5 games reach Published state on first generation pass without rejection" — this tests the generation pipeline's actual reliability.
- **medium** Design invariants have no corresponding SMs — "PDF-authoritative" and "unobtrusive" are stated as constraints but there is no observable metric that would catch a violation. *Fix:* add SM-6 "Rulebook PDF is the only authoritative rules source used during a Session — no external URL is opened to resolve a rules dispute" (observable at game night, validates FR-8 + the invariant).
- **low** "Learning through use" invariant has no downstream trace — it appears to imply something about session history being surfaced contextually over time, but nothing in the PRD operationalizes it. *Fix:* either trace to a deferred FR or remove it.

---

## 4. Done-ness clarity — adequate

The "Consequences (testable)" structure is consistently applied and mostly works. Most consequences are genuinely testable. A few exceptions:

**Hidden architectural requirement:** FR-14's third consequence — "Guests currently on the Room page see a 'session ended' notice without needing to refresh" — silently mandates a real-time push mechanism (WebSocket, SSE, or long-polling). This is a non-trivial architectural decision buried in a bullet point. The architect will hit this and need to make a significant choice (WebSocket adds state, SSE is simpler, polling is simplest but adds latency). It should surface as an OQ or a technical assumption.

**Vague criterion:** FR-13 — "Content scrolls smoothly; no pagination required." "Scrolls smoothly" is not testable. It should read: "Content is rendered as a single scrollable document; no JavaScript-powered pagination or virtualization is applied."

**Ambiguous Guest access:** FR-3 states the PDF viewer is "accessible on both desktop (Host) and mobile (Guest, for Rulebook access if navigated directly)." FR-13 (Room page) only exposes Quick-start Guide and Cheat Sheet to Guests. These contradict each other: can a Guest access the Rulebook PDF by directly navigating to its URL? If yes, that needs to be a consequence in FR-12 or a NON-GOAL. If no, FR-3's "(Guest, for Rulebook access if navigated directly)" should be removed or scoped.

### Findings

- **critical** FR-14 hides a real-time push requirement — "Guests see session-ended notice without refreshing" implies WebSocket/SSE. This will surprise architecture and drive a non-trivial implementation choice. *Fix:* add ASSUMPTION A-15 "Session end notification uses SSE (server-sent events); degradation path if unsupported is guest sees 'ended' on next manual refresh," plus OQ-7 "SSE vs polling for session end notification."
- **high** FR-3 vs FR-12/FR-13 Guest Rulebook access contradiction — is the PDF accessible to Guests or Host-only? *Fix:* if Guests cannot access the Rulebook directly (most likely intent), remove "(Guest, for Rulebook access if navigated directly)" from FR-3 and add a NON-GOAL note. If they can, add a consequence to FR-12.
- **medium** "Scrolls smoothly" in FR-13 is not testable. *Fix:* replace with "rendered as a single scrollable document by the browser's native scroll; no JS virtualization or custom pagination."
- **low** FR-5 "the Host is warned" is underspecified — what UI element? *Fix:* "a confirmation modal is shown before triggering Generation" or similar.

---

## 5. Scope honesty — strong

This is the PRD's second strongest dimension. §5 Non-Goals lists 7 explicit exclusions, all well-reasoned. §6.2 Out of Scope is detailed, version-tagged (v1.1 vs Could Have), and includes a `[NOTE FOR PM]` on the highest-value v1.1 item (content quality voting). The Assumptions Index in §12 covers 14 assumptions, all with a status column indicating whether they are unvalidated vs. design decisions.

One gap: several architectural choices that carry real scope implications are not assumption-tagged. The LAN network topology (single WiFi segment? can guest be on a separate guest network?) affects FR-12's LAN-served claim and has no assumption. LLM token limits are not bounded — a very large rulebook (e.g., Twilight Imperium 4th ed.) could hit API context limits, and this is not flagged.

### Findings

- **medium** No assumption about LAN topology (FR-12) — the QR Room model assumes all Guests are on the same network segment as the NAS. A guest-network-separated WiFi would break it. *Fix:* add ASSUMPTION A-15 "all guests are on the same LAN segment as the NAS; guest WiFi isolation would require router configuration."
- **medium** No assumption about LLM context window limits (FR-5/FR-6) — large rulebooks (Twilight Imperium: ~100K tokens) may exceed provider context windows. No cap or chunking strategy is mentioned. *Fix:* add ASSUMPTION A-16 "Rulebook text extraction fits within the chosen provider's context window; for v1, games with rulebooks estimated >80K tokens may require chunking (deferred)."
- **low** A-14 is redundant with A-7 — A-14 ("Room URL is short and pronounceable") just restates A-7. *Fix:* remove A-14; in UJ-2 replace `[ASSUMPTION: Room URLs are short and pronounceable]` with `[see A-7]`.

---

## 6. Downstream usability — adequate

**Glossary:** 13 terms, complete for the domain. All domain nouns in FRs resolve. Play Mode is defined. Pipeline State definitions are clean.

**ID continuity:** FR-1–18 contiguous. UJ-1–4 contiguous. SM-1–5 + SM-C1 contiguous. NFR-1–6 contiguous. A-1–14 contiguous. Clean.

**Cross-references:** FR-10 → FR-14, FR-15 → FR-10, FR-17 → FR-4 all resolve correctly. UJ-to-FR links are present at the section-description level ("Realizes UJ-X") but individual FRs don't back-reference their UJs — minor friction for epic decomposition but not a blocker.

**State machine gap:** §3 defines three Pipeline States (Draft, Published, Rejected) but does not define all valid transitions. The undefined cases:
- Can Published content be directly un-published or demoted?
- What is the state of Content when a Rulebook is replaced and existing Published content remains? (FR-2 answers this verbally: "Published Content is not affected" — but there's no state name for "Published but potentially stale.")
- Can the Host reject Published content directly, or must they generate a new Draft first?

This ambiguity will force the architect to invent a state model that may not match the PRD author's intent.

**Glossary ordering:** The Glossary is at §3, but §2 (Target User / UJs) uses Glossary terms before they are defined. For a 488-line doc this causes no real friction, but moving Glossary to §1 or §2 would make the document fully top-down readable.

### Findings

- **high** Pipeline State transition table missing (§3) — valid transitions between Draft/Published/Rejected are implied but not specified. "Un-publish," "stale-but-published," and "reject-after-publish" are all undefined. *Fix:* add a 3×3 state transition table or a state diagram description to §3, with explicit "not permitted" cells.
- **medium** UJ-to-FR back-references absent at FR level — FRs don't cite which UJs they realize. *Fix:* add a one-line "Realizes: UJ-X" under each FR heading, mirroring the section-level pattern already used.
- **low** Glossary at §3 comes after §2 UJs which use Glossary terms — minor readability friction. *Fix:* move Glossary to §2 (swap with Target User/UJs section), or add a forward-reference note at the top of §2.

---

## 7. Shape fit — strong

For a personal tool feeding architecture and epics, this PRD is well-calibrated. It is thorough without being bureaucratic. The brief-forward reference model (§0: "this PRD does not duplicate the brief; it extends it") elegantly avoids document bloat. The decision to omit competitive analysis, persona narrative padding, and design mockups is correct for this context.

The 18 FRs are a reasonable scope for a v1 with 4 feature areas. The UJs are appropriately detailed (edge cases, entry/exit states) without being exhaustive. The assumption index adds rigor without overhead.

The one formalization that slightly overshoots: §2.2 "Non-Users (v1)" as a named subsection is common in team-facing PRDs to defend scope in stakeholder review, but for a solo project it reads as light scaffolding. It's harmless and the content is useful for alignment, so this is a non-issue.

The document is architecture-ready once the FR-14 push requirement and the Pipeline State transition gap are addressed. Epic decomposition maps cleanly onto the four feature areas (§4.1–4.4).

### Findings

- **low** §2.2 Non-Users is mild over-formalization for solo context, but content is genuinely useful for scope anchoring. No action needed.

---

## Mechanical notes

**Glossary drift:** None found. All domain nouns in FRs appear in §3. No Glossary terms are defined but unused.

**ID continuity:** All ID series are contiguous. No gaps found (FR-1–18, UJ-1–4, SM-1–5+C1, NFR-1–6, A-1–14).

**Assumptions Index roundtrip:** All `[ASSUMPTION: ...]` inline tags in the body map to a row in §12. No orphaned assumptions found. A-14 is redundant with A-7 (see §5 finding). The new assumptions flagged in this review (LAN topology, LLM context limits, SSE/push) are not yet indexed.

**OQ roundtrip:** All §11 questions correspond to a real unresolved issue in the FRs. OQ-1 maps to FR-7. OQ-2 maps to FR-10. OQ-3 maps to FR-11/A-7. OQ-4 maps to §6.1/FR-13. OQ-5 maps to §6.1/A-12. OQ-6 maps to FR-2. No dangling OQs.

**UJ edge cases:** UJ-1 edge case (expired API key) is thorough. UJ-2 edge case (QR scan failure) is handled. UJ-3 and UJ-4 have no edge cases — UJ-4 in particular (session logging during a party wind-down) could document the "Host forgets to log until days later" case, but this is minor for the current scope.

---

## Priority fix list

| Severity | Finding | Location | Fix summary |
|---|---|---|---|
| critical | Hidden real-time push requirement | FR-14 | Add ASSUMPTION for SSE + OQ-7 |
| high | Pipeline State transition table missing | §3 | Add state transition table |
| high | FR-3 vs FR-13 Guest Rulebook access contradiction | FR-3, FR-12 | Clarify or remove Guest Rulebook access from FR-3 |
| high | OQ-2, OQ-4, OQ-5, OQ-6 lack resolution gates | §11 | Add "Decision needed before X" to each |
| medium | Design invariants untraceable | §1 | Trace each to ≥1 FR/SM, or relabel as philosophy |
| medium | SM-2 target too weak | §10 | Raise to ≥3/5 games published on first pass |
| medium | LAN topology and LLM context limit assumptions missing | FR-12, FR-5 | Add A-15, A-16 |
| medium | "Scrolls smoothly" untestable | FR-13 | Replace with specific criterion |
| low | A-14 redundant with A-7 | §12 | Remove A-14 |
