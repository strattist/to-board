---
title: 'Generate Draft Content from a Rulebook'
type: 'feature'
created: '2026-09-26'
status: 'done'
review_loop_iteration: 0
baseline_commit: '1ecf1ddb7b13f40ba99c6dd5be750ad6098d1f71'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Story 2.3’s backend generation path and paired Draft persistence already exist, but Game Detail does not know whether an API key is configured and uses a generic confirmation even when it will discard an existing Draft. During regeneration, the retained Published pair also cannot start a new Session because session readiness is tied to the transient pipeline state.

**Approach:** Complete the Host generation flow by exposing only a safe configured/not-configured value, showing specific prerequisite reasons and a Draft replacement confirmation, and keeping an existing Published pair usable while a new Draft is generated. Reuse the existing Content state machine, async worker, provider adapters, and low-quality extraction acknowledgment.

## Boundaries & Constraints

**Always:** Keep generation Host-authenticated and explicitly triggered. Require a completed, safely contained extracted-text cache and configured provider key; send extracted text only, never PDF bytes. Keep provider credentials server-side and encrypted. Persist the Quick-start Guide and Cheat Sheet together in the single Content row; keep Published fields intact during generation and failure. Permit Preview, active Rooms, and starting a Session whenever the complete Published pair exists, regardless of an in-progress Draft generation. Continue to recover interrupted generation to its recorded predecessor and surface safe errors.

**Ask First:** Any database migration, new pipeline state, additional provider, or change to the provider prompt/response contract.

**Never:** Expose keys, filesystem paths, or PDF data in the Game response or frontend; generate on page load; use a local model; publish generated content automatically; or replace the existing provider and Content architecture.

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Missing prerequisite | No Rulebook, extraction incomplete, or no configured key | Detail disables generation and explains the specific missing prerequisite; direct trigger is rejected before starting work | Standard 422 response; no provider task |
| Replace Draft | Eligible Game with existing Draft; Host confirms replacement | Confirmation states the Draft will be replaced; Cancel makes no request; confirmation starts async work and retains any Published pair for Preview, Rooms, and new Sessions | Request errors are shown without exposing secrets |
| Provider result | Valid pair or failed/invalid provider response | Valid pair is stored together as Draft; failure returns to the recorded predecessor and leaves Published fields unchanged | Safe provider error; no partial pair |

</frozen-after-approval>

## Code Map

- `_bmad-output/planning-artifacts/epics.md:435-480` -- Story 2.3 source intent and acceptance criteria.
- `_bmad-output/implementation-artifacts/epic-2-context.md` -- Epic constraints and cross-story dependencies; Story 2.1 supplies credentials and 2.2 supplies extraction.
- `backend/routers/games.py:33-78,230-256` -- Game DTO and Host generation route. The route already validates extraction/key/confirmation, commits `generating`, and schedules the worker; add only a non-secret configuration boolean to the DTO.
- `backend/services/content.py:21-26,73-99` -- state transitions, paired Draft save, predecessor restoration, and Published preservation. Keep these as the single mutation owner.
- `backend/workers/generation.py:20-62` and `backend/services/llm.py:73-174` -- current extracted-path read, async provider call, output validation, safe failure handling, and atomic pair persistence; reuse these paths.
- `backend/db/init.py:32-78` -- startup recovery of interrupted generation to `prior_pipeline_state`.
- `backend/services/sessions.py:17-27`, `backend/routers/room.py:18-21`, and `backend/routers/games.py:276-280` -- Session readiness currently requires `pipeline_state == published`; Room and Preview already read the retained Published fields.
- `frontend/src/lib/api.ts:33-38` and `frontend/src/lib/generation-flow.js:1-15` -- generation request/type and reusable prerequisite gate.
- `frontend/src/components/Detail.svelte:40-67,107-122,206-247` -- prerequisite copy, generic confirmation, and Preview/Session controls. Reuse existing confirmation, busy, error, and status patterns.
- `tests/test_app.py:202-395,1425-1475` and `frontend/tests/interaction-contracts.test.mjs:25-35,68-74,128-135` -- current prerequisite, provider, pair persistence, secret-safety, and client-contract coverage; extend for identified gaps.

## Tasks & Acceptance

**Execution:**
- [x] `backend/routers/games.py`, `frontend/src/lib/api.ts` -- expose and type only whether a provider key is configured, so Detail can gate generation without receiving a secret.
- [x] `frontend/src/lib/generation-flow.js`, `frontend/src/components/Detail.svelte` -- disable generation with distinct no-Rulebook, incomplete-extraction, and missing-key reasons; confirm Draft replacement explicitly and leave state untouched on cancel.
- [x] `backend/services/sessions.py`, `frontend/src/components/Detail.svelte` -- base Session and Preview availability on a complete Published pair, not `pipeline_state`, so Published Content remains usable during regeneration.
- [x] `tests/test_app.py`, `frontend/tests/interaction-contracts.test.mjs` -- cover missing-key gating/direct rejection, replacement cancel/confirm, Published access during generation, paired success, and safe failure preservation.

**Acceptance Criteria:**
- Given a Game has no Rulebook, incomplete extraction, or no configured provider key, when the Host views Game Detail, then generation is disabled with the matching reason; a direct trigger is rejected and does not start a provider call.
- Given prerequisites are met, when the Host confirms generation, then the API commits `generating` and returns without waiting for the provider; the worker reads only `Rulebook.extracted_text_path` and the Host sees the busy state and then “Needs review” on success.
- Given an existing Draft, when the Host starts regeneration, then the confirmation says the Draft will be replaced; cancelling sends no request, and confirming preserves any Published pair for Preview, Guest Rooms, and Session start.
- Given a provider returns two valid Markdown fields, when the worker completes, then both Draft fields are saved in the one Content row and the pipeline reaches `draft`.
- Given a provider fails or returns invalid content, when failure handling completes, then the Host sees a safe error, the pipeline returns to its recorded predecessor, and any Published pair remains available and unchanged.
- Given the process restarts while generation is in progress, when startup recovery runs, then state returns to `prior_pipeline_state` and the Host can retry.

## Spec Change Log

## Design Notes

`pipeline_state` describes the current operation; it does not determine whether Published content exists. The published Markdown pair remains authoritative during regeneration. Session eligibility should therefore be based on both Published fields being present, matching Guest Room and Host Preview reads.

## Verification

**Commands:**
- `rtk uv run --no-cache pytest -q tests/test_app.py` -- backend acceptance and regression coverage passes.
- `rtk npm --prefix frontend run check` -- Svelte and TypeScript checks pass.
- `rtk npm --prefix frontend run test:contracts` -- frontend behavior and API contracts pass.
- `rtk npm --prefix frontend run build` -- production frontend bundle succeeds.

## Suggested Review Order

**Game/API boundary**

- The Game DTO adds provider readiness and omits stored file paths.
  [`games.py:33`](../../backend/routers/games.py#L33)

- The frontend type exposes the safe readiness flag to Detail.
  [`api.ts:38`](../../frontend/src/lib/api.ts#L38)

**Host generation flow**

- Detail maps the payload into distinct Rulebook, extraction, and provider gates.
  [`Detail.svelte:49`](../../frontend/src/components/Detail.svelte#L49)

- The handler refreshes eligibility and serializes repeat clicks before confirmation.
  [`Detail.svelte:113`](../../frontend/src/components/Detail.svelte#L113)

- Confirmation names Draft replacement, Published retention, and cloud generation.
  [`generation-flow.js:15`](../../frontend/src/lib/generation-flow.js#L15)

- Missing provider guidance links directly to Settings.
  [`Detail.svelte:276`](../../frontend/src/components/Detail.svelte#L276)

**Published access**

- Session readiness depends on both Published documents during regeneration.
  [`sessions.py:17`](../../backend/services/sessions.py#L17)

- Detail keeps Preview and Session actions available with Published Content.
  [`Detail.svelte:90`](../../frontend/src/components/Detail.svelte#L90)

**Verification**

- The API lifecycle test verifies Published preservation through worker failure.
  [`test_app.py:459`](../../tests/test_app.py#L459)

- Route tests reject incomplete pairs for Session, Preview, and Guest Room.
  [`test_app.py:780`](../../tests/test_app.py#L780)

- Interaction contracts cover payload mapping, confirmation wiring, and busy actions.
  [`interaction-contracts.test.mjs:36`](../../frontend/tests/interaction-contracts.test.mjs#L36)
