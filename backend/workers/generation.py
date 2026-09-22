import asyncio
from pathlib import Path
from sqlmodel import Session, select
from backend.db.engine import engine
from backend.models import AppSettings, Content, PipelineState, Rulebook
from backend.services.content import generation_failed, save_draft
from backend.services.llm import ProviderError, generate_content, safe_provider_failure


def _record_failure(game_id: str, message: str) -> None:
    """Record a safe failure in a fresh transaction after a rollback."""
    with Session(engine) as recovery:
        current = recovery.exec(select(Content).where(Content.game_id == game_id)).first()
        if current and current.pipeline_state == PipelineState.generating:
            generation_failed(recovery, current, message)
            recovery.commit()


async def run_generation(game_id: str, rulebook_id: str) -> None:
    with Session(engine) as session:
        content = session.exec(select(Content).where(Content.game_id == game_id)).first()
        rulebook = session.exec(select(Rulebook).where(Rulebook.id == rulebook_id, Rulebook.game_id == game_id)).first()
        if not content or not rulebook or content.pipeline_state != PipelineState.generating:
            return
        current_rulebook = session.exec(select(Rulebook).where(Rulebook.game_id == game_id)).first()
        if not current_rulebook or current_rulebook.id != rulebook_id:
            return
        settings = session.get(AppSettings, 1)
        if not settings or not rulebook.extracted_text_path:
            generation_failed(session, content, 'Generation prerequisites are no longer available.')
            session.commit()
            return
        try:
            text = Path(rulebook.extracted_text_path).read_text(encoding='utf-8')
        except Exception:
            generation_failed(session, content, 'Rulebook text could not be read.')
            session.commit()
            return

        try:
            quickstart, cheat_sheet = await generate_content(settings, text)
        except ProviderError as exc:
            generation_failed(session, content, str(exc))
            session.commit()
            return
        except Exception:
            generation_failed(session, content, safe_provider_failure(settings.llm_provider))
            session.commit()
            return

        try:
            current = session.exec(select(Content).where(Content.game_id == game_id)).first()
            latest_rulebook = session.exec(select(Rulebook).where(Rulebook.game_id == game_id)).first()
            if not current or current.pipeline_state != PipelineState.generating or not latest_rulebook or latest_rulebook.id != rulebook_id:
                return
            save_draft(session, current, quickstart, cheat_sheet)
            session.commit()
        except Exception:
            session.rollback()
            _record_failure(game_id, 'Generated content could not be saved.')
