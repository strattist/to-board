from io import BytesIO
from pathlib import Path
import warnings
from sqlmodel import Session, select
from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError
from PIL.Image import DecompressionBombError, DecompressionBombWarning
from backend.core.config import get_settings
from backend.core.utils import slugify, uuid4_str
from backend.models import Content, Game, Rulebook
from backend.services.content import get_or_create

MAX_COVER_BYTES = 10 * 1024 * 1024
COVER_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
MAX_GAME_TITLE_LENGTH = 200


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

def remove_file(path: str | None):
    if path:
        try: Path(path).unlink(missing_ok=True)
        except OSError: pass

def delete_game(session: Session, game: Game):
    rulebook = session.exec(select(Rulebook).where(Rulebook.game_id == game.id)).first()
    content = session.exec(select(Content).where(Content.game_id == game.id)).first()
    if rulebook:
        remove_file(rulebook.pdf_path); remove_file(rulebook.extracted_text_path); session.delete(rulebook)
    if game.cover_image_path: remove_file(game.cover_image_path)
    if content: session.delete(content)
    session.delete(game)
    session.commit()
