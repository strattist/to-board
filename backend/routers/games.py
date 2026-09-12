import asyncio
import json
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from backend.core.auth import require_host
from backend.core.config import get_settings
from backend.core.utils import uuid4_str
from backend.db.engine import get_session
from backend.models import Content, Game, Rulebook, PipelineState, AppSettings
from backend.services.content import begin_extraction, begin_generation, get_or_create, publish, reject, reset_for_rulebook
from backend.services.games import create_game, delete_game
from backend.workers.extraction import run_extraction
from backend.workers.generation import run_generation

router = APIRouter(prefix='/api/games', tags=['games'])

class GameCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
class GameUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
class GenerationRequest(BaseModel):
    confirm: bool = False

def payload(session: Session, game: Game) -> dict:
    rulebook = session.exec(select(Rulebook).where(Rulebook.game_id == game.id)).first()
    content = get_or_create(session, game.id)
    return {
        'id': game.id, 'title': game.title, 'cover_image_path': game.cover_image_path,
        'room_slug_prefix': game.room_slug_prefix, 'created_at': game.created_at,
        'rulebook': {'id': rulebook.id, 'uploaded_at': rulebook.uploaded_at, 'has_extracted_text': bool(rulebook.extracted_text_path)} if rulebook else None,
        'pipeline_state': content.pipeline_state.value, 'error_message': content.error_message,
        'has_published_content': bool(content.published_quickstart_md and content.published_cheat_sheet_md),
        'has_draft_content': bool(content.draft_quickstart_md and content.draft_cheat_sheet_md),
    }

@router.get('')
def list_games(session: Session = Depends(get_session), _host=Depends(require_host)):
    return [payload(session, game) for game in session.exec(select(Game).order_by(Game.created_at)).all()]

@router.post('', status_code=status.HTTP_201_CREATED)
def add_game(body: GameCreate, session: Session = Depends(get_session), _host=Depends(require_host)):
    game = create_game(session, body.title)
    return payload(session, game)

@router.get('/{game_id}')
def get_game(game_id: str, session: Session = Depends(get_session), _host=Depends(require_host)):
    game = session.get(Game, game_id)
    if not game: raise HTTPException(404, 'Game not found.')
    return payload(session, game)

@router.patch('/{game_id}')
def update_game(game_id: str, body: GameUpdate, session: Session = Depends(get_session), _host=Depends(require_host)):
    game = session.get(Game, game_id)
    if not game: raise HTTPException(404, 'Game not found.')
    if body.title is not None:
        title = body.title.strip()
        if not title: raise HTTPException(422, 'Game title is required.')
        game.title = title
    session.add(game); session.commit(); session.refresh(game)
    return payload(session, game)

@router.delete('/{game_id}', status_code=204)
def remove_game(game_id: str, session: Session = Depends(get_session), _host=Depends(require_host)):
    game = session.get(Game, game_id)
    if not game: raise HTTPException(404, 'Game not found.')
    delete_game(session, game)

@router.post('/{game_id}/rulebook')
async def upload_rulebook(game_id: str, background_tasks: BackgroundTasks, file: UploadFile = File(...), session: Session = Depends(get_session), _host=Depends(require_host)):
    game = session.get(Game, game_id)
    if not game: raise HTTPException(404, 'Game not found.')
    settings = get_settings(); max_bytes = settings.max_upload_mb * 1024 * 1024
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(422, 'Only PDF rulebooks are accepted.')
    content_bytes = await file.read(max_bytes + 1)
    if len(content_bytes) > max_bytes or not content_bytes.startswith(b'%PDF'):
        raise HTTPException(422, 'The rulebook must be a valid PDF no larger than 100 MB.')
    game_dir = settings.uploads_path / 'rulebooks' / game_id
    game_dir.mkdir(parents=True, exist_ok=True)
    new_pdf = game_dir / f'{uuid4_str()}.pdf'
    new_pdf.write_bytes(content_bytes)
    old = session.exec(select(Rulebook).where(Rulebook.game_id == game_id)).first()
    old_paths = [old.pdf_path, old.extracted_text_path] if old else []
    if old: session.delete(old)
    content_record = get_or_create(session, game_id)
    reset_for_rulebook(session, content_record)
    rulebook = Rulebook(id=uuid4_str(), game_id=game_id, pdf_path=str(new_pdf))
    session.add(rulebook)
    begin_extraction(session, game_id)
    session.commit(); session.refresh(rulebook)
    for old_path in old_paths:
        if old_path:
            try: Path(old_path).unlink(missing_ok=True)
            except OSError: pass
    background_tasks.add_task(run_extraction, game_id, rulebook.id)
    return payload(session, game)

@router.post('/{game_id}/cover')
async def upload_cover(game_id: str, file: UploadFile = File(...), session: Session = Depends(get_session), _host=Depends(require_host)):
    game = session.get(Game, game_id)
    if not game: raise HTTPException(404, 'Game not found.')
    if not file.filename or Path(file.filename).suffix.lower() not in {'.jpg', '.jpeg', '.png', '.webp'}:
        raise HTTPException(422, 'Cover image must be JPEG, PNG, or WebP.')
    data = await file.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024: raise HTTPException(422, 'Cover image must be no larger than 10 MB.')
    target = get_settings().uploads_path / 'covers' / f'{game_id}{Path(file.filename).suffix.lower()}'
    target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
    if game.cover_image_path and game.cover_image_path != str(target):
        try: Path(game.cover_image_path).unlink(missing_ok=True)
        except OSError: pass
    game.cover_image_path = str(target); session.add(game); session.commit(); session.refresh(game)
    return payload(session, game)

@router.get('/{game_id}/cover/file')
def cover_file(game_id: str, session: Session = Depends(get_session), _host=Depends(require_host)):
    game = session.get(Game, game_id)
    if not game or not game.cover_image_path: raise HTTPException(404, 'Cover image not found.')
    return FileResponse(game.cover_image_path)

@router.get('/{game_id}/rulebook')
def rulebook_info(game_id: str, session: Session = Depends(get_session), _host=Depends(require_host)):
    game = session.get(Game, game_id); rulebook = session.exec(select(Rulebook).where(Rulebook.game_id == game_id)).first()
    if not game or not rulebook: raise HTTPException(404, 'Rulebook not found.')
    return {'game_id': game_id, 'pdf_path': rulebook.pdf_path, 'uploaded_at': rulebook.uploaded_at}

@router.get('/{game_id}/rulebook/file')
def rulebook_file(game_id: str, session: Session = Depends(get_session), _host=Depends(require_host)):
    rulebook = session.exec(select(Rulebook).where(Rulebook.game_id == game_id)).first()
    if not rulebook: raise HTTPException(404, 'Rulebook not found.')
    return FileResponse(rulebook.pdf_path, media_type='application/pdf', filename=Path(rulebook.pdf_path).name)

@router.post('/{game_id}/generate')
def generate(game_id: str, body: GenerationRequest, background_tasks: BackgroundTasks, session: Session = Depends(get_session), _host=Depends(require_host)):
    game = session.get(Game, game_id); rulebook = session.exec(select(Rulebook).where(Rulebook.game_id == game_id)).first(); settings = session.get(AppSettings, 1)
    if not game: raise HTTPException(404, 'Game not found.')
    if not rulebook or not rulebook.extracted_text_path: raise HTTPException(422, 'Rulebook extraction is not complete.')
    if not settings or not settings.api_key_encrypted: raise HTTPException(422, 'API key is missing — add one in Settings.')
    content = get_or_create(session, game_id)
    if content.pipeline_state == PipelineState.generating: raise HTTPException(409, 'Content generation is already in progress.')
    begin_generation(session, game_id)
    session.commit(); background_tasks.add_task(run_generation, game_id)
    return payload(session, game)

@router.get('/{game_id}/content')
def get_content(game_id: str, session: Session = Depends(get_session), _host=Depends(require_host)):
    game = session.get(Game, game_id); content = session.exec(select(Content).where(Content.game_id == game_id)).first()
    if not game or not content: raise HTTPException(404, 'Content not found.')
    return {'game_id': game_id, 'pipeline_state': content.pipeline_state.value, 'draft_quickstart_md': content.draft_quickstart_md, 'draft_cheat_sheet_md': content.draft_cheat_sheet_md, 'published_quickstart_md': content.published_quickstart_md, 'published_cheat_sheet_md': content.published_cheat_sheet_md}

@router.post('/{game_id}/content/publish')
def publish_content(game_id: str, session: Session = Depends(get_session), _host=Depends(require_host)):
    content = session.exec(select(Content).where(Content.game_id == game_id)).first()
    if not content: raise HTTPException(404, 'Content not found.')
    publish(session, content); session.commit(); return {'pipeline_state': content.pipeline_state.value}

@router.post('/{game_id}/content/reject')
def reject_content(game_id: str, session: Session = Depends(get_session), _host=Depends(require_host)):
    content = session.exec(select(Content).where(Content.game_id == game_id)).first()
    if not content: raise HTTPException(404, 'Content not found.')
    reject(session, content); session.commit(); return {'pipeline_state': content.pipeline_state.value}

@router.get('/{game_id}/preview')
def preview(game_id: str, session: Session = Depends(get_session), _host=Depends(require_host)):
    game = session.get(Game, game_id); content = session.exec(select(Content).where(Content.game_id == game_id)).first()
    if not game or not content or not content.published_quickstart_md or not content.published_cheat_sheet_md: raise HTTPException(404, 'Published Content not found.')
    return {'game': {'id': game.id, 'title': game.title}, 'quickstart_md': content.published_quickstart_md, 'cheat_sheet_md': content.published_cheat_sheet_md}
