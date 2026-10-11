"""Shared test bootstrap: the environment must be set before any backend import."""
from io import BytesIO
from pathlib import Path
import os

DATA = Path('tests/.data')
DATA.mkdir(parents=True, exist_ok=True)
os.environ['DB_PATH'] = str(DATA / 'to-board.db')
os.environ['UPLOADS_PATH'] = str(DATA / 'uploads')
os.environ['AUTH_DISABLED'] = 'true'
os.environ['SECRET_KEY'] = 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='

from PIL import Image
from backend.db.engine import engine
from backend.models import Content, Game, PipelineState
from sqlmodel import Session, select


def encoded_image(format_name: str) -> bytes:
    output = BytesIO()
    Image.new('RGB', (2, 2), color='purple').save(output, format=format_name)
    return output.getvalue()


def stored_cover_path(game_id: str) -> Path:
    with Session(engine) as db:
        game = db.get(Game, game_id)
        assert game is not None and game.cover_image_path is not None
        return Path(game.cover_image_path)


PDF = b'%PDF-1.4\n1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n4 0 obj<< /Length 44 >>stream\nBT /F1 12 Tf 72 720 Td (Rulebook text) Tj ET\nendstream endobj\n5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\ntrailer<< /Root 1 0 R >>\n%%EOF'


def _publish_pair(game_id: str, state: PipelineState):
    with Session(engine) as db:
        content = db.exec(select(Content).where(Content.game_id == game_id)).one()
        content.pipeline_state = state
        content.published_quickstart_md = '# Start'
        content.published_cheat_sheet_md = '- Rule'
        db.add(content)
        db.commit()


def _published_game(client, title):
    game = client.post('/api/games', json={'title': title}).json()
    with Session(engine) as db:
        content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
        content.pipeline_state = PipelineState.published
        content.published_quickstart_md = '# Start'
        content.published_cheat_sheet_md = '- Rule'
        db.add(content)
        db.commit()
    return game


async def _make_queue():
    import asyncio
    return asyncio.Queue(maxsize=2)
