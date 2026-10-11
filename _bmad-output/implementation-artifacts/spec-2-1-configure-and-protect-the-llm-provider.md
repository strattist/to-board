---
title: 'Configure and Protect the LLM Provider'
type: 'feature'
created: '2026-09-21'
status: 'done'
review_loop_iteration: 0
baseline_commit: '8fb9140bb32ac3ef2f80ace9b78af4bc5de4adb9'
context:
  - '/home/baptiste/work/to-board/_bmad-output/implementation-artifacts/epic-2-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The Host needs to configure a supported cloud LLM provider without exposing the API key, while the existing Settings surface and generation path need consistent error handling and test coverage.

**Approach:** Keep provider configuration in the singleton `AppSettings` row, encrypt keys with the existing Fernet helper before persistence, expose only provider/configured state, and harden the Host Settings UI and generation error path around those contracts.

## Boundaries & Constraints

**Always:** Only `anthropic` and `google` are accepted; the submitted key is encrypted with the single `SECRET_KEY`-backed Fernet implementation before SQLite writes; Settings APIs require Host authentication; responses, frontend source, logs, and persisted provider errors contain neither plaintext nor ciphertext; updating settings does not mutate Content rows; provider failures identify the selected provider without leaking request details.

**Ask First:** Changing the supported provider list, encryption format, authentication boundary, or adding a new persistence location.

**Never:** Send keys to the frontend, expose Settings on Guest routes, add local LLM inference, or change published/draft Content as a side effect of configuration.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|----------------------------|----------------|
| Save settings | Authenticated Host submits supported provider and non-empty key | Encrypt and persist singleton row; return provider and configured=true | Validation error for unsupported provider or empty key |
| Read settings | Host requests Settings | Return only provider and configured boolean | Unauthenticated request is rejected |
| Replace key | Existing Content plus new provider/key | Replace encrypted settings only; all Content fields remain unchanged | No partial Content mutation |
| Provider rejection | Generation uses invalid stored key/provider response | Preserve Published Content and surface sanitized provider-specific error | Never persist URL, key, ciphertext, or raw request details |

</frozen-after-approval>

## Code Map

- `backend/models/settings.py:4-7` -- singleton `AppSettings` schema; encrypted key is the only persisted secret field.
- `backend/core/crypto.py:5-17` -- centralized Fernet construction plus encrypt/decrypt helpers; reuse without a second crypto path.
- `backend/routers/settings.py:9-29` -- Host-protected GET/PUT, input validation, and `safe()` response contract to harden and test.
- `backend/services/llm.py:8-35` -- server-side key decryption and provider dispatch; sanitize provider failures and retain provider-specific context.
- `backend/workers/generation.py:10-37` -- catches generation failures and restores pipeline state; preserve Published fields while recording safe errors.
- `backend/routers/games.py:207-221` -- generation prerequisite/auth boundary that consumes AppSettings.
- `frontend/src/lib/api.ts:1-31` -- shared authenticated fetch/error abstraction; add typed Settings calls here.
- `frontend/src/components/SettingsPage.svelte:1` -- existing Settings form; route requests through the API helper and handle loading/save failures safely.
- `tests/test_app.py:31-45,854-864` -- fixture cleanup and generation tests; extend with isolated Settings security and preservation coverage.
- `frontend/tests/interaction-contracts.test.mjs:73-` -- static/mocked frontend contract-test conventions for Settings UI behavior.

## Tasks & Acceptance

**Execution:**
- [x] `backend/routers/settings.py`, `backend/services/llm.py`, `backend/workers/generation.py` -- enforce safe settings responses and sanitized provider-specific failure handling without changing Content preservation semantics.
- [x] `frontend/src/lib/api.ts`, `frontend/src/components/SettingsPage.svelte` -- add typed Settings API calls, authenticated error handling, loading/disabled states, and retain the key only until a successful save.
- [x] `tests/test_app.py` -- add Host authorization, encryption/non-disclosure, replacement preservation, validation, and provider-error tests.
- [x] `frontend/tests/interaction-contracts.test.mjs` -- cover Settings API usage and non-secret UI state.

### Review Findings

- [x] [Review][Patch] Settings validation can echo a submitted API key in FastAPI's default 422 body [backend/routers/settings.py:10-12]
- [x] [Review][Patch] Local extraction, file, database, and draft-save failures are mislabeled as provider request failures [backend/workers/generation.py:25-39]
- [x] [Review][Patch] Network timeouts and transport errors are reported as invalid provider responses [backend/services/llm.py:71-97]
- [x] [Review][Patch] Arbitrary `ProviderError` messages are persisted without enforcing the safe-message contract [backend/workers/generation.py:33-39]
- [x] [Review][Patch] Provider safety blocks and empty content responses collapse into a generic invalid-response message [backend/services/llm.py:88-108]
- [x] [Review][Patch] `GOOGLE_MODEL` is interpolated into the request URL without model-identifier validation [backend/services/llm.py:74-81]
- [x] [Review][Patch] Settings remains writable with default values after the initial settings load fails [frontend/src/components/SettingsPage.svelte:13-60]
- [x] [Review][Patch] Settings Save is not a form submission, so pressing Enter in the API-key field does nothing [frontend/src/components/SettingsPage.svelte:45-60]
- [x] [Review][Patch] Settings load/save lifecycle has no executed component-level test [frontend/tests/interaction-contracts.test.mjs:48-55]
- [x] [Review][Patch] Anthropic HTTP-200 malformed payloads lack adapter-level coverage [tests/test_app.py:403-477]
- [x] [Review][Patch] Compose model overrides lack end-to-end environment/interpolation verification [docker-compose.yml:11-12]
- [x] [Review][Patch] The README's `export ANTHROPIC_API_KEY=...` example contradicts its shell-history safety warning [README.md:59-66]

**Acceptance Criteria:**
- Given an authenticated Host submits a supported provider and key, when saving succeeds, then the database contains ciphertext only and the response reports provider/configured state without either key form.
- Given Settings data is requested by a Guest or unauthenticated caller, when the request is made, then it is rejected and no provider or key information is returned.
- Given existing Draft, Rejected, or Published Content, when the Host replaces provider/key settings, then every Content field remains unchanged and future generation uses the replacement configuration.
- Given a provider rejects a generation request, when the failure is recorded or displayed, then it names the provider, preserves existing Published Content, and contains no secret or request URL.

## Design Notes

Provider failures should be mapped at the service boundary to stable, calm messages (for example, “Anthropic rejected the API key”) while retaining the existing pipeline rollback behavior. The Google key must not appear in a request URL that could be copied into an exception string; prefer a secret-bearing header where the provider supports it, or redact before persistence.

## Verification

**Commands:**
- `python3 -m pytest` -- expected: all backend tests pass, including Settings security and preservation cases.
- `npm --prefix frontend run check` -- expected: Svelte/TypeScript checks pass.
- `npm --prefix frontend run test:contracts` -- expected: frontend contract assertions pass.
- `npm --prefix frontend run build` -- expected: production bundle succeeds and contains no API key literals.

## Suggested Review Order

**Settings boundary**

- Host-only update validates input, encrypts the key, and returns non-secret state.
  [`settings.py:31`](../../backend/routers/settings.py#L31)

- Shared API helpers keep Settings requests authenticated and strongly typed.
  [`api.ts:7`](../../frontend/src/lib/api.ts#L7)

**Provider security and failure handling**

- Provider adapters keep secrets in headers and convert failures into safe messages.
  [`llm.py:31`](../../backend/services/llm.py#L31)

- Background generation preserves published content while persisting sanitized failures.
  [`generation.py:33`](../../backend/workers/generation.py#L33)

**Host interaction**

- Settings loading and saving expose calm states without retaining failed credentials.
  [`SettingsPage.svelte:13`](../../frontend/src/components/SettingsPage.svelte#L13)

**Verification and tracking**

- Backend tests cover encryption, authorization, preservation, provider transport, and redaction.
  [`test_app.py:204`](../../tests/test_app.py#L204)

- Frontend contracts verify Settings API requests and non-secret UI structure.
  [`interaction-contracts.test.mjs:51`](../../frontend/tests/interaction-contracts.test.mjs#L51)

- Sprint tracking records Story 2.1 as actively implemented under Epic 2.
  [`sprint-status.yaml:46`](sprint-status.yaml#L46)
