from pathlib import Path
from sqlmodel import Session, select
from backend.db.engine import create_db_and_tables, engine
from backend.core.config import get_settings
from backend.models import Content, PipelineState, Rulebook


def _cleanup_candidates(candidates: list[Path]) -> bool:
    cleanup_failed = False
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            candidate.unlink(missing_ok=True)
        except OSError:
            cleanup_failed = True
        try:
            parts = list(candidate.parent.glob(f'.{candidate.name}.*.part'))
        except OSError:
            cleanup_failed = True
            parts = []
        for part in parts:
            try:
                part.unlink(missing_ok=True)
            except OSError:
                cleanup_failed = True
    return cleanup_failed


def initialize_database() -> None:
    create_db_and_tables()
    uploads_root = get_settings().uploads_path.resolve()
    with Session(engine) as session:
        for content in session.exec(select(Content)).all():
            if content.pipeline_state in (PipelineState.extracting, PipelineState.generating):
                if content.pipeline_state == PipelineState.extracting:
                    rulebook = session.exec(select(Rulebook).where(Rulebook.game_id == content.game_id)).first()
                    # An interrupted extraction must never leave a cache path
                    # that looks ready. Only delete artifacts under the
                    # configured uploads dataset, and keep recovery retryable
                    # if the filesystem is temporarily unavailable.
                    candidates: list[Path | None] = []
                    if rulebook:
                        candidates.extend([
                            Path(rulebook.pdf_path).resolve().with_suffix('.txt'),
                            Path(rulebook.extracted_text_path).resolve() if rulebook.extracted_text_path else None,
                        ])
                    else:
                        game_root = uploads_root / 'rulebooks' / content.game_id
                        try:
                            candidates.extend(game_root.glob('*.txt'))
                            candidates.extend(game_root.glob('.*.txt.*.part'))
                        except OSError:
                            content.error_message = 'The previous background operation was interrupted; cleanup is pending.'
                            session.add(content)
                            continue
                    safe_candidates = []
                    for candidate in candidates:
                        if candidate is None:
                            continue
                        try:
                            candidate.relative_to(uploads_root)
                        except ValueError:
                            continue
                        safe_candidates.append(candidate)
                    if _cleanup_candidates(safe_candidates):
                        content.error_message = 'The previous background operation was interrupted; cleanup is pending.'
                        session.add(content)
                        continue
                    if rulebook:
                        rulebook.extracted_text_path = None
                        session.add(rulebook)
                content.pipeline_state = content.prior_pipeline_state or PipelineState.no_rulebook
                content.error_message = 'The previous background operation was interrupted; retry when ready.'
                session.add(content)
        session.commit()
