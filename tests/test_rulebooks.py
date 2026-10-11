from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import json
import subprocess

from tests.helpers import DATA, PDF
import pytest
from PIL import Image
from backend.core.config import get_settings
from backend.db.engine import engine
from backend.main import app
from backend.models import AppSettings, Content, PipelineState, Rulebook
from backend.services import extraction as extraction_service
from backend.services.extraction import extract_pdf
from backend.workers.extraction import run_extraction
from backend.workers.generation import run_generation
from fastapi.testclient import TestClient
from sqlmodel import Session, select


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


def test_rulebook_view_routes_validate_resources_and_serve_pdf(monkeypatch):
    with TestClient(app) as client:
        monkeypatch.setattr('backend.routers.games.run_extraction', lambda *_args: None)
        game = client.post('/api/games', json={'title': 'Independent viewer'}).json()
        info_url = f"/api/games/{game['id']}/rulebook"
        file_url = f"{info_url}/file"
        assert client.get(info_url).status_code == 404
        assert client.get(file_url).status_code == 404
        assert client.get('/api/games/not-a-game/rulebook').json()['detail'] == 'Game not found.'
        assert client.get('/api/games/not-a-game/rulebook/file').status_code == 404

        uploaded = client.post(info_url, files={'file': ('rules.pdf', PDF, 'application/pdf')})
        assert uploaded.status_code == 200
        served = client.get(file_url)
        assert served.status_code == 200
        assert served.headers['content-type'].startswith('application/pdf')
        assert served.content == PDF

        with Session(engine) as db:
            rulebook = db.exec(select(Rulebook).where(Rulebook.game_id == game['id'])).one()
            Path(rulebook.pdf_path).unlink()
        assert client.get(info_url).json()['detail'] == 'Rulebook file not found.'
        assert client.get(file_url).json()['detail'] == 'Rulebook file not found.'

        settings = get_settings()
        previous = settings.auth_disabled
        settings.auth_disabled = False
        try:
            assert client.get(info_url).status_code == 401
            assert client.get(file_url).status_code == 401
        finally:
            settings.auth_disabled = previous


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


def test_extraction_uses_local_ocr_for_image_only_pages(tmp_path, monkeypatch):
    import pdfplumber

    class ImageOnlyPage:
        page_number = 1
        images = [{}]

        def extract_text(self):
            return None

    class ImageOnlyPDF:
        pages = [ImageOnlyPage()]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(pdfplumber, 'open', lambda _path: ImageOnlyPDF())
    monkeypatch.setattr(extraction_service, '_ocr_page', lambda _page: 'Les règles sont données.')
    output_path = tmp_path / 'extracted.txt'

    count = extract_pdf(str(tmp_path / 'scanned.pdf'), str(output_path))

    assert count == 4
    assert output_path.read_text(encoding='utf-8') == 'Les règles sont données.'


def test_ocr_page_uses_french_and_english_tesseract_models(monkeypatch):
    calls = {}

    def fake_run(command, **kwargs):
        calls['command'] = command
        calls.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout='La règle est prête.'.encode('utf-8'))

    class Page:
        page_number = 1

        def to_image(self, resolution):
            assert resolution == 300
            return SimpleNamespace(original=Image.new('RGB', (2, 2)))

    monkeypatch.setattr(extraction_service.subprocess, 'run', fake_run)

    text = extraction_service._ocr_page(Page())

    assert text == 'La règle est prête.'
    assert calls['command'] == ['tesseract', 'stdin', 'stdout', '-l', 'fra+eng', '--psm', '3']
    assert calls['timeout'] == 30
    assert calls['check'] is True
    assert calls['input'].startswith(b'\x89PNG\r\n\x1a\n')


def test_low_quality_extraction_warns_and_requires_server_override(monkeypatch):
    with TestClient(app) as client:
        generation_calls = []
        monkeypatch.setattr('backend.routers.games.run_extraction', lambda *_args: None)
        monkeypatch.setattr('backend.routers.games.run_generation', lambda *args: generation_calls.append(args))
        game = client.post('/api/games', json={'title': 'Low quality extraction'}).json()
        uploaded = client.post(
            f"/api/games/{game['id']}/rulebook",
            files={'file': ('rules.pdf', PDF, 'application/pdf')},
        )
        rulebook_id = uploaded.json()['rulebook']['id']
        run_extraction(game['id'], rulebook_id)

        current = client.get(f"/api/games/{game['id']}")
        assert current.status_code == 200
        body = current.json()
        assert body['pipeline_state'] == 'ready_to_generate'
        assert body['extraction_warning'].startswith('Rulebook text extraction is below')
        assert body['error_message'] is None
        assert 'pdf_path' not in body['rulebook']
        assert 'extracted_text_path' not in body['rulebook']

        with Session(engine) as db:
            db.add(AppSettings(id=1, llm_provider='anthropic', api_key_encrypted='test-ciphertext'))
            db.commit()
        blocked = client.post(f"/api/games/{game['id']}/generate", json={'confirm': True})
        assert blocked.status_code == 422
        assert 'allow_low_quality' in blocked.json()['detail']
        assert generation_calls == []
        allowed = client.post(
            f"/api/games/{game['id']}/generate",
            json={'confirm': True, 'allow_low_quality': True},
        )
        assert allowed.status_code == 200
        assert generation_calls == [(game['id'], rulebook_id)]


def test_high_quality_extraction_allows_generation_without_override(monkeypatch):
    with TestClient(app) as client:
        monkeypatch.setattr('backend.routers.games.run_extraction', lambda *_args: None)
        monkeypatch.setattr('backend.routers.games.run_generation', lambda *_args: None)
        game = client.post('/api/games', json={'title': 'High quality extraction'}).json()
        uploaded = client.post(
            f"/api/games/{game['id']}/rulebook",
            files={'file': ('rules.pdf', PDF, 'application/pdf')},
        )
        rulebook_id = uploaded.json()['rulebook']['id']
        run_extraction(game['id'], rulebook_id)

        with Session(engine) as db:
            rulebook = db.exec(select(Rulebook).where(Rulebook.game_id == game['id'])).one()
            Path(rulebook.extracted_text_path).write_text(' '.join(['rule'] * 500), encoding='utf-8')
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.error_message = None
            db.add(content)
            db.add(AppSettings(id=1, llm_provider='anthropic', api_key_encrypted='test-ciphertext'))
            db.commit()

        response = client.post(f"/api/games/{game['id']}/generate", json={'confirm': True})
        assert response.status_code == 200
        assert response.json()['pipeline_state'] == 'generating'
        assert response.json()['extraction_warning'] is None


def test_startup_recovery_clears_interrupted_extraction_cache():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Interrupted extraction'}).json()
        with Session(engine) as db:
            rulebook = Rulebook(
                id=str(uuid4()),
                game_id=game['id'],
                pdf_path=str(DATA / 'uploads' / 'rulebooks' / 'interrupted.pdf'),
            )
            Path(rulebook.pdf_path).parent.mkdir(parents=True, exist_ok=True)
            extracted = Path(rulebook.pdf_path).with_suffix('.txt').resolve()
            extracted.write_text('orphaned text', encoding='utf-8')
            partial = extracted.with_name(f'.{extracted.name}.crash.part')
            partial.write_text('partial', encoding='utf-8')
            rulebook.extracted_text_path = str(extracted)
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.pipeline_state = PipelineState.extracting
            content.prior_pipeline_state = PipelineState.no_rulebook
            db.add(rulebook)
            db.add(content)
            db.commit()

        from backend.db.init import initialize_database
        initialize_database()
        with Session(engine) as db:
            rulebook = db.exec(select(Rulebook).where(Rulebook.game_id == game['id'])).one()
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            assert rulebook.extracted_text_path is None
            assert content.pipeline_state == PipelineState.no_rulebook
            assert 'interrupted' in content.error_message.lower()
        assert not extracted.exists()
        assert not partial.exists()


def test_startup_recovery_restores_interrupted_generation_predecessor_and_allows_retry(monkeypatch):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Interrupted generation'}).json()
        extracted = DATA / 'uploads' / 'interrupted-generation.txt'
        extracted.write_text(' '.join(['rule'] * 500), encoding='utf-8')
        rulebook_id = str(uuid4())
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.pipeline_state = PipelineState.generating
            content.prior_pipeline_state = PipelineState.published
            content.published_quickstart_md = '# Published guide'
            content.published_cheat_sheet_md = '- Published rule'
            db.add(Rulebook(
                id=rulebook_id,
                game_id=game['id'],
                pdf_path='rules.pdf',
                extracted_text_path=str(extracted),
            ))
            db.add(AppSettings(id=1, llm_provider='google', api_key_encrypted='ciphertext'))
            db.add(content)
            db.commit()

        from backend.db.init import initialize_database
        initialize_database()
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            assert content.pipeline_state == PipelineState.published
            assert content.published_quickstart_md == '# Published guide'
            assert content.published_cheat_sheet_md == '- Published rule'
            assert 'interrupted' in content.error_message.lower()

        scheduled = []
        monkeypatch.setattr('backend.routers.games.run_generation', lambda *args: scheduled.append(args))
        retried = client.post(f"/api/games/{game['id']}/generate", json={'confirm': True})
        assert retried.status_code == 200
        assert retried.json()['pipeline_state'] == 'generating'
        assert scheduled == [(game['id'], rulebook_id)]


def test_startup_recovery_retries_cleanup_after_filesystem_failure(monkeypatch):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Retry interrupted cleanup'}).json()
        with Session(engine) as db:
            rulebook = Rulebook(
                id=str(uuid4()),
                game_id=game['id'],
                pdf_path=str(DATA / 'uploads' / 'rulebooks' / 'retry.pdf'),
            )
            Path(rulebook.pdf_path).parent.mkdir(parents=True, exist_ok=True)
            extracted = Path(rulebook.pdf_path).with_suffix('.txt').resolve()
            extracted.write_text('orphaned text', encoding='utf-8')
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.pipeline_state = PipelineState.extracting
            content.prior_pipeline_state = PipelineState.no_rulebook
            db.add(rulebook)
            db.add(content)
            db.commit()

        original_unlink = Path.unlink
        failed = False

        def fail_once(path: Path, *args, **kwargs):
            nonlocal failed
            if path == extracted and not failed:
                failed = True
                raise OSError('simulated cleanup failure')
            return original_unlink(path, *args, **kwargs)

        monkeypatch.setattr(Path, 'unlink', fail_once)
        from backend.db.init import initialize_database
        initialize_database()
        with Session(engine) as db:
            assert db.exec(select(Content).where(Content.game_id == game['id'])).one().pipeline_state == PipelineState.extracting
        monkeypatch.setattr(Path, 'unlink', original_unlink)
        initialize_database()
        with Session(engine) as db:
            assert db.exec(select(Content).where(Content.game_id == game['id'])).one().pipeline_state == PipelineState.no_rulebook
        assert not extracted.exists()


def test_startup_recovery_cleans_orphans_without_rulebook():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Orphan cleanup'}).json()
        game_root = DATA / 'uploads' / 'rulebooks' / game['id']
        game_root.mkdir(parents=True, exist_ok=True)
        extracted = game_root / 'orphan.txt'
        partial = game_root / '.orphan.txt.crash.part'
        extracted.write_text('orphaned text', encoding='utf-8')
        partial.write_text('partial', encoding='utf-8')
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.pipeline_state = PipelineState.extracting
            content.prior_pipeline_state = PipelineState.no_rulebook
            db.add(content)
            db.commit()

        from backend.db.init import initialize_database
        initialize_database()
        with Session(engine) as db:
            assert db.exec(select(Content).where(Content.game_id == game['id'])).one().pipeline_state == PipelineState.no_rulebook
        assert not extracted.exists()
        assert not partial.exists()


def test_generation_rejects_extracted_path_outside_uploads_dataset():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Unsafe extraction path'}).json()
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.pipeline_state = PipelineState.ready_to_generate
            db.add(content)
            db.add(AppSettings(id=1, llm_provider='anthropic', api_key_encrypted='ciphertext'))
            db.add(Rulebook(id=str(uuid4()), game_id=game['id'], pdf_path='rules.pdf', extracted_text_path=str(DATA / 'outside.txt')))
            db.commit()
        response = client.post(f"/api/games/{game['id']}/generate", json={'confirm': True})
        assert response.status_code == 422
        assert 'extraction' in response.json()['detail'].lower()


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
            stale_rulebook = Rulebook(id=str(uuid4()), game_id=game['id'], pdf_path='tests/.data/uploads/stale-generate.pdf', extracted_text_path='tests/.data/uploads/stale.txt')
            db.add(stale_rulebook)
            db.add(content)
            db.commit()
            stale_id = stale_rulebook.id
        with Session(engine) as db:
            stale_rulebook = db.get(Rulebook, stale_id)
            db.delete(stale_rulebook)
            db.commit()
            replacement = Rulebook(id=str(uuid4()), game_id=game['id'], pdf_path='tests/.data/uploads/replacement-generate.pdf', extracted_text_path='tests/.data/uploads/generated.txt')
            db.add(replacement)
            db.commit()
        import asyncio
        asyncio.run(run_generation(game['id'], stale_id))
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            assert content.pipeline_state == PipelineState.generating
            assert content.draft_quickstart_md is None
            assert content.draft_cheat_sheet_md is None
