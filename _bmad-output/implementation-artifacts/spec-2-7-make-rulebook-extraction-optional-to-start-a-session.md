---
title: 'Make Rulebook extraction optional to start a Session'
type: 'feature'
created: '2026-09-30'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
baseline_commit: 'b6a565d53e2842e0ceadcedc96daada5b95c1d63'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Story 2.7 asks that a Game with Published Content can start a Session even when Rulebook extraction is absent, pending, or failed, while generation still requires completed extraction. The code already behaves this way (`backend/services/sessions.py` create_session checks only Published Content; Game Detail's Start button checks only `hasPublishedContent`), but tests cover only the `extracting` and `generating` states, so the no-Rulebook and `ready_to_generate` states and the generation prerequisite are unprotected.

**Approach:** Keep the implementation unchanged. Add backend tests for Session start and for the generation prerequisite, and only fix production code if a test finds a real mismatch.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Start, no Rulebook | Published pair; no Rulebook row; `no_rulebook` | 201; Room serves the Published pair | N/A |
| Start, extraction done | Published pair; `ready_to_generate` | 201 | N/A |
| Start, no Published pair | Extraction absent or done; no Published pair | Refused | 422 "Published Content is required to start a Session." |
| Generate, no extraction | Published pair; no Rulebook or extracted text | Refused; Published pair unchanged | 422 "Rulebook extraction is not complete." |

</frozen-after-approval>

## Implementation Notes

- Investigation found the behavior already implemented: `backend/services/sessions.py` (create_session) and `frontend/src/components/Detail.svelte` (Start button gated on `hasPublishedContent` only; contract at `frontend/tests/interaction-contracts.test.mjs:179` forbids `extractionBusy`). No production code changed.
- Added 5 tests at the end of `tests/test_app.py`: session start with no Rulebook and with extraction complete, refusal without a Published pair, and generation still refused without extraction while leaving the Published pair untouched. Suite: 116 passed; frontend contracts pass.
- Review ran inline (no subagents were requested): the tests pass on unchanged production code, which is expected since they pin existing behavior. Not covered: an extraction-failed state distinct from `no_rulebook` (the model has none; failed extraction returns to `no_rulebook`).
- No commit made: AGENTS.md forbids commits unless explicitly asked.

## Verification

**Commands:**
- `pytest -q` -- expected: all tests pass
- `npm --prefix frontend run test:contracts` -- expected: contracts pass
