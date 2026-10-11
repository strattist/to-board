import json
import logging
import secrets
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import update
from sqlmodel import Session, select
from fastapi import HTTPException
from backend.models import Content, Game, GameSession
from backend.core.utils import uuid4_str

logger = logging.getLogger(__name__)

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
    try:
        for attempt in range(3):
            active = session.exec(select(GameSession).where(GameSession.game_id == game.id, GameSession.ended_at.is_(None))).first()
            if active:
                raise HTTPException(status_code=409, detail='This Game already has an active Session.')
            record = GameSession(id=uuid4_str(), game_id=game.id, game_title_snapshot=game.title, room_slug=make_room_slug(game.room_slug_prefix, session))
            try:
                session.add(record)
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                # The database is the arbiter: a concurrent start took the active slot or this Room slug.
                if 'room_slug' in str(exc.orig) and attempt < 2:
                    continue
                if 'room_slug' not in str(exc.orig):
                    raise HTTPException(status_code=409, detail='This Game already has an active Session.') from exc
                raise
            session.refresh(record)
            return record
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        session.rollback()
        logger.exception('Session could not be saved for Game %s', game.id)
        raise HTTPException(status_code=500, detail='Session could not be saved. No Room was created.') from exc

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

def end_session(session: Session, record: GameSession) -> bool:
    """Persist the end of a Session. Returns True only when this call changed it."""
    if record.ended_at is not None:
        return False
    session_id = record.id
    try:
        # Conditional update: of two concurrent end requests, exactly one wins and notifies.
        result = session.exec(update(GameSession).where(GameSession.id == session_id, GameSession.ended_at.is_(None)).values(ended_at=datetime.now(timezone.utc)))
        session.commit()
        session.refresh(record)
    except SQLAlchemyError as exc:
        session.rollback()
        logger.exception('Session %s could not be ended', session_id)
        raise HTTPException(status_code=500, detail='Session could not be ended. The Room is still open.') from exc
    return result.rowcount == 1
