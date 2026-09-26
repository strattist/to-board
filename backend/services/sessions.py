import json
import secrets
from datetime import datetime, timezone
from sqlmodel import Session, select
from fastapi import HTTPException
from backend.models import Content, Game, GameSession
from backend.core.utils import uuid4_str

def make_room_slug(prefix: str, session: Session) -> str:
    for _ in range(20):
        suffix = ''.join(secrets.choice('0123456789abcdefghijklmnopqrstuvwxyz') for _ in range(4))
        slug = f'{prefix}-{suffix}'
        if not session.exec(select(GameSession).where(GameSession.room_slug == slug)).first():
            return slug
    raise HTTPException(status_code=500, detail='Could not allocate a unique Room URL.')

def create_session(session: Session, game: Game, content: Content) -> GameSession:
    if not content.published_quickstart_md or not content.published_cheat_sheet_md:
        raise HTTPException(status_code=422, detail='Published Content is required to start a Session.')
    active = session.exec(select(GameSession).where(GameSession.game_id == game.id, GameSession.ended_at.is_(None))).first()
    if active:
        raise HTTPException(status_code=409, detail='This Game already has an active Session.')
    record = GameSession(id=uuid4_str(), game_id=game.id, game_title_snapshot=game.title, room_slug=make_room_slug(game.room_slug_prefix, session))
    session.add(record)
    session.commit()
    session.refresh(record)
    return record

def parse_json(value: str):
    try:
        return json.loads(value)
    except Exception:
        return []

def update_metadata(record: GameSession, players: list[str] | None, outcomes: list[str] | None):
    if players is not None:
        record.players_json = json.dumps(players)
    if outcomes is not None:
        record.outcomes_json = json.dumps(outcomes)

def end_session(record: GameSession):
    if record.ended_at is None:
        record.ended_at = datetime.now(timezone.utc)
