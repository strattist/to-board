---
title: 'Add OpenAI as a Supported Provider'
type: 'feature'
created: '2026-09-29'
status: 'done'
review_loop_iteration: 0
baseline_commit: '56357ed14f5d59266f00a721d45433d06de7315b'
story_id: '2-6'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Host settings and generation currently support Anthropic and Google only, preventing a Host with an OpenAI key from generating the same paired game reference content.

**Approach:** Add OpenAI to the existing provider settings and generation path. Reuse the current encrypted singleton settings, HTTP client, sanitized errors, and Draft/Published pipeline.

## Boundaries & Constraints

**Always:** Keep Settings Host-protected. Encrypt keys with the existing Fernet helper and return only `{provider, configured}`. Send the fixed generation instructions and locally extracted Rulebook text to OpenAI; never upload the PDF or send unrelated Game data. Send credentials only in the Authorization header. Set Responses API `store` to false. Keep provider/model configuration server-side. Provider changes preserve every Content field; generation failures preserve the Published pair and follow existing state recovery.

**Ask First:** Changes to authentication, credential storage, public settings response shape, database schema, or a new runtime dependency.

**Never:** Add local inference, expose or log API keys, put keys in URLs, send raw PDFs, or mutate Draft/Published Content when saving Settings.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Save OpenAI settings | Authenticated Host, OpenAI, non-empty key | Persist provider and encrypted key; return only provider/configured; Content is unchanged | Standard 422 for invalid input; no key in response |
| Generate successfully | OpenAI selected; extracted text exists | Send instructions and extracted text using configured model; parse both Markdown fields into existing Draft flow | Reject absent, incomplete, or malformed response with sanitized OpenAI error |
| Provider failure | Rejected key, rate limit, unavailable API, or invalid model | Keep prior Published pair available | Return provider-specific safe error; do not persist credentials, request URLs, raw response bodies, or provider exception text |
| Unauthorized settings request | Guest or unauthenticated caller | Reveal or change no provider/key state | Existing Host authentication response |

</frozen-after-approval>

## Code Map

- `_bmad-output/implementation-artifacts/epic-2-context.md` — provider, key, local extraction, Content-state, and privacy invariants.
- `backend/routers/settings.py:10-45`, `backend/models/settings.py:4-7`, `backend/core/crypto.py:13-17` — provider allowlist, safe response, singleton storage, Host protection, and shared Fernet path.
- `backend/core/config.py:5-18`, `docker-compose.yml:11-12`, `.env.example:5-6`, `README.md:25-40` — model override configuration and operator documentation pattern.
- `backend/services/llm.py:12-174` — provider labels, model validation, HTTP dispatch, sanitized errors, and shared JSON-to-Markdown validation.
- `backend/workers/generation.py:29-62`, `backend/services/content.py:22-30,74-99` — extracted-text-only input and existing Draft/Published transitions.
- `frontend/src/lib/api.ts:7-13`, `frontend/src/lib/settings-flow.ts:22-67`, `frontend/src/components/SettingsPage.svelte:43-52` — typed provider contract, key-clearing behavior, and selector.
- `tests/test_app.py:269-328,540-728` — encryption/auth/Content assertions, provider request mocks, sanitized failures, and model overrides; line 302 currently expects OpenAI to be rejected.
- `frontend/tests/interaction-contracts.test.mjs:370-410` — settings request/controller contract; add provider-option coverage.
- `_bmad-output/planning-artifacts/architecture/architecture-to-board-2026-09-07/ARCHITECTURE-SPINE.md:48,163,208` — provider list, configuration invariant, and LLM service description to reconcile with persisted provider selection.

## Tasks & Acceptance

**Execution:**
- [x] `backend/core/config.py`, `backend/routers/settings.py`, `backend/services/llm.py` — allow OpenAI and add a validated environment-configured model; call the Responses API with bearer auth and `store: false`; collect `output_text` from message items and pass complete JSON through the existing pair validator.
- [x] `frontend/src/lib/api.ts`, `frontend/src/components/SettingsPage.svelte` — add OpenAI to the provider type and selector; keep key entry server-only and clear it after save.
- [x] `tests/test_app.py`, `frontend/tests/interaction-contracts.test.mjs` — cover OpenAI settings, request/response shape, success, invalid output, provider errors, key privacy, auth, provider switching, Content preservation, and selector contract.
- [x] `docker-compose.yml`, `.env.example`, `README.md`, `_bmad-output/planning-artifacts/architecture/architecture-to-board-2026-09-07/ARCHITECTURE-SPINE.md` — document `OPENAI_MODEL` and supported providers; state that provider selection is persisted in Settings while model IDs are environment configuration.

**Acceptance Criteria:**
- Given the Host opens Settings, when provider options render, then Anthropic, Google, and OpenAI are selectable and the saved provider loads correctly.
- Given a valid OpenAI key is saved, when the Host reads Settings or inspects a compiled frontend bundle, then only provider/configured is exposed and no key material appears.
- Given OpenAI is selected and extraction is complete, when Host-triggered generation runs, then the configured model receives the fixed instructions and extracted text through the documented Responses API and the result enters the existing Draft state.
- Given output contains multiple non-text items or text content blocks, when parsing completes, then all OpenAI output text is handled without assuming the first output item is the answer; only a complete, non-empty Quick-start and Cheat Sheet pair is accepted.
- Given the Host changes providers, when Settings saves, then all Draft, Rejected, and Published Content fields remain unchanged; given OpenAI generation fails, then the existing recovery path runs and the Published pair remains available.
- Given a Guest or unauthenticated caller accesses Settings, when the request is made, then current Host authentication behavior remains in force and no provider or credential state is disclosed.

## Design Notes

Use OpenAI’s Responses API (`POST https://api.openai.com/v1/responses`) with bearer authentication, `instructions` for the existing generation prompt, and `input` for the Rulebook text. Use a configurable `OPENAI_MODEL`, defaulting to `gpt-6-luna` (the current model catalog’s cost-sensitive option); retain shared model-ID validation. Responses can contain multiple output items, so collect message `output_text` parts rather than indexing the first item. Require a completed response and non-empty JSON fields before using the shared parser. `store: false` avoids the API’s default response storage. References: [text-generation guide](https://developers.openai.com/api/docs/guides/text), [Responses API reference](https://developers.openai.com/api/reference/cli/resources/responses/methods/create), [model catalog](https://developers.openai.com/api/docs/models).

## Verification

**Commands:**
- `rtk uv run --no-cache pytest -q tests/test_app.py` — backend provider, security, and preservation tests pass.
- `rtk npm --prefix frontend run test:contracts` — provider selector and Settings contract pass.
- `rtk npm --prefix frontend run check` — frontend type and Svelte checks pass.

## Suggested Review Order

**Provider request and response**

- Start here to see provider dispatch and shared adapter boundaries.
  [`llm.py:85`](../../backend/services/llm.py#L85)
- The OpenAI request uses extracted text, server-side model configuration, private credentials, disabled storage, and an output cap.
  [`llm.py:123`](../../backend/services/llm.py#L123)
- Safe status handling and response parsing reject provider failures and incomplete output before the shared content parser.
  [`llm.py:138`](../../backend/services/llm.py#L138)

**Host settings**

- The provider allowlist and safe response preserve the Host-only credential contract.
  [`settings.py:11`](../../backend/routers/settings.py#L11)
- The existing Settings selector now includes OpenAI.
  [`SettingsPage.svelte:44`](../../frontend/src/components/SettingsPage.svelte#L44)
- The typed frontend API contract includes the OpenAI provider.
  [`api.ts:7`](../../frontend/src/lib/api.ts#L7)

**Runtime configuration and project documentation**

- The OpenAI model default is server-side, and Compose passes the override into the API container.
  [`config.py:15`](../../backend/core/config.py#L15)
  [`docker-compose.yml:13`](../../docker-compose.yml#L13)
- The environment example and operator guide document OpenAI model setup and the official catalog.
  [`.env.example:7`](../../.env.example#L7)
  [`README.md:46`](../../README.md#L46)
  [`README.md:64`](../../README.md#L64)
- The architecture spine and deck align provider persistence with model environment variables.
  [`ARCHITECTURE-SPINE.md:163`](../planning-artifacts/architecture/architecture-to-board-2026-09-07/ARCHITECTURE-SPINE.md#L163)
  [`architecture-deck.html:655`](../planning-artifacts/architecture/architecture-to-board-2026-09-07/architecture-deck.html#L655)

**Verification and workflow records**

- Backend tests cover the Responses API request, safe provider failures, and Compose model wiring.
  [`test_app.py:700`](../../tests/test_app.py#L700)
  [`test_app.py:962`](../../tests/test_app.py#L962)
- Frontend interaction contracts check the provider selector and Settings request.
  [`interaction-contracts.test.mjs:240`](../../frontend/tests/interaction-contracts.test.mjs#L240)
- The review recorded pre-existing follow-up work for focused future changes.
  [`deferred-work.md:113`](deferred-work.md#L113)
- Sprint tracking marks the story ready for review.
  [`sprint-status.yaml:52`](sprint-status.yaml#L52)
- Ignore rules expose the environment template while keeping secret files ignored.
  [`.gitignore:14`](../../.gitignore#L14)

### Review Findings

- [x] [Review][Patch] Recognize OpenAI `insufficient_quota` error types as billing limits [backend/services/llm.py:140]
- [x] [Review][Patch] Verify persisted OpenAI settings reach the generation adapter [tests/test_app.py:428]
