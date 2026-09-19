import os
import base64
import json
import shutil
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

DATA = Path('tests/.data')
DATA.mkdir(parents=True, exist_ok=True)
os.environ['DB_PATH'] = str(DATA / 'to-board.db')
os.environ['UPLOADS_PATH'] = str(DATA / 'uploads')
os.environ['AUTH_DISABLED'] = 'true'
os.environ['SECRET_KEY'] = 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='

from fastapi.testclient import TestClient
import pytest
from PIL import Image
from sqlmodel import Session, delete, select
from backend.main import app
from backend.db.engine import engine
from backend.core.config import get_settings
from backend.models import Content, Game, PipelineState, Rulebook
from backend.services.extraction import extract_pdf
from backend.workers.extraction import run_extraction
from backend.workers.generation import run_generation


@pytest.fixture(autouse=True)
def reset_test_data():
    with Session(engine) as db:
        db.exec(delete(Rulebook))
        db.exec(delete(Content))
        db.exec(delete(Game))
        db.commit()
    shutil.rmtree(DATA / 'uploads', ignore_errors=True)
    (DATA / 'uploads').mkdir(parents=True, exist_ok=True)
    yield


def encoded_image(format_name: str) -> bytes:
    output = BytesIO()
    Image.new('RGB', (2, 2), color='purple').save(output, format=format_name)
    return output.getvalue()


def test_game_creation_and_validation():
    with TestClient(app) as client:
        response = client.post('/api/games', json={'title': '  Wingspan  '})
        assert response.status_code == 201
        assert response.json()['title'] == 'Wingspan'
        assert response.json()['pipeline_state'] == 'no_rulebook'
        assert client.post('/api/games', json={'title': '   '}).status_code == 422


def test_game_creation_with_cover_is_atomic():
    with TestClient(app) as client:
        image = encoded_image('PNG')
        created = client.post(
            '/api/games/with-cover',
            data={'title': '  Atomic cover  '},
            files={'file': ('cover.png', image, 'image/png')},
        )
        assert created.status_code == 201
        game = created.json()
        assert game['title'] == 'Atomic cover'
        assert Path(game['cover_image_path']).read_bytes() == image

        too_long = client.post(
            '/api/games/with-cover',
            data={'title': 'x' * 201},
            files={'file': ('cover.png', image, 'image/png')},
        )
        assert too_long.status_code == 422

        rejected = client.post(
            '/api/games/with-cover',
            data={'title': 'Should not persist'},
            files={'file': ('cover.png', b'not an image', 'image/png')},
        )
        assert rejected.status_code == 422
        assert [item['title'] for item in client.get('/api/games').json()] == ['Atomic cover']


def test_collection_metadata_and_cover_validation():
    with TestClient(app) as client:
        assert client.get('/api/games').json() == []
        created = client.post('/api/games', json={'title': '  Cover test  '})
        assert created.status_code == 201
        game = created.json()
        parsed_id = UUID(game['id'])
        assert parsed_id.version == 4
        assert game['title'] == 'Cover test'
        assert game['created_at'].endswith('+00:00')

        listing = client.get('/api/games')
        assert listing.status_code == 200
        assert any(item['id'] == game['id'] for item in listing.json())

        png = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
        )
        uploaded = client.post(
            f"/api/games/{game['id']}/cover",
            files={'file': ('cover.png', png, 'image/png')},
        )
        assert uploaded.status_code == 200
        cover = uploaded.json()
        cover_path = Path(cover['cover_image_path'])
        assert cover_path.is_file()
        assert cover_path.read_bytes() == png
        assert cover['cover_url'].startswith(f"/api/games/{game['id']}/cover/file?v=")
        assert client.get(cover['cover_url']).content == png

        invalid = client.post(
            f"/api/games/{game['id']}/cover",
            files={'file': ('replacement.png', b'not an image', 'image/png')},
        )
        assert invalid.status_code == 422
        assert cover_path.read_bytes() == png

        unsupported = client.post(
            f"/api/games/{game['id']}/cover",
            files={'file': ('replacement.gif', b'GIF89a', 'image/gif')},
        )
        assert unsupported.status_code == 422
        assert cover_path.read_bytes() == png

        oversized = client.post(
            f"/api/games/{game['id']}/cover",
            files={'file': ('oversized.png', b'x' * (10 * 1024 * 1024 + 1), 'image/png')},
        )
        assert oversized.status_code == 422
        assert cover_path.read_bytes() == png

        malformed = bytearray(png)
        malformed[29] ^= 0xFF
        invalid_crc = client.post(
            f"/api/games/{game['id']}/cover",
            files={'file': ('malformed.png', bytes(malformed), 'image/png')},
        )
        assert invalid_crc.status_code == 422
        assert cover_path.read_bytes() == png

        mismatched = client.post(
            f"/api/games/{game['id']}/cover",
            files={'file': ('mismatched.jpg', png, 'image/jpeg')},
        )
        assert mismatched.status_code == 422
        assert cover_path.read_bytes() == png

        for filename, image in [('cover.jpg', encoded_image('JPEG')), ('cover.webp', encoded_image('WEBP'))]:
            replacement = client.post(
                f"/api/games/{game['id']}/cover",
                files={'file': (filename, image, 'image/*')},
            )
            assert replacement.status_code == 200
            assert Path(replacement.json()['cover_image_path']).read_bytes() == image


def test_game_management_requires_host():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Protected game'}).json()
        settings = get_settings()
        previous = settings.auth_disabled
        settings.auth_disabled = False
        try:
            assert client.get('/api/games').status_code == 401
            assert client.post('/api/games', json={'title': 'Should not exist'}).status_code == 401
            assert client.post(
                f"/api/games/{game['id']}/cover",
                files={'file': ('cover.png', b'not an image', 'image/png')},
            ).status_code == 401
            assert client.post(
                f"/api/games/{game['id']}/rulebook",
                files={'file': ('rules.pdf', PDF, 'application/pdf')},
            ).status_code == 401
        finally:
            settings.auth_disabled = previous


def test_generation_requires_prerequisites():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Generation prerequisites'}).json()
        response = client.post(f"/api/games/{game['id']}/generate", json={'confirm': True})
        assert response.status_code == 422
        assert 'extraction' in response.json()['detail'].lower()


def test_publish_and_reject_are_atomic_and_preserve_published_content():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Publish test'}).json()
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
        game = client.post('/api/games', json={'title': 'Session test'}).json()
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


def test_missing_cover_file_returns_not_found():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Missing cover'}).json()
        image = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
        )
        uploaded = client.post(f"/api/games/{game['id']}/cover", files={'file': ('cover.png', image, 'image/png')})
        assert uploaded.status_code == 200
        Path(uploaded.json()['cover_image_path']).unlink()
        assert client.get(uploaded.json()['cover_url']).status_code == 404


def test_cover_filesystem_failure_restores_previous_cover(monkeypatch):
    with TestClient(app, raise_server_exceptions=False) as client:
        game = client.post('/api/games', json={'title': 'Cover rollback'}).json()
        original = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
        )
        uploaded = client.post(f"/api/games/{game['id']}/cover", files={'file': ('cover.png', original, 'image/png')})
        assert uploaded.status_code == 200
        original_replace = Path.replace

        def fail_temporary_replace(path: Path, destination: Path):
            if path.name.endswith('.tmp'):
                raise OSError('simulated filesystem failure')
            return original_replace(path, destination)

        monkeypatch.setattr(Path, 'replace', fail_temporary_replace)
        failed = client.post(f"/api/games/{game['id']}/cover", files={'file': ('replacement.jpg', encoded_image('JPEG'), 'image/jpeg')})
        assert failed.status_code == 500
        assert Path(uploaded.json()['cover_image_path']).read_bytes() == original
        restored = client.get(f"/api/games/{game['id']}")
        assert restored.status_code == 200
        assert restored.json()['cover_image_path'] == uploaded.json()['cover_image_path']
        assert client.get(restored.json()['cover_url']).content == original

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


def test_rulebook_validation_preserves_existing_file(monkeypatch):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Validation game'}).json()
        monkeypatch.setattr('backend.routers.games.run_extraction', lambda *_args: None)
        uploaded = client.post(f"/api/games/{game['id']}/rulebook", files={'file': ('rules.pdf', PDF, 'application/pdf')})
        assert uploaded.status_code == 200
        with Session(engine) as db:
            existing = db.exec(select(Rulebook).where(Rulebook.game_id == game['id'])).first()
            old_path = Path(existing.pdf_path)
        malformed = client.post(
            f"/api/games/{game['id']}/rulebook",
            files={'file': ('broken.pdf', b'%PDF-1.7\ntruncated', 'application/pdf')},
        )
        assert malformed.status_code == 422
        settings = get_settings()
        previous_limit = settings.max_upload_mb
        settings.max_upload_mb = 1
        try:
            oversized = client.post(
                f"/api/games/{game['id']}/rulebook",
                files={'file': ('large.pdf', b'%PDF' + b'x' * (1024 * 1024), 'application/pdf')},
            )
        finally:
            settings.max_upload_mb = previous_limit
        assert oversized.status_code == 422
        with Session(engine) as db:
            current = db.exec(select(Rulebook).where(Rulebook.game_id == game['id'])).one()
            assert current.pdf_path == str(old_path)
        assert old_path.read_bytes() == PDF


def test_rulebook_replacement_cleans_files_and_preserves_published_content(monkeypatch):
    with TestClient(app) as client:
        monkeypatch.setattr('backend.routers.games.run_extraction', lambda *_args: None)
        game = client.post('/api/games', json={'title': 'Content preservation'}).json()
        first = client.post(f"/api/games/{game['id']}/rulebook", files={'file': ('first.pdf', PDF, 'application/pdf')})
        assert first.status_code == 200
        with Session(engine) as db:
            old = db.exec(select(Rulebook).where(Rulebook.game_id == game['id'])).one()
            old_text = Path(old.pdf_path).with_suffix('.txt')
            old_text.write_text('old extracted text', encoding='utf-8')
            old.extracted_text_path = str(old_text)
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.pipeline_state = PipelineState.draft
            content.draft_quickstart_md = '# Old draft'
            content.draft_cheat_sheet_md = '- Old draft rule'
            content.published_quickstart_md = '# Published guide'
            content.published_cheat_sheet_md = '- Published rule'
            db.add(old)
            db.add(content)
            db.commit()
            old_pdf = Path(old.pdf_path)
        second = client.post(f"/api/games/{game['id']}/rulebook", files={'file': ('second.pdf', PDF, 'application/pdf')})
        assert second.status_code == 200
        with Session(engine) as db:
            current = db.exec(select(Rulebook).where(Rulebook.game_id == game['id'])).one()
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            assert current.pdf_path != str(old_pdf)
            assert content.pipeline_state == PipelineState.extracting
            assert content.draft_quickstart_md is None
            assert content.draft_cheat_sheet_md is None
            assert content.published_quickstart_md == '# Published guide'
            assert content.published_cheat_sheet_md == '- Published rule'
            assert Path(current.pdf_path).is_absolute()
        assert not old_pdf.exists()
        assert not old_text.exists()


def test_extraction_persists_absolute_text_path(monkeypatch):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Extraction path'}).json()
        monkeypatch.setattr('backend.routers.games.run_extraction', lambda *_args: None)
        uploaded = client.post(
            f"/api/games/{game['id']}/rulebook",
            files={'file': ('rules.pdf', PDF, 'application/pdf')},
        )
        rulebook_id = uploaded.json()['rulebook']['id']
        run_extraction(game['id'], rulebook_id)
        with Session(engine) as db:
            rulebook = db.exec(select(Rulebook).where(Rulebook.game_id == game['id'])).one()
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            assert Path(rulebook.extracted_text_path).is_absolute()
            assert Path(rulebook.extracted_text_path).is_file()
            assert content.pipeline_state == PipelineState.ready_to_generate


def test_rulebook_filesystem_failure_keeps_previous_state(monkeypatch):
    with TestClient(app, raise_server_exceptions=False) as client:
        monkeypatch.setattr('backend.routers.games.run_extraction', lambda *_args: None)
        game = client.post('/api/games', json={'title': 'Rulebook rollback'}).json()
        first = client.post(f"/api/games/{game['id']}/rulebook", files={'file': ('first.pdf', PDF, 'application/pdf')})
        assert first.status_code == 200
        with Session(engine) as db:
            old_path = Path(db.exec(select(Rulebook).where(Rulebook.game_id == game['id'])).one().pdf_path)
        original_replace = Path.replace

        def fail_staging(path: Path, destination: Path):
            if path.name.endswith('.part'):
                raise OSError('simulated staging failure')
            return original_replace(path, destination)

        monkeypatch.setattr(Path, 'replace', fail_staging)
        failed = client.post(f"/api/games/{game['id']}/rulebook", files={'file': ('replacement.pdf', PDF, 'application/pdf')})
        assert failed.status_code == 500
        with Session(engine) as db:
            current = db.exec(select(Rulebook).where(Rulebook.game_id == game['id'])).one()
            assert current.pdf_path == str(old_path)
        assert old_path.read_bytes() == PDF
        assert not list(old_path.parent.glob('*.part'))


def test_rulebook_cleanup_journal_retries_failed_old_file_cleanup(monkeypatch):
    with TestClient(app) as client:
        monkeypatch.setattr('backend.routers.games.run_extraction', lambda *_args: None)
        game = client.post('/api/games', json={'title': 'Cleanup retry'}).json()
        first = client.post(f"/api/games/{game['id']}/rulebook", files={'file': ('first.pdf', PDF, 'application/pdf')})
        assert first.status_code == 200
        with Session(engine) as db:
            old_path = Path(db.exec(select(Rulebook).where(Rulebook.game_id == game['id'])).one().pdf_path)
        original_unlink = Path.unlink
        attempts = 0

        def fail_old_once(path: Path, *args, **kwargs):
            nonlocal attempts
            if path == old_path and attempts == 0:
                attempts += 1
                raise OSError('transient cleanup failure')
            return original_unlink(path, *args, **kwargs)

        monkeypatch.setattr(Path, 'unlink', fail_old_once)
        second = client.post(f"/api/games/{game['id']}/rulebook", files={'file': ('second.pdf', PDF, 'application/pdf')})
        assert second.status_code == 200
        assert attempts == 1
        assert not old_path.exists()
        assert not (old_path.parents[2] / '.rulebook-cleanup.json').exists()


def test_rulebook_cleanup_journal_tracks_persistent_failure(monkeypatch):
    with TestClient(app) as client:
        monkeypatch.setattr('backend.routers.games.run_extraction', lambda *_args: None)
        game = client.post('/api/games', json={'title': 'Cleanup journal'}).json()
        first = client.post(f"/api/games/{game['id']}/rulebook", files={'file': ('first.pdf', PDF, 'application/pdf')})
        assert first.status_code == 200
        with Session(engine) as db:
            old_path = Path(db.exec(select(Rulebook).where(Rulebook.game_id == game['id'])).one().pdf_path)
        original_unlink = Path.unlink

        def fail_old(path: Path, *args, **kwargs):
            if path == old_path:
                raise OSError('persistent cleanup failure')
            return original_unlink(path, *args, **kwargs)

        monkeypatch.setattr(Path, 'unlink', fail_old)
        second = client.post(f"/api/games/{game['id']}/rulebook", files={'file': ('second.pdf', PDF, 'application/pdf')})
        assert second.status_code == 200
        journal = old_path.parents[2] / '.rulebook-cleanup.json'
        assert old_path.exists()
        assert str(old_path.relative_to(old_path.parents[2])) in json.loads(journal.read_text(encoding='utf-8'))
        monkeypatch.setattr(Path, 'unlink', original_unlink)
        third = client.post(f"/api/games/{game['id']}/rulebook", files={'file': ('third.pdf', PDF, 'application/pdf')})
        assert third.status_code == 200
        assert not old_path.exists()
        assert not journal.exists()


def test_extraction_publication_preserves_existing_output_on_rename_failure(tmp_path, monkeypatch):
    pdf_path = tmp_path / 'rulebook.pdf'
    output_path = tmp_path / 'rulebook.txt'
    pdf_path.write_bytes(PDF)
    output_path.write_text('previous extraction', encoding='utf-8')
    original_replace = Path.replace

    def fail_output_replace(path: Path, destination: Path):
        if path.name.endswith('.part') and destination == output_path:
            raise OSError('simulated output rename failure')
        return original_replace(path, destination)

    monkeypatch.setattr(Path, 'replace', fail_output_replace)
    with pytest.raises(OSError):
        extract_pdf(str(pdf_path), str(output_path))
    assert output_path.read_text(encoding='utf-8') == 'previous extraction'
    assert not list(tmp_path.glob('*.part'))


def test_rulebook_database_failure_keeps_committed_file_consistent(monkeypatch):
    with TestClient(app, raise_server_exceptions=False) as client:
        monkeypatch.setattr('backend.routers.games.run_extraction', lambda *_args: None)
        game = client.post('/api/games', json={'title': 'Database rollback'}).json()
        first = client.post(f"/api/games/{game['id']}/rulebook", files={'file': ('first.pdf', PDF, 'application/pdf')})
        assert first.status_code == 200
        original_commit = Session.commit

        def fail_commit(self):
            raise RuntimeError('simulated database failure')

        monkeypatch.setattr('backend.services.rulebooks.Session.commit', fail_commit)
        failed = client.post(f"/api/games/{game['id']}/rulebook", files={'file': ('replacement.pdf', PDF, 'application/pdf')})
        assert failed.status_code == 500
        with Session(engine) as db:
            current = db.exec(select(Rulebook).where(Rulebook.game_id == game['id'])).one()
            assert Path(current.pdf_path).is_file()
            assert len(list(Path(current.pdf_path).parent.glob('*.pdf'))) == 1
        monkeypatch.setattr(Session, 'commit', original_commit)


def test_rulebook_refresh_failure_does_not_delete_committed_file(monkeypatch):
    with TestClient(app, raise_server_exceptions=False) as client:
        monkeypatch.setattr('backend.routers.games.run_extraction', lambda *_args: None)
        game = client.post('/api/games', json={'title': 'Refresh failure'}).json()

        def fail_refresh(self, _instance):
            raise RuntimeError('simulated refresh failure')

        monkeypatch.setattr('backend.services.rulebooks.Session.refresh', fail_refresh)
        failed = client.post(f"/api/games/{game['id']}/rulebook", files={'file': ('rules.pdf', PDF, 'application/pdf')})
        assert failed.status_code == 500
        with Session(engine) as db:
            current = db.exec(select(Rulebook).where(Rulebook.game_id == game['id'])).one()
            assert Path(current.pdf_path).is_file()


def test_extraction_failure_removes_partial_output(monkeypatch):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Extraction failure'}).json()
        monkeypatch.setattr('backend.routers.games.run_extraction', lambda *_args: None)
        uploaded = client.post(
            f"/api/games/{game['id']}/rulebook",
            files={'file': ('rules.pdf', PDF, 'application/pdf')},
        )
        rulebook_id = uploaded.json()['rulebook']['id']

        def fail_extract(_pdf_path, output_path):
            Path(output_path).write_text('partial', encoding='utf-8')
            raise RuntimeError('simulated extraction failure')

        monkeypatch.setattr('backend.workers.extraction.extract_pdf', fail_extract)
        run_extraction(game['id'], rulebook_id)
        with Session(engine) as db:
            rulebook = db.exec(select(Rulebook).where(Rulebook.game_id == game['id'])).one()
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            assert rulebook.extracted_text_path is None
            assert content.pipeline_state == PipelineState.no_rulebook
            assert not Path(rulebook.pdf_path).with_suffix('.txt').exists()


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


def test_stale_extraction_worker_ignores_replaced_rulebook():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Stale extraction game'}).json()
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            content.pipeline_state = PipelineState.extracting
            stale_rulebook = Rulebook(id=str(uuid4()), game_id=game['id'], pdf_path='tests/.data/stale.pdf')
            db.add(stale_rulebook)
            db.add(content)
            db.commit()
            stale_id = stale_rulebook.id
        with Session(engine) as db:
            stale_rulebook = db.get(Rulebook, stale_id)
            db.delete(stale_rulebook)
            db.commit()
            replacement = Rulebook(id=str(uuid4()), game_id=game['id'], pdf_path='tests/.data/replacement.pdf')
            db.add(replacement)
            db.commit()
        run_extraction(game['id'], stale_id)
        with Session(engine) as db:
            row = db.exec(select(Rulebook).where(Rulebook.game_id == game['id'])).first()
            assert row is not None
            assert row.pdf_path.endswith('replacement.pdf')
            assert row.extracted_text_path is None


def test_stale_generation_worker_ignores_replaced_rulebook():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Stale generation game'}).json()
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            content.pipeline_state = PipelineState.generating
            content.prior_pipeline_state = PipelineState.ready_to_generate
            stale_rulebook = Rulebook(id=str(uuid4()), game_id=game['id'], pdf_path='tests/.data/stale-generate.pdf', extracted_text_path='tests/.data/stale.txt')
            db.add(stale_rulebook)
            db.add(content)
            db.commit()
            stale_id = stale_rulebook.id
        with Session(engine) as db:
            stale_rulebook = db.get(Rulebook, stale_id)
            db.delete(stale_rulebook)
            db.commit()
            replacement = Rulebook(id=str(uuid4()), game_id=game['id'], pdf_path='tests/.data/replacement-generate.pdf', extracted_text_path='tests/.data/generated.txt')
            db.add(replacement)
            db.commit()
        import asyncio
        asyncio.run(run_generation(game['id'], stale_id))
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            assert content.pipeline_state == PipelineState.generating
            assert content.draft_quickstart_md is None
            assert content.draft_cheat_sheet_md is None
