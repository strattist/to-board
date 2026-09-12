from pathlib import Path
from sqlmodel import Session, select
from fastapi import HTTPException
from backend.core.config import get_settings
from backend.core.utils import slugify, uuid4_str
from backend.models import Content, Game, Rulebook
from backend.services.content import get_or_create

def create_game(session: Session, title: str) -> Game:
    title = title.strip()
    if not title:
        raise HTTPException(status_code=422, detail='Game title is required.')
    game = Game(id=uuid4_str(), title=title, room_slug_prefix=slugify(title))
    session.add(game)
    get_or_create(session, game.id)
    session.commit(); session.refresh(game)
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
