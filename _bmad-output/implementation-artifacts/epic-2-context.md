# Epic 2 Context: Prepare Trusted Game Content

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Enable the Host to prepare trustworthy game-night content from an uploaded Rulebook. Text is extracted locally, cloud generation is explicitly Host-triggered using a protected provider key, and the Quick-start Guide and Cheat Sheet remain Draft until reviewed and published. The Host can preview the published pair without a Session; Guests and runtime views use locally stored Published Content.

## Stories

- Story 2.1: Configure and Protect the LLM Provider
- Story 2.2: Extract Rulebook Text Locally
- Story 2.3: Generate Draft Content from a Rulebook
- Story 2.4: Review, Reject, and Publish Draft Content
- Story 2.5: Preview Published Content Without a Session
- Story 2.6: Add OpenAI as a Supported Provider
- Story 2.7: Make Rulebook Extraction Optional to Start a Session

## Requirements & Constraints

- Generation requires a Game Rulebook with completed extraction and configured provider credentials. A Host explicitly confirms the cloud generation action; unavailable prerequisites disable generation and direct invalid triggers return clear validation or conflict errors.
- Extract the uploaded PDF locally before any cloud call. Cache extracted text on persistent storage; send extracted text only, never raw PDF bytes. Warn on low extraction quality and allow the Host to override.
- Each successful generation creates a paired Quick-start Guide and Cheat Sheet in Markdown. Warn before replacing an existing Draft. During regeneration, keep the existing Published pair available; a failed generation must not damage it.
- The Host reviews the pair as read-only content. Publish replaces the Published pair atomically and clears the Draft; Reject clears only the Draft and permits regeneration. Invalid or incomplete actions must not partially mutate content.
- Only Published Content is eligible for Host Preview or Guest/runtime serving. Preview reads the same published pair locally without creating a Room or Session, and must not expose Draft or Rejected content as published.
- Settings show only non-secret provider configuration state. Encrypt API keys before local persistence; never return keys in API responses or frontend code. Provider errors are surfaced clearly while existing Published Content remains available. Protect Host routes with Authentik; Guest routes expose no settings or credentials.
- PDFs, extracted text, Content, and settings persist through the named TrueNAS datasets. Runtime Room and preview access makes no cloud calls. Success target: at least three of the first five Games reach Published within two generation attempts.

## Technical Decisions

- Store structured data in the single SQLModel/SQLite database. Keep exactly one Content row per Game, with separate nullable Draft and Published Markdown fields, pipeline state, prior state, and timestamps.
- Enforce pipeline transitions in `backend/services/content.py`; invalid transitions return HTTP 409. Routers and workers do not mutate state directly. Preserve Published fields during generation and recover stuck `extracting` or `generating` jobs to their recorded prior state on startup.
- Run PDF extraction in a thread pool and generation as an in-process async task. Persist the absolute `Rulebook.extracted_text_path`; generation reads only that path. Host polling for extraction/generation state is no more frequent than every five seconds.
- Store API keys with the single Fernet implementation using `SECRET_KEY`; keep encryption/decryption centralized in `backend/core/crypto.py`. Provider calls and credentials stay server-side. Story 2.6 adds OpenAI through the existing configured-provider and Draft flow.
- Render stored Markdown through one shared sanitized frontend component; do not store generated HTML. Use standard FastAPI error shapes and ISO 8601 UTC API timestamps.

## UX & Interaction Patterns

- Provide Settings, Game Detail, Content Review, and Host Preview flows. Show pipeline state with text and semantic color, including inline extraction/generation loading and error feedback; announce asynchronous updates accessibly.
- Content Review presents both read-only Markdown documents side by side on desktop and stacked on narrow screens. Keep Reject and Publish actions sticky. Reject requires a destructive-action confirmation; Publish does not.
- Host Preview is read-only, uses the shared renderer, and shows a clear unavailable state when Published Content does not exist. Use calm microcopy, visible keyboard focus, and accessible labels/status semantics.

## Cross-Story Dependencies

- Epic 2 depends on Epic 1 providing a Game and its single active Rulebook with persistent PDF storage and replacement behavior.
- Stories 2.1 and 2.2 provide the credentials and completed extracted-text path required by Story 2.3. Story 2.6 extends provider support through Settings and the same generation path.
- Story 2.3 creates the Draft consumed by Story 2.4. Publishing makes the pair available to Story 2.5 and to Epic 3; preview and Guest serving use the same Published fields without invoking generation.
- Story 2.7 relaxes the Session-start prerequisite: a Game with Published Content can start a Session even when extraction is absent, pending, or failed. Generation still requires completed extraction.
