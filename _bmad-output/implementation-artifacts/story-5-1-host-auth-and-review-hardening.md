---
title: 'Host auth and review hardening'
type: 'feature'
created: '2026-09-12'
status: 'draft'
story_id: '5-1'
---

# Story 5-1: Host auth and review hardening

## Summary

This story tracks the remaining production-readiness work identified during the build review: finish the Host auth boundary, make the app behave correctly under real Authentik/OIDC conditions, and close the remaining gaps in regression coverage and verification.

## Problem

The initial build foundation is working in the local test environment, but the review surfaced several remaining risks that must be addressed before the app is ready to run as a real Host app. The main issues are: Host auth is not fully integrated end-to-end; stale background jobs can still race with rule updates; the SSE/Room closure contract and session semantics need stronger verification; and the test suite does not yet cover the production-facing auth and deployment behaviors.

## Approach

Harden the app along the review findings without expanding scope beyond the approved architecture and PRD. Focus on the production guardrails first: end-to-end Host auth and route protection, stale/background-job safety, and evidence-backed verification of the accepted flows.

## Acceptance Criteria

- Given a valid Authentik OIDC token, when the Host calls a protected route, then the request succeeds only when the issuer, audience, and subject checks pass and the token is validated against the configured JWKS.
- Given a missing, expired, or invalid Host token, when the user requests protected Host routes, then the API responds with the expected 401 and does not expose internal state.
- Given a stale extraction or generation job observes a replaced Rulebook, when it finishes, then it exits without mutating the current Game or writing stale Draft content.
- Given a Session is ended, when connected Guests are listening on the room SSE stream, then the `session-ended` event is received without a refresh.
- Given the app is started on a real deployment, when the runtime configuration is loaded, then Host routes enforce the auth boundary and Guest routes remain anonymous without persisting guest identity.
- Given the review findings are addressed, when the verification suite runs, then the critical auth, content, session, and stale-worker scenarios are covered and passing.

## Tasks

- [ ] `backend/core/auth.py` -- complete Authentik/JWKS validation, enforce the single-host boundary, and cache/refresh keys safely.
- [ ] `backend/routers/games.py` and `backend/services/content.py` -- validate remaining pipeline and stale-worker protections across content generation and rulebook replacement.
- [ ] `backend/routers/room.py` and `frontend/src/components/RoomPage.svelte` -- verify SSE closure semantics and guest-room failure handling.
- [ ] `tests/test_app.py` -- add coverage for auth, room closure, and still-risky lifecycle conditions.
- [ ] `docker-compose.yml` and deployment config -- verify the runtime setup includes the required environment variables and Authentik wiring.

## Notes

This story is intentionally a follow-on to the initial build foundation, not a new product feature. It closes the remaining production-readiness gaps identified by the review and keeps the build aligned with the architecture and PRD.
