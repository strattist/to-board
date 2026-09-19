from pathlib import Path
from sqlmodel import Session, select
from backend.db.engine import engine
from backend.models import Content, PipelineState, Rulebook
from backend.services.content import mark_extraction_complete, mark_extraction_failed
from backend.services.extraction import extract_pdf

def _remove_output(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        # Cleanup must never prevent the worker from recording a recoverable
        # extraction failure or returning from stale work.
        return


def run_extraction(game_id: str, rulebook_id: str) -> None:
    with Session(engine) as session:
        rulebook = session.exec(select(Rulebook).where(Rulebook.id == rulebook_id, Rulebook.game_id == game_id)).first()
        if not rulebook:
            return
        current = session.exec(select(Rulebook).where(Rulebook.game_id == game_id)).first()
        if not current or current.id != rulebook_id:
            stale_output = Path(rulebook.pdf_path).resolve().with_suffix('.txt')
            _remove_output(stale_output)
            return
        output = str(Path(rulebook.pdf_path).resolve().with_suffix('.txt'))
        try:
            extract_pdf(rulebook.pdf_path, output)
            current = session.exec(select(Rulebook).where(Rulebook.game_id == game_id)).first()
            if not current or current.id != rulebook_id:
                _remove_output(Path(output))
                return
            content = session.exec(select(Content).where(Content.game_id == game_id)).first()
            if not content or content.pipeline_state != PipelineState.extracting:
                _remove_output(Path(output))
                return
            rulebook.extracted_text_path = output
            session.add(rulebook)
            mark_extraction_complete(session, game_id)
            session.commit()
        except Exception as exc:
            _remove_output(Path(output))
            current = session.exec(select(Rulebook).where(Rulebook.game_id == game_id)).first()
            content = session.exec(select(Content).where(Content.game_id == game_id)).first()
            if current and current.id == rulebook_id and content and content.pipeline_state == PipelineState.extracting:
                mark_extraction_failed(session, game_id, f'Rulebook extraction failed: {exc}')
            session.commit()
