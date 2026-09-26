import hashlib
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlmodel import Session, select
from backend.core.utils import uuid4_str
from backend.models import Content, PipelineState

EXTRACTION_WARNING_PREFIX = 'Rulebook text extraction is below the recommended minimum.'


def extraction_warning(token_count: int, minimum_tokens: int) -> str:
    return (
        f'{EXTRACTION_WARNING_PREFIX} The cache contains {token_count} words; '
        f'the recommended minimum is {minimum_tokens}. Review the Rulebook '
        'before generating, or explicitly acknowledge this warning to continue.'
    )


def is_extraction_warning(message: str | None) -> bool:
    return bool(message and message.startswith(EXTRACTION_WARNING_PREFIX))

TRANSITIONS = {
    PipelineState.no_rulebook: {PipelineState.extracting},
    PipelineState.extracting: {PipelineState.ready_to_generate, PipelineState.no_rulebook},
    PipelineState.ready_to_generate: {PipelineState.generating},
    PipelineState.generating: {PipelineState.draft, PipelineState.ready_to_generate, PipelineState.rejected},
    PipelineState.draft: {PipelineState.published, PipelineState.rejected},
    PipelineState.rejected: {PipelineState.generating},
    PipelineState.published: {PipelineState.generating},
}

def get_or_create(session: Session, game_id: str) -> Content:
    content = session.exec(select(Content).where(Content.game_id == game_id)).first()
    if content is None:
        content = Content(id=uuid4_str(), game_id=game_id)
        session.add(content)
        session.flush()
    return content

def transition(session: Session, content: Content, target: PipelineState) -> Content:
    current = content.pipeline_state
    if target not in TRANSITIONS.get(current, set()):
        raise HTTPException(status_code=409, detail=f'Cannot transition content from {current.value} to {target.value}.')
    content.prior_pipeline_state = current
    content.pipeline_state = target
    session.add(content)
    return content

def reset_for_rulebook(session: Session, content: Content) -> Content:
    content.prior_pipeline_state = content.pipeline_state
    content.pipeline_state = PipelineState.no_rulebook
    content.draft_quickstart_md = None
    content.draft_cheat_sheet_md = None
    content.error_message = None
    session.add(content)
    return content

def begin_extraction(session: Session, game_id: str) -> Content:
    return transition(session, get_or_create(session, game_id), PipelineState.extracting)

def mark_extraction_complete(session: Session, game_id: str, warning: str | None = None) -> Content:
    content = get_or_create(session, game_id)
    transition(session, content, PipelineState.ready_to_generate)
    content.error_message = warning
    return content

def mark_extraction_failed(session: Session, game_id: str, message: str) -> Content:
    content = get_or_create(session, game_id)
    if content.pipeline_state == PipelineState.extracting:
        transition(session, content, PipelineState.no_rulebook)
    content.error_message = message
    return content

def begin_generation(session: Session, game_id: str) -> Content:
    content = get_or_create(session, game_id)
    if content.pipeline_state == PipelineState.draft:
        content.draft_quickstart_md = None
        content.draft_cheat_sheet_md = None
        content.pipeline_state = PipelineState.rejected
        content.prior_pipeline_state = PipelineState.draft
    return transition(session, content, PipelineState.generating)

def save_draft(session: Session, content: Content, quickstart: str, cheat_sheet: str) -> Content:
    if content.pipeline_state != PipelineState.generating:
        raise HTTPException(status_code=409, detail='Content is not being generated.')
    transition(session, content, PipelineState.draft)
    content.draft_quickstart_md = quickstart
    content.draft_cheat_sheet_md = cheat_sheet
    content.generated_at = datetime.now(timezone.utc)
    content.error_message = None
    return content

def generation_failed(session: Session, content: Content, message: str) -> Content:
    if content.pipeline_state == PipelineState.generating:
        previous = content.prior_pipeline_state or PipelineState.ready_to_generate
        content.prior_pipeline_state = content.pipeline_state
        content.pipeline_state = previous
    content.error_message = message
    session.add(content)
    return content

def _has_complete_draft(content: Content) -> bool:
    return bool(
        content.draft_quickstart_md
        and content.draft_quickstart_md.strip()
        and content.draft_cheat_sheet_md
        and content.draft_cheat_sheet_md.strip()
    )

def draft_revision(content: Content) -> str | None:
    if not _has_complete_draft(content):
        return None
    digest = hashlib.sha256()
    for document in (content.draft_quickstart_md, content.draft_cheat_sheet_md):
        encoded = document.encode('utf-8')
        digest.update(len(encoded).to_bytes(8, 'big'))
        digest.update(encoded)
    return digest.hexdigest()

def _require_reviewed_draft(content: Content, expected_revision: str | None) -> None:
    if content.pipeline_state != PipelineState.draft or not _has_complete_draft(content):
        raise HTTPException(status_code=409, detail='A complete Draft is required before this action.')
    if not expected_revision or expected_revision != draft_revision(content):
        raise HTTPException(status_code=409, detail='Draft changed since it was loaded. Reload before acting.')

def publish(session: Session, content: Content, expected_revision: str | None = None) -> Content:
    _require_reviewed_draft(content, expected_revision)
    transition(session, content, PipelineState.published)
    content.published_quickstart_md = content.draft_quickstart_md
    content.published_cheat_sheet_md = content.draft_cheat_sheet_md
    content.draft_quickstart_md = None
    content.draft_cheat_sheet_md = None
    content.published_at = datetime.now(timezone.utc)
    return content

def reject(session: Session, content: Content, expected_revision: str | None = None) -> Content:
    _require_reviewed_draft(content, expected_revision)
    transition(session, content, PipelineState.rejected)
    content.draft_quickstart_md = None
    content.draft_cheat_sheet_md = None
    return content
