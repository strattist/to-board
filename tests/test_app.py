import os
from pathlib import Path
from uuid import uuid4

DATA = Path('tests/.data')
DATA.mkdir(parents=True, exist_ok=True)
os.environ['DB_PATH'] = str(DATA / 'to-board.db')
os.environ['UPLOADS_PATH'] = str(DATA / 'uploads')
os.environ['AUTH_DISABLED'] = 'true'
os.environ['SECRET_KEY'] = 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='

from fastapi.testclient import TestClient
from sqlmodel import Session, select
from backend.main import app
from backend.db.engine import engine
from backend.models import Content, PipelineState, Rulebook


def test_game_creation_and_validation():
    with TestClient(app) as client:
        response = client.post('/api/games', json={'title': '  Wingspan  '})
        assert response.status_code == 201
        assert response.json()['title'] == 'Wingspan'
        assert response.json()['pipeline_state'] == 'no_rulebook'
        assert client.post('/api/games', json={'title': '   '}).status_code == 422


def test_generation_requires_prerequisites():
    with TestClient(app) as client:
        game = client.get('/api/games').json()[0]
        response = client.post(f"/api/games/{game['id']}/generate", json={'confirm': True})
        assert response.status_code == 422
        assert 'extraction' in response.json()['detail'].lower()


def test_publish_and_reject_are_atomic_and_preserve_published_content():
    with TestClient(app) as client:
        game = client.get('/api/games').json()[0]
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            content.pipeline_state = PipelineState.draft
            content.draft_quickstart_md = '# Draft'
            content.draft_cheat_sheet_md = '- Draft rule'
            content.published_quickstart_md = '# Published'
            content.published_cheat_sheet_md = '- Published rule'
            db.add(content)
            db.commit()
        assert client.post(f"/api/games/{game['id']}/content/reject").status_code == 200
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            assert content.pipeline_state == PipelineState.rejected
            assert content.draft_quickstart_md is None
            assert content.published_quickstart_md == '# Published'


def test_session_room_and_close_state():
    with TestClient(app) as client:
        game = client.get('/api/games').json()[0]
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            content.pipeline_state = PipelineState.published
            content.published_quickstart_md = '# Start'
            content.published_cheat_sheet_md = '- Rule'
            db.add(content)
            db.commit()
        created = client.post(f"/api/sessions?game_id={game['id']}")
        assert created.status_code == 201
        record = created.json()
        assert client.get('/api/room/' + record['room_slug']).json()['quickstart_md'] == '# Start'
        assert client.post('/api/sessions/' + record['id'] + '/end').status_code == 200
        assert client.get('/api/room/' + record['room_slug']).json()['ended'] is True

PDF = b'%PDF-1.4\n1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n4 0 obj<< /Length 44 >>stream\nBT /F1 12 Tf 72 720 Td (Rulebook text) Tj ET\nendstream endobj\n5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\ntrailer<< /Root 1 0 R >>\n%%EOF'


def test_rulebook_upload_and_replacement_is_single_active_row():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Replacement game'}).json()
        first = client.post(f"/api/games/{game['id']}/rulebook", files={'file': ('first.pdf', PDF, 'application/pdf')})
        second = client.post(f"/api/games/{game['id']}/rulebook", files={'file': ('second.pdf', PDF, 'application/pdf')})
        assert first.status_code == second.status_code == 200
        with Session(engine) as db:
            rows = db.exec(select(Rulebook).where(Rulebook.game_id == game['id'])).all()
            assert len(rows) == 1
            assert rows[0].pdf_path.endswith('.pdf')


def test_generation_blocks_when_api_key_is_missing_after_extraction():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Missing key game'}).json()
        with Session(engine) as db:
            rulebook = Rulebook(id=str(uuid4()), game_id=game['id'], pdf_path='tests/.data/rules.pdf', extracted_text_path='tests/.data/rules.txt')
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            content.pipeline_state = PipelineState.ready_to_generate
            db.add(rulebook); db.add(content); db.commit()
        response = client.post(f"/api/games/{game['id']}/generate", json={'confirm': True})
        assert response.status_code == 422
        assert 'API key' in response.json()['detail']
