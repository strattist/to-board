import asyncio
from pathlib import Path
from sqlmodel import Session, select
from backend.db.engine import engine
from backend.models import AppSettings, Content, Rulebook
from backend.services.content import generation_failed, save_draft
from backend.services.llm import generate_content

async def run_generation(game_id: str) -> None:
    with Session(engine) as session:
        content = session.exec(select(Content).where(Content.game_id == game_id)).first()
        rulebook = session.exec(select(Rulebook).where(Rulebook.game_id == game_id)).first()
        settings = session.get(AppSettings, 1)
        if not content or not rulebook or not rulebook.extracted_text_path or not settings:
            return
        try:
            text = Path(rulebook.extracted_text_path).read_text(encoding='utf-8')
            quickstart, cheat_sheet = await generate_content(settings, text)
            save_draft(session, content, quickstart, cheat_sheet)
            session.commit()
        except Exception as exc:
            generation_failed(session, content, str(exc))
            session.commit()
