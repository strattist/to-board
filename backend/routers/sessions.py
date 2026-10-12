import json
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select
from backend.core.auth import require_host
from backend.core.config import get_settings
from backend.db.engine import get_session
from backend.models import Content, Game, GameSession, PipelineState
from backend.services.sessions import create_session, end_session, parse_json, update_metadata
from backend.routers.room import notify_session_ended

logger = logging.getLogger(__name__)
router = APIRouter(prefix='/api/sessions', tags=['sessions'])

class SessionCreate(BaseModel):
    game_id: str

MAX_PLAYERS = 12
MAX_OUTCOMES = 20
MAX_PLAYER_LENGTH = 100
MAX_OUTCOME_LENGTH = 200

class SessionUpdate(BaseModel):
    players: Optional[list[str]] = None
    outcomes: Optional[list[str]] = None

def clean_entries(values: list[str] | None, label: str, max_count: int, max_length: int) -> list[str] | None:
    if values is None: return None
    if len(values) > max_count: raise HTTPException(422, f'A Session can have at most {max_count} {label}s.')
    cleaned = [item.strip() for item in values]
    if any(not item for item in cleaned): raise HTTPException(422, f'Each {label} needs some text.')
    if any('\n' in item or '\r' in item for item in cleaned): raise HTTPException(422, f'Each {label} must be a single line.')
    if any(len(item) > max_length for item in cleaned): raise HTTPException(422, f'Each {label} can have at most {max_length} characters.')
    return cleaned

def utc_iso(value: datetime | None) -> str | None:
    if value is None: return None
    if value.tzinfo is None: value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()

def serialize(record: GameSession) -> dict:
    return {'id': record.id, 'game_id': record.game_id, 'game_title_snapshot': record.game_title_snapshot, 'room_slug': record.room_slug, 'started_at': utc_iso(record.started_at), 'ended_at': utc_iso(record.ended_at), 'players': parse_json(record.players_json), 'outcomes': parse_json(record.outcomes_json), 'active': record.ended_at is None, 'room_url': f"{get_settings().app_base_url.rstrip('/')}/room/{record.room_slug}"}

@router.get('')
def list_sessions(game_id: str | None = None, session: Session = Depends(get_session), _host=Depends(require_host)):
    query = select(GameSession).order_by(GameSession.started_at.desc())
    if game_id: query = query.where(GameSession.game_id == game_id)
    return [serialize(item) for item in session.exec(query).all()]

@router.post('', status_code=201)
def start_session(body: SessionCreate | None = None, game_id: str | None = None, session: Session = Depends(get_session), _host=Depends(require_host)):
    game_id = game_id or (body.game_id if body else None)
    if not game_id: raise HTTPException(422, 'game_id is required.')
    game = session.get(Game, game_id); content = session.exec(select(Content).where(Content.game_id == game_id)).first()
    if not game or not content: raise HTTPException(404, 'Game not found.')
    return serialize(create_session(session, game, content))

@router.get('/{session_id}')
def get_session_record(session_id: str, session: Session = Depends(get_session), _host=Depends(require_host)):
    record = session.get(GameSession, session_id)
    if not record: raise HTTPException(404, 'Session not found.')
    return serialize(record)

@router.patch('/{session_id}')
def update_session_record(session_id: str, body: SessionUpdate, session: Session = Depends(get_session), _host=Depends(require_host)):
    record = session.get(GameSession, session_id)
    if not record: raise HTTPException(404, 'Session not found.')
    players = clean_entries(body.players, 'player name', MAX_PLAYERS, MAX_PLAYER_LENGTH)
    outcomes = clean_entries(body.outcomes, 'outcome', MAX_OUTCOMES, MAX_OUTCOME_LENGTH)
    try:
        update_metadata(record, players, outcomes); session.add(record); session.commit(); session.refresh(record)
    except SQLAlchemyError as exc:
        session.rollback()
        logger.exception('Players and outcomes could not be saved for Session %s', session_id)
        raise HTTPException(500, 'Players and outcomes could not be saved. The previous values are kept.') from exc
    return serialize(record)

@router.post('/{session_id}/end')
def close_session(session_id: str, session: Session = Depends(get_session), _host=Depends(require_host)):
    record = session.get(GameSession, session_id)
    if not record: raise HTTPException(404, 'Session not found.')
    if end_session(session, record):
        try: notify_session_ended(record.room_slug)
        except Exception: logger.exception('Guests of Room %s could not be notified', record.room_slug)
    return serialize(record)
