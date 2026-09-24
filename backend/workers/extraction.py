from pathlib import Path
from sqlmodel import Session, select
from backend.db.engine import engine
from backend.models import Content, PipelineState, Rulebook
from backend.core.config import get_settings
from backend.services.content import extraction_warning, mark_extraction_complete, mark_extraction_failed
from backend.services.extraction import count_extracted_tokens, extract_pdf
from backend.services.games import game_operation_lock
from backend.services.rulebooks import safe_upload_path

def _remove_output(path: Path) -> bool:
    try:
        path.unlink(missing_ok=True)
        return True
    except OSError:
        # Cleanup must never prevent the worker from recording a recoverable
        # extraction failure or returning from stale work.
        return False


def _record_failure(game_id: str, rulebook_id: str, message: str, clear_path: bool) -> None:
    with Session(engine) as recovery:
        current = recovery.exec(select(Rulebook).where(Rulebook.game_id == game_id)).first()
        content = recovery.exec(select(Content).where(Content.game_id == game_id)).first()
        if current and current.id == rulebook_id and content and content.pipeline_state == PipelineState.extracting:
            if clear_path:
                current.extracted_text_path = None
                recovery.add(current)
                mark_extraction_failed(recovery, game_id, message)
            else:
                content.error_message = message
                recovery.add(content)
            recovery.commit()


def run_extraction(game_id: str, rulebook_id: str) -> None:
    with game_operation_lock(game_id):
        with Session(engine) as session:
            rulebook = session.exec(select(Rulebook).where(Rulebook.id == rulebook_id, Rulebook.game_id == game_id)).first()
            if not rulebook:
                return
            pdf_path = safe_upload_path(rulebook.pdf_path, get_settings().uploads_path.resolve())
            current = session.exec(select(Rulebook).where(Rulebook.game_id == game_id)).first()
            if not current or current.id != rulebook_id:
                if pdf_path:
                    _remove_output(pdf_path.with_suffix('.txt'))
                return
            if not pdf_path:
                _record_failure(game_id, rulebook_id, 'Rulebook extraction failed. Re-upload the Rulebook to try again.', True)
                return
            output = pdf_path.with_suffix('.txt')
            try:
                # FastAPI executes this synchronous BackgroundTask in its worker
                # thread pool, keeping blocking pdfplumber work off the request
                # event loop.
                token_count = extract_pdf(str(pdf_path), str(output))
                current = session.exec(select(Rulebook).where(Rulebook.game_id == game_id)).first()
                if not current or current.id != rulebook_id:
                    _remove_output(output)
                    return
                content = session.exec(select(Content).where(Content.game_id == game_id)).first()
                if not content or content.pipeline_state != PipelineState.extracting:
                    _remove_output(output)
                    return
                rulebook.extracted_text_path = str(output)
                session.add(rulebook)
                settings = get_settings()
                warning = (
                    extraction_warning(token_count, settings.extraction_min_tokens)
                    if token_count < settings.extraction_min_tokens else None
                )
                mark_extraction_complete(session, game_id, warning)
                session.commit()
            except Exception:
                cleanup_ok = _remove_output(output)
                session.rollback()
                if cleanup_ok:
                    _record_failure(game_id, rulebook_id, 'Rulebook extraction failed. Re-upload the Rulebook to try again.', True)
                else:
                    _record_failure(
                        game_id,
                        rulebook_id,
                        'Rulebook extraction failed; cleanup is pending. Re-upload the Rulebook to try again.',
                        False,
                    )
