"""Rulebook validation, staging, and replacement operations."""

from __future__ import annotations

from io import BytesIO
import json
import logging
import os
from pathlib import Path
import time
from uuid import uuid4

from fastapi import HTTPException
from sqlmodel import Session, select

from backend.core.config import Settings
from backend.core.utils import uuid4_str
from backend.models import Content, Game, Rulebook
from backend.services.content import begin_extraction, get_or_create, reset_for_rulebook

logger = logging.getLogger(__name__)
_CLEANUP_JOURNAL = '.rulebook-cleanup.json'
_CLEANUP_RETRIES = 3

def _remove_path(path: Path) -> None:
    for attempt in range(_CLEANUP_RETRIES):
        try:
            path.unlink(missing_ok=True)
            return
        except OSError as exc:
            if attempt == _CLEANUP_RETRIES - 1:
                logger.warning('Unable to remove temporary Rulebook artifact %s: %s', path, exc)
            else:
                time.sleep(0.01)


def _cleanup_journal_path(uploads_root: Path) -> Path:
    return uploads_root / _CLEANUP_JOURNAL


def _read_cleanup_journal(uploads_root: Path) -> list[str]:
    try:
        value = json.loads(_cleanup_journal_path(uploads_root).read_text(encoding='utf-8'))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return []
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _write_cleanup_journal(uploads_root: Path, paths: list[str]) -> None:
    journal = _cleanup_journal_path(uploads_root)
    if not paths:
        _remove_path(journal)
        return
    temporary = journal.with_name(f'.{journal.name}.{uuid4().hex}.part')
    try:
        with temporary.open('w', encoding='utf-8') as handle:
            json.dump(paths, handle)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(journal)
    except OSError as exc:
        logger.error('Unable to persist Rulebook cleanup journal %s: %s', journal, exc)
    finally:
        _remove_path(temporary)


def validate_pdf(data: bytes, max_bytes: int) -> None:
    """Reject files that are too large or are not parseable local PDFs."""
    if len(data) > max_bytes:
        raise HTTPException(422, 'The rulebook must be a valid PDF no larger than 100 MB.')
    if not data.startswith(b'%PDF'):
        raise HTTPException(422, 'The rulebook must be a valid PDF no larger than 100 MB.')

    try:
        import pdfplumber

        with pdfplumber.open(BytesIO(data)) as pdf:
            # Opening and reading the page collection catches truncated and
            # malformed cross-reference tables before anything is persisted.
            if not pdf.pages:
                raise ValueError('PDF has no pages')
            for page in pdf.pages:
                page.extract_text()
                page.close()
    except Exception as exc:
        raise HTTPException(422, 'The uploaded rulebook is malformed or truncated.') from exc


def _safe_upload_path(path: str | None, uploads_root: Path) -> Path | None:
    if not path:
        return None
    candidate = Path(path)
    candidates = [candidate] if candidate.is_absolute() else [candidate, uploads_root / candidate]
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            resolved.relative_to(uploads_root)
            return resolved
        except (OSError, ValueError):
            continue
    logger.warning('Skipping cleanup of rulebook path outside uploads dataset: %s', path)
    return None


def safe_upload_path(path: str | None, uploads_root: Path) -> Path | None:
    """Resolve a persisted Rulebook path only when it stays in uploads_root."""
    return _safe_upload_path(path, uploads_root)


def _track_cleanup(paths: list[Path], uploads_root: Path) -> None:
    pending = set(_read_cleanup_journal(uploads_root))
    for path in paths:
        try:
            pending.add(str(path.resolve().relative_to(uploads_root)))
        except (OSError, ValueError):
            logger.warning('Skipping cleanup tracking outside uploads dataset: %s', path)
    _write_cleanup_journal(uploads_root, sorted(pending))


def _retry_pending_cleanup(uploads_root: Path) -> None:
    pending = _read_cleanup_journal(uploads_root)
    remaining: list[str] = []
    for value in pending:
        path = _safe_upload_path(value, uploads_root)
        if path is None:
            continue
        before = path.exists()
        _remove_path(path)
        if before and path.exists():
            remaining.append(value)
    if remaining != pending:
        _write_cleanup_journal(uploads_root, remaining)


def retry_pending_cleanup(uploads_root: Path) -> None:
    """Replay persisted cleanup work during application startup."""
    _retry_pending_cleanup(uploads_root)


def _remove_old_files(paths: list[str | None], uploads_root: Path) -> list[Path]:
    failed: list[Path] = []
    for path in paths:
        safe_path = _safe_upload_path(path, uploads_root)
        if safe_path is None:
            continue
        before = safe_path.exists()
        _remove_path(safe_path)
        if before and safe_path.exists():
            failed.append(safe_path)
    return failed


def replace_rulebook(
    session: Session,
    game: Game,
    data: bytes,
    settings: Settings,
) -> Rulebook:
    """Stage a PDF, install its unique row, and queue extraction state.

    The staged file is renamed into place before the database commit so a
    committed row always points at a durable file. If the commit fails, only
    the new file is removed and the prior row/files remain untouched.
    """
    uploads_root = settings.uploads_path.resolve()
    _retry_pending_cleanup(uploads_root)
    game_dir = uploads_root / 'rulebooks' / game.id
    game_dir.mkdir(parents=True, exist_ok=True)
    final_path = game_dir / f'{uuid4_str()}.pdf'
    temporary_path = game_dir / f'.{final_path.name}.{uuid4().hex}.part'

    old = session.exec(select(Rulebook).where(Rulebook.game_id == game.id)).first()
    old_paths = [old.pdf_path, old.extracted_text_path] if old else []
    content = get_or_create(session, game.id)

    committed = False
    try:
        with temporary_path.open('xb') as staged:
            staged.write(data)
            staged.flush()
            os.fsync(staged.fileno())
        temporary_path.replace(final_path)

        if old:
            session.delete(old)
            # The unique game_id constraint requires the old row to be
            # removed before the replacement row is flushed.
            session.flush()
        reset_for_rulebook(session, content)
        rulebook = Rulebook(id=uuid4_str(), game_id=game.id, pdf_path=str(final_path))
        session.add(rulebook)
        begin_extraction(session, game.id)
        session.commit()
        committed = True
        session.refresh(rulebook)
    except Exception:
        session.rollback()
        failed_cleanup: list[Path] = []
        if not committed:
            if temporary_path.exists():
                failed_cleanup.append(temporary_path)
            _remove_path(temporary_path)
            # The rename may have happened before the database failure.
            if final_path.exists():
                failed_cleanup.append(final_path)
            _remove_path(final_path)
        _track_cleanup([path for path in failed_cleanup if path.exists()], uploads_root)
        raise

    failed_cleanup = _remove_old_files(old_paths, uploads_root)
    _track_cleanup(failed_cleanup, uploads_root)
    return rulebook
