import json
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
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

class SessionUpdate(BaseModel):
    players: Optional[list[str]] = Field(default=None, max_length=12)
    outcomes: Optional[list[str]] = Field(default=None, max_length=20)

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
    for values in (body.players, body.outcomes):
        if values is not None and any(not item.strip() for item in values): raise HTTPException(422, 'Names and outcomes cannot be empty.')
    update_metadata(record, body.players, body.outcomes); session.add(record); session.commit(); session.refresh(record)
    return serialize(record)

@router.post('/{session_id}/end')
def close_session(session_id: str, session: Session = Depends(get_session), _host=Depends(require_host)):
    record = session.get(GameSession, session_id)
    if not record: raise HTTPException(404, 'Session not found.')
    if end_session(session, record):
        try: notify_session_ended(record.room_slug)
        except Exception: logger.exception('Guests of Room %s could not be notified', record.room_slug)
    return serialize(record)
