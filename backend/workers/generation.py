import asyncio
from pathlib import Path
from sqlmodel import Session, select
from backend.db.engine import engine
from backend.models import AppSettings, Content, PipelineState, Rulebook
from backend.services.content import generation_failed, save_draft
from backend.services.llm import generate_content


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
            quickstart, cheat_sheet = await generate_content(settings, text)
            current = session.exec(select(Content).where(Content.game_id == game_id)).first()
            latest_rulebook = session.exec(select(Rulebook).where(Rulebook.game_id == game_id)).first()
            if not current or current.pipeline_state != PipelineState.generating or not latest_rulebook or latest_rulebook.id != rulebook_id:
                return
            save_draft(session, current, quickstart, cheat_sheet)
            session.commit()
        except Exception as exc:
            current = session.exec(select(Content).where(Content.game_id == game_id)).first()
            if current and current.pipeline_state == PipelineState.generating:
                generation_failed(session, current, str(exc))
            session.commit()
