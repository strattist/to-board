from sqlmodel import Session, select
from backend.core.config import get_settings
from backend.db.engine import engine
from backend.models import Rulebook
from backend.services.content import mark_extraction_complete, mark_extraction_failed
from backend.services.extraction import extract_pdf
from pathlib import Path

def run_extraction(game_id: str, rulebook_id: str) -> None:
    settings = get_settings()
    with Session(engine) as session:
        rulebook = session.exec(select(Rulebook).where(Rulebook.id == rulebook_id, Rulebook.game_id == game_id)).first()
        if not rulebook:
            return
        output = str(Path(rulebook.pdf_path).with_suffix('.txt'))
        try:
            extract_pdf(rulebook.pdf_path, output)
            current = session.exec(select(Rulebook).where(Rulebook.game_id == game_id)).first()
            if not current or current.id != rulebook_id:
                return
            rulebook.extracted_text_path = output
            session.add(rulebook)
            mark_extraction_complete(session, game_id)
            session.commit()
        except Exception as exc:
            mark_extraction_failed(session, game_id, f'Rulebook extraction failed: {exc}')
            session.commit()
