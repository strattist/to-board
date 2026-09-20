from io import BytesIO
from contextlib import contextmanager
import json
import logging
import os
from pathlib import Path
import time
from threading import RLock
from uuid import uuid4
import warnings
from sqlmodel import Session, select
from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError
from PIL.Image import DecompressionBombError, DecompressionBombWarning
from backend.core.config import get_settings
from backend.core.utils import slugify, uuid4_str
from backend.models import Content, Game, GameSession, Rulebook
from backend.services.content import get_or_create

MAX_COVER_BYTES = 10 * 1024 * 1024
COVER_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
MAX_GAME_TITLE_LENGTH = 200
_DELETE_CLEANUP_JOURNAL = '.game-delete-cleanup.json'
_DELETE_RECOVERY_JOURNAL = '.game-delete-recovery.json'
_DELETE_PENDING_DIR = '.game-delete-pending'
_DELETE_CLEANUP_RETRIES = 3
logger = logging.getLogger(__name__)
_journal_lock = RLock()
_game_locks: dict[str, RLock] = {}


@contextmanager
def game_operation_lock(game_id: str):
    """Serialize all filesystem/database operations that own one Game."""
    with _journal_lock:
        lock = _game_locks.setdefault(game_id, RLock())
    with lock:
        yield


def validate_cover(data: bytes, suffix: str) -> None:
    """Validate the supported cover formats and verify that the image decodes."""
    if suffix not in COVER_EXTENSIONS:
        raise ValueError('Cover image must be JPEG, PNG, or WebP.')
    if len(data) > MAX_COVER_BYTES:
        raise ValueError('Cover image must be no larger than 10 MB.')

    expected_formats = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.webp': 'WEBP'}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                image_format = image.format
                image.verify()
            with Image.open(BytesIO(data)) as image:
                image.load()
        if image_format != expected_formats[suffix]:
            raise ValueError('Cover extension does not match its image format.')
    except (DecompressionBombError, DecompressionBombWarning, SyntaxError, UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError('Cover image is not a valid JPEG, PNG, or WebP file.') from exc


def create_game(session: Session, title: str) -> Game:
    title = title.strip()
    if not title:
        raise HTTPException(status_code=422, detail='Game title is required.')
    if len(title) > MAX_GAME_TITLE_LENGTH:
        raise HTTPException(status_code=422, detail='Game title must be 200 characters or fewer.')
    game = Game(id=uuid4_str(), title=title, room_slug_prefix=slugify(title))
    session.add(game)
    get_or_create(session, game.id)
    session.commit(); session.refresh(game)
    return game

def create_game_with_cover(session: Session, title: str, cover_data: bytes, suffix: str) -> Game:
    title = title.strip()
    if not title:
        raise HTTPException(status_code=422, detail='Game title is required.')
    if len(title) > MAX_GAME_TITLE_LENGTH:
        raise HTTPException(status_code=422, detail='Game title must be 200 characters or fewer.')
    try:
        validate_cover(cover_data, suffix)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    game = Game(id=uuid4_str(), title=title, room_slug_prefix=slugify(title))
    session.add(game)
    get_or_create(session, game.id)
    target = get_settings().uploads_path / 'covers' / f'{game.id}{suffix}'
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.write_bytes(cover_data)
        game.cover_image_path = str(target)
        session.add(game)
        session.commit()
    except Exception:
        session.rollback()
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return game

def _safe_upload_path(path: str | None, uploads_root: Path) -> Path | None:
    """Resolve a stored asset path only when it is inside the uploads dataset."""
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
    return None


def _remove_path(path: Path) -> bool:
    """Remove a staged asset, returning whether it is gone after retries."""
    for attempt in range(_DELETE_CLEANUP_RETRIES):
        try:
            path.unlink(missing_ok=True)
            return not path.exists()
        except OSError as exc:
            if attempt == _DELETE_CLEANUP_RETRIES - 1:
                logger.warning('Unable to remove deleted Game asset %s: %s', path, exc)
            else:
                time.sleep(0.01)
    return not path.exists()


def _journal_path(uploads_root: Path) -> Path:
    return uploads_root / _DELETE_CLEANUP_JOURNAL


def _recovery_journal_path(uploads_root: Path) -> Path:
    return uploads_root / _DELETE_RECOVERY_JOURNAL


def _pending_marker_path(uploads_root: Path, game_id: str) -> Path:
    return uploads_root / _DELETE_PENDING_DIR / f'{game_id}.json'


def _read_json_list(path: Path) -> list:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return []
    return value if isinstance(value, list) else []


def _write_json_list(path: Path, values: list) -> None:
    temporary = path.with_name(f'.{path.name}.{uuid4().hex}.part')
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with temporary.open('w', encoding='utf-8') as handle:
            json.dump(values, handle)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        _remove_path(temporary)


def _relative_paths(uploads_root: Path, paths: list[Path]) -> list[str]:
    values: list[str] = []
    for path in paths:
        try:
            values.append(str(path.resolve().relative_to(uploads_root)))
        except (OSError, ValueError) as exc:
            raise OSError(f'Asset path is outside the uploads dataset: {path}') from exc
    return sorted(set(values))


def _write_cleanup_journal(uploads_root: Path, paths: list[Path | str]) -> None:
    """Atomically replace the cleanup journal, raising if it cannot be persisted."""
    values = [str(path) for path in paths] if paths and isinstance(paths[0], str) else _relative_paths(uploads_root, paths)  # type: ignore[arg-type]
    with _journal_lock:
        if values:
            _write_json_list(_journal_path(uploads_root), sorted(set(values)))
        elif _journal_path(uploads_root).exists() and not _remove_path(_journal_path(uploads_root)):
            raise OSError(f'Unable to clear Game cleanup journal {_journal_path(uploads_root)}')


def _add_cleanup_journal(uploads_root: Path, paths: list[Path]) -> None:
    with _journal_lock:
        existing = {value for value in _read_json_list(_journal_path(uploads_root)) if isinstance(value, str)}
        existing.update(_relative_paths(uploads_root, paths))
        _write_json_list(_journal_path(uploads_root), sorted(existing))


def _remove_cleanup_paths(uploads_root: Path, paths: list[Path]) -> None:
    with _journal_lock:
        existing = {value for value in _read_json_list(_journal_path(uploads_root)) if isinstance(value, str)}
        existing.difference_update(_relative_paths(uploads_root, paths))
        if existing:
            _write_json_list(_journal_path(uploads_root), sorted(existing))
        else:
            _remove_path(_journal_path(uploads_root))


def _write_pending_marker(uploads_root: Path, game_id: str, paths: list[Path]) -> None:
    values = _relative_paths(uploads_root, paths)
    with _journal_lock:
        _write_json_list(_pending_marker_path(uploads_root, game_id), values)


def _reconcile_pending_markers(uploads_root: Path) -> None:
    marker_root = uploads_root / _DELETE_PENDING_DIR
    if not marker_root.is_dir():
        return
    with _journal_lock:
        for marker in marker_root.glob('*.json'):
            values = _read_json_list(marker)
            pending = False
            for value in values:
                if not isinstance(value, str):
                    continue
                path = _safe_upload_path(value, uploads_root)
                if path is not None and path.exists():
                    pending = True
                    break
            if not pending:
                _remove_path(marker)


def game_deletion_pending(uploads_root: Path, game_id: str) -> bool:
    return _pending_marker_path(uploads_root, game_id).exists()


def _recovery_entry(value, uploads_root: Path) -> dict[str, str]:
    if isinstance(value, dict):
        entry = {key: str(item) for key, item in value.items() if key in {'operation', 'game_id', 'phase', 'original', 'tombstone'} and isinstance(item, str)}
    else:
        original, tombstone = value
        entry = {
            'original': str(original.resolve().relative_to(uploads_root)),
            'tombstone': str(tombstone.resolve().relative_to(uploads_root)),
            'phase': 'staging',
        }
    if 'original' not in entry or 'tombstone' not in entry:
        raise OSError('Recovery journal entry is incomplete')
    entry.setdefault('phase', 'staging')
    return entry


def _write_recovery_journal(uploads_root: Path, staged) -> None:
    """Merge durable recovery entries; failure is surfaced to the caller."""
    entries = [_recovery_entry(value, uploads_root) for value in staged]
    with _journal_lock:
        existing = _read_json_list(_recovery_journal_path(uploads_root))
        merged: dict[tuple[str | None, str, str], dict[str, str]] = {}
        for value in existing + entries:
            if not isinstance(value, dict) or not isinstance(value.get('original'), str) or not isinstance(value.get('tombstone'), str):
                continue
            key = (value.get('operation'), value['original'], value['tombstone'])
            merged[key] = {key_name: str(item) for key_name, item in value.items()}
        if merged:
            _write_json_list(_recovery_journal_path(uploads_root), list(merged.values()))
        elif _recovery_journal_path(uploads_root).exists() and not _remove_path(_recovery_journal_path(uploads_root)):
            raise OSError(f'Unable to clear Game recovery journal {_recovery_journal_path(uploads_root)}')


def _replace_recovery_journal(uploads_root: Path, entries: list[dict[str, str]]) -> None:
    with _journal_lock:
        if entries:
            _write_json_list(_recovery_journal_path(uploads_root), entries)
        elif _recovery_journal_path(uploads_root).exists() and not _remove_path(_recovery_journal_path(uploads_root)):
            raise OSError(f'Unable to clear Game recovery journal {_recovery_journal_path(uploads_root)}')


def _remove_recovery_operation(uploads_root: Path, operation: str) -> None:
    with _journal_lock:
        entries = [value for value in _read_json_list(_recovery_journal_path(uploads_root)) if isinstance(value, dict) and value.get('operation') != operation]
        _replace_recovery_journal(uploads_root, entries)


def _mark_recovery_committed(uploads_root: Path, operation: str) -> None:
    with _journal_lock:
        entries = _read_json_list(_recovery_journal_path(uploads_root))
        changed = False
        for value in entries:
            if isinstance(value, dict) and value.get('operation') == operation:
                value['phase'] = 'committed'
                changed = True
        if changed:
            _replace_recovery_journal(uploads_root, [value for value in entries if isinstance(value, dict)])


def _game_exists(game_id: str | None) -> bool | None:
    if not game_id:
        return None
    try:
        from backend.db.engine import engine
        with Session(engine) as session:
            return session.get(Game, game_id) is not None
    except Exception:
        return None


def _restore_pair(original: Path, tombstone: Path) -> bool:
    """Restore without overwriting a replacement and never claim missing data is safe."""
    if not tombstone.exists():
        return original.exists()
    try:
        if original.exists():
            return _remove_path(tombstone)
        original.parent.mkdir(parents=True, exist_ok=True)
        tombstone.replace(original)
        return original.exists() and not tombstone.exists()
    except OSError as exc:
        logger.error('Unable to restore Game asset %s: %s', original, exc)
        return False


def retry_pending_game_cleanup(uploads_root: Path) -> None:
    """Replay rollback restoration and committed cleanup after a restart."""
    with _journal_lock:
        recovery = _read_json_list(_recovery_journal_path(uploads_root))
        remaining_recovery: list[dict[str, str]] = []
        for value in recovery:
            if not isinstance(value, dict):
                remaining_recovery.append({'phase': 'staging', 'original': '', 'tombstone': ''})
                continue
            original_value = value.get('original')
            tombstone_value = value.get('tombstone')
            if not isinstance(original_value, str) or not isinstance(tombstone_value, str):
                remaining_recovery.append(value)
                continue
            original = _safe_upload_path(original_value, uploads_root)
            tombstone = _safe_upload_path(tombstone_value, uploads_root)
            if original is None or tombstone is None:
                remaining_recovery.append(value)
                continue
            committed = value.get('phase') == 'committed' or _game_exists(value.get('game_id')) is False
            if committed:
                if tombstone.exists() and not _remove_path(tombstone):
                    remaining_recovery.append(value)
            elif not _restore_pair(original, tombstone):
                remaining_recovery.append(value)
        _replace_recovery_journal(uploads_root, remaining_recovery)

        values = _read_json_list(_journal_path(uploads_root))
        remaining: list[str] = []
        for value in values:
            if not isinstance(value, str):
                continue
            path = _safe_upload_path(value, uploads_root)
            if path is not None and not _remove_path(path):
                remaining.append(value)
        _write_cleanup_journal(uploads_root, remaining)
        _reconcile_pending_markers(uploads_root)


def _restore_staged(staged: list[tuple[Path, Path]]) -> bool:
    return all(_restore_pair(original, tombstone) for original, tombstone in reversed(staged))


def _create_tombstone_root(uploads_root: Path) -> Path:
    """Create a private staging directory without following a redirecting path."""
    staging_parent = uploads_root / '.game-delete'
    if staging_parent.is_symlink() or (staging_parent.exists() and not staging_parent.is_dir()):
        raise HTTPException(status_code=500, detail='Game deletion could not be completed safely.')
    try:
        staging_parent.mkdir(parents=True, exist_ok=True)
        if staging_parent.is_symlink() or not staging_parent.is_dir():
            raise OSError('Game deletion staging path is not a directory')
        tombstone_root = staging_parent / uuid4().hex
        if tombstone_root.exists() or tombstone_root.is_symlink():
            raise OSError('Game deletion staging directory already exists')
        tombstone_root.mkdir()
        if tombstone_root.is_symlink() or not tombstone_root.is_dir():
            raise OSError('Game deletion staging directory is not a directory')
        return tombstone_root
    except OSError as exc:
        raise HTTPException(status_code=500, detail='Game deletion could not be completed safely.') from exc


def delete_game(session: Session, game: Game):
    with game_operation_lock(game.id):
        return _delete_game_locked(session, game)


def _delete_game_locked(session: Session, game: Game):
    """Delete current Game assets and rows as one recoverable operation.

    Files are first moved to a tombstone directory inside the uploads dataset.
    This leaves the old rows and assets recoverable if staging or the database
    transaction fails. Once rows are committed, tombstones are removed; failed
    removals are journaled and retried on the next startup.
    """
    uploads_root = get_settings().uploads_path.resolve()
    active_session = session.exec(
        select(GameSession).where(GameSession.game_id == game.id, GameSession.ended_at.is_(None))
    ).first()
    if active_session:
        raise HTTPException(status_code=409, detail='End the active Session before deleting this Game.')
    rulebook = session.exec(select(Rulebook).where(Rulebook.game_id == game.id)).first()
    content = session.exec(select(Content).where(Content.game_id == game.id)).first()
    paths: list[Path] = []
    for value in (
        rulebook.pdf_path if rulebook else None,
        rulebook.extracted_text_path if rulebook else None,
        game.cover_image_path,
    ):
        path = _safe_upload_path(value, uploads_root)
        if value and path is None:
            raise HTTPException(status_code=500, detail='Game deletion could not be completed safely.')
        if path and path not in paths:
            paths.append(path)

    tombstone_root = _create_tombstone_root(uploads_root)
    operation = uuid4().hex
    planned: list[dict[str, str]] = []
    paths_to_stage: list[Path] = []
    for path in paths:
        if not path.exists():
            continue
        tombstone = tombstone_root / path.relative_to(uploads_root)
        paths_to_stage.append(path)
        planned.append({
            'operation': operation,
            'game_id': game.id,
            'phase': 'staging',
            'original': str(path.relative_to(uploads_root)),
            'tombstone': str(tombstone.relative_to(uploads_root)),
        })
    if planned:
        try:
            _write_recovery_journal(uploads_root, planned)
        except OSError as exc:
            try:
                tombstone_root.rmdir()
                tombstone_root.parent.rmdir()
            except OSError:
                logger.warning('Unable to remove unused Game deletion staging directory %s', tombstone_root)
            raise HTTPException(status_code=500, detail='Game deletion could not be prepared safely.') from exc
    staged: list[tuple[Path, Path]] = []
    try:
        for path, planned_entry in zip(paths_to_stage, planned):
            tombstone = uploads_root / planned_entry['tombstone']
            tombstone.parent.mkdir(parents=True, exist_ok=True)
            path.replace(tombstone)
            staged.append((path, tombstone))
    except OSError as exc:
        if _restore_staged(staged):
            _remove_recovery_operation(uploads_root, operation)
        raise HTTPException(status_code=500, detail='Game deletion could not be completed safely.') from exc

    try:
        if rulebook:
            session.delete(rulebook)
        if content:
            session.delete(content)
        session.delete(game)
        session.commit()
    except Exception as exc:
        session.rollback()
        restored = _restore_staged(staged)
        if restored:
            _remove_recovery_operation(uploads_root, operation)
        raise HTTPException(status_code=500, detail='Game deletion could not be completed safely.') from exc

    try:
        _mark_recovery_committed(uploads_root, operation)
    except OSError as exc:
        logger.error('Unable to mark committed Game deletion %s: %s', operation, exc)

    failed_cleanup = [tombstone for _, tombstone in staged if not _remove_path(tombstone)]
    if failed_cleanup:
        try:
            _add_cleanup_journal(uploads_root, failed_cleanup)
            _write_pending_marker(uploads_root, game.id, failed_cleanup)
        except OSError as exc:
            raise HTTPException(status_code=500, detail='Game deletion committed; storage cleanup requires reconciliation.') from exc
        _remove_recovery_operation(uploads_root, operation)
        raise HTTPException(status_code=500, detail='Game deletion committed; storage cleanup requires reconciliation.')
    _remove_recovery_operation(uploads_root, operation)
    try:
        tombstone_root.rmdir()
        tombstone_root.parent.rmdir()
    except OSError:
        pass
