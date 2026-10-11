---
title: 'Fix Anthropic Model Configuration'
type: 'bugfix'
created: '2026-09-21'
status: 'done'
review_loop_iteration: 0
baseline_commit: '8fb9140bb32ac3ef2f80ace9b78af4bc5de4adb9'
context:
  - '/home/baptiste/work/to-board/_bmad-output/implementation-artifacts/epic-2-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Anthropic generation currently sends a retired hardcoded model alias, causing the provider to return an HTTP error that is displayed as “Anthropic returned an invalid response.” The existing runtime model settings are ignored, and Docker Compose does not pass model overrides into the API container.

**Approach:** Use the configured `ANTHROPIC_MODEL` value for Anthropic requests, set a currently active default, pass model overrides through Compose, and preserve the existing secret-safe error boundary while making model/status failures actionable.

## Boundaries & Constraints

**Always:** Model selection remains runtime configuration, not persisted with API keys; the API key stays in the existing Fernet-encrypted field and is sent only in the provider header; error messages never include keys, response bodies, or request URLs; existing Draft, Rejected, and Published Content behavior remains unchanged; Google model configuration must use the same runtime-config pattern when touched.

**Ask First:** Changing provider scope, adding a model picker to the UI, or changing the encrypted settings schema.

**Never:** Restore retired Anthropic aliases, hardcode a model in the request adapter, add local LLM inference, or expose model/API credentials to Guests or the frontend bundle.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|-----------------------------|----------------|
| Default model | No model override; valid Anthropic key | Request uses the active configured default | Provider response is parsed into the existing content pair |
| Override model | `ANTHROPIC_MODEL` set in host `.env` and Compose | Container receives the override and request uses it | No source-code change required to switch models |
| Retired/unknown model | Provider returns 404 or model error | Generation rolls back safely and Host sees a clear Anthropic model/provider error | No raw response or credential material is persisted |
| Valid response | Anthropic returns the Messages response shape with JSON content | Draft Quick-start Guide and Cheat Sheet are saved as before | Malformed content remains a sanitized provider error |

</frozen-after-approval>

## Code Map

- `backend/core/config.py:5-18` -- cached runtime settings already define model fields; update the active Anthropic default.
- `backend/services/llm.py:31-89` -- provider adapter currently hardcodes both model identifiers and collapses HTTP failures into “invalid response.”
- `backend/workers/generation.py:24-40` -- preserves pipeline rollback and sanitized persistence; do not leak underlying provider exceptions.
- `docker-compose.yml:4-10` -- explicit environment pass-through required for model overrides.
- `.env.example:1-6` and `README.md:20-42,117-126` -- document valid model overrides and safe model discovery.
- `tests/test_app.py:300-364` -- existing mocked provider seam; extend request assertions and Anthropic failure coverage.

## Tasks & Acceptance

**Execution:**
- [x] `backend/core/config.py` -- set an active Anthropic default while retaining environment override support.
- [x] `backend/services/llm.py` -- use configured Anthropic/Google model values and map model/status failures to safe provider-specific errors.
- [x] `docker-compose.yml`, `.env.example`, `README.md` -- pass and document model overrides and how to inspect provider model IDs without exposing keys.
- [x] `tests/test_app.py` -- verify configured model request bodies, successful parsing, retired-model/status errors, and secret-safe rollback behavior.

**Acceptance Criteria:**
- Given no `ANTHROPIC_MODEL` override, when generation runs with a valid key, then the request uses the active default model rather than the retired alias.
- Given `ANTHROPIC_MODEL` is set in the host `.env`, when the Compose API service starts, then the container receives it and generation uses that exact value.
- Given Anthropic returns a model-not-found or other non-success response, when generation fails, then the Host sees a clear sanitized provider/model error and existing Published Content remains available.
- Given Anthropic returns a valid Messages response, when its text contains the expected JSON pair, then generation stores the Draft exactly as before.
- Given model configuration is changed, when the frontend or Guest routes are used, then no model value, API key, or provider response body is exposed.

## Design Notes

Model IDs are operational configuration because providers retire aliases independently of application releases. The default should be an active Anthropic model at implementation time, while operators can switch models by editing `.env` and recreating the API container. A model/status error should distinguish configuration/provider availability from malformed generated content without revealing raw HTTP details.

## Verification

**Commands:**
- `rtk uv run --no-cache pytest -q` -- expected: all backend tests pass, including model selection and sanitized failure regression tests.
- `npm --prefix frontend run check` -- expected: no frontend diagnostics.
- `npm --prefix frontend run test:contracts` -- expected: frontend contract tests pass.
- `npm --prefix frontend run build` -- expected: production bundle succeeds and contains no credentials or provider response bodies.
- `docker compose config --quiet` -- expected: Compose accepts model environment interpolation.

## Suggested Review Order

**Runtime model selection and provider boundary**

- Start with the adapter to see runtime model lookup, request construction, and safe status mapping.
  [`llm.py:45`](../../backend/services/llm.py#L45)

- Confirm the active default remains environment-overridable and separate from persisted API-key settings.
  [`config.py:5`](../../backend/core/config.py#L5)

- Verify provider errors reach the Host without exposing credentials or response bodies.
  [`generation.py:24`](../../backend/workers/generation.py#L24)

**Deployment and operator configuration**

- Check Compose explicitly forwards host model overrides into the API container.
  [`docker-compose.yml:4`](../../docker-compose.yml#L4)

- Review the operator instructions for changing models and consulting provider lifecycle documentation.
  [`README.md:44`](../../README.md#L44)

**Regression coverage**

- Follow adapter tests for defaults, overrides, successful parsing, status failures, and secret-safe messages.
  [`test_app.py:362`](../../tests/test_app.py#L362)

- Confirm worker persistence preserves published content when Anthropic reports an unavailable model.
  [`test_app.py:331`](../../tests/test_app.py#L331)
