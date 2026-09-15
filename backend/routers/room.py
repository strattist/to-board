import asyncio
import json
from collections import defaultdict
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from backend.core.config import get_settings
from backend.db.engine import engine
from backend.models import Content, Game, GameSession

router = APIRouter(prefix='/api/room', tags=['room'])
_connections: dict[str, set[tuple[asyncio.Queue, asyncio.AbstractEventLoop]]] = defaultdict(set)

def room_payload(slug: str, session: Session):
    record = session.exec(select(GameSession).where(GameSession.room_slug == slug)).first()
    if not record: raise HTTPException(404, 'Room not found.')
    if record.ended_at is not None: return {'ended': True, 'game_title': record.game_title_snapshot, 'room_slug': slug}
    content = session.exec(select(Content).where(Content.game_id == record.game_id)).first()
    if not content or not content.published_quickstart_md or not content.published_cheat_sheet_md:
        raise HTTPException(404, 'Published Content is unavailable for this Room.')
    return {'ended': False, 'game_title': record.game_title_snapshot, 'room_slug': slug, 'quickstart_md': content.published_quickstart_md, 'cheat_sheet_md': content.published_cheat_sheet_md}

@router.get('/{slug}')
def get_room(slug: str):
    with Session(engine) as session: return room_payload(slug, session)

@router.get('/{slug}/events')
async def room_events(slug: str):
    with Session(engine) as session:
        record = session.exec(select(GameSession).where(GameSession.room_slug == slug)).first()
        if not record: raise HTTPException(404, 'Room not found.')
        if record.ended_at is not None:
            async def ended_now():
                yield 'event: session-ended\ndata: {}\n\n'
            return StreamingResponse(ended_now(), media_type='text/event-stream')
    queue: asyncio.Queue = asyncio.Queue(maxsize=2); loop = asyncio.get_running_loop(); _connections[slug].add((queue, loop))
    async def stream():
        try:
            yield ': connected\n\n'
            while True:
                try: event = await asyncio.wait_for(queue.get(), timeout=25)
                except asyncio.TimeoutError:
                    yield ': keepalive\n\n'; continue
                yield event
                break
        finally:
            _connections[slug].discard((queue, loop))
            if not _connections[slug]: _connections.pop(slug, None)
    return StreamingResponse(stream(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive'})

def notify_session_ended(slug: str):
    for queue, loop in list(_connections.get(slug, ())):
        def deliver(q=queue):
            try: q.put_nowait('event: session-ended\ndata: {}\n\n')
            except asyncio.QueueFull: pass
        loop.call_soon_threadsafe(deliver)
