## Deferred from: code review of story-1-1-create-and-browse-game-entries (2026-09-16)

- Detail's session, generation, and delete actions ignore non-2xx responses. This predates the Story 1.1 cover/collection implementation and should be addressed in the broader Detail workflow.
- AGENTS.md still contains TODO verification instructions. Updating agent-context guidance belongs to the project-context workflow, not this implementation review.

## Deferred from: code review rerun of story-1-1-create-and-browse-game-entries (2026-09-16)

- Detail's session, generation, and delete actions still ignore non-2xx responses; this predates the Story 1.1 cover/collection changes.
- Cover replacement locking is process-local; supporting multiple workers requires an architecture decision about distributed locking.
- Synchronous cover filesystem/database work runs inside an async endpoint; converting this route needs a broader async I/O decision.
