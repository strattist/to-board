import asyncio
import os
import base64
import json
import re
import shutil
import subprocess
import threading
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
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
import httpx
import pytest
from PIL import Image
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, delete, select
from backend.main import app
from backend.db.engine import engine
from backend.db.init import initialize_database
from backend.core.config import Settings, get_settings
from backend.core.crypto import decrypt_api_key, encrypt_api_key
from backend.services import games as games_service
from backend.models import AppSettings, Content, Game, GameSession, PipelineState, Rulebook
from backend.services.extraction import extract_pdf
from backend.services import extraction as extraction_service
from backend.workers.extraction import run_extraction
from backend.workers.generation import run_generation
from backend.services.llm import PROMPT, ProviderError, generate_content


@pytest.fixture(autouse=True)
def reset_test_data():
    with Session(engine) as db:
        db.exec(delete(GameSession))
        db.exec(delete(Rulebook))
        db.exec(delete(Content))
        db.exec(delete(Game))
        db.exec(delete(AppSettings))
        db.commit()
    shutil.rmtree(DATA / 'uploads', ignore_errors=True)
    (DATA / 'uploads').mkdir(parents=True, exist_ok=True)
    for generated_text in DATA.glob('*.txt'):
        generated_text.unlink(missing_ok=True)
    try:
        yield
    finally:
        # Tests may create provider settings; do not let a failed test leak a
        # secret or provider selection into the next test.
        with Session(engine) as db:
            db.exec(delete(AppSettings))
            db.commit()
        for generated_text in DATA.glob('*.txt'):
            generated_text.unlink(missing_ok=True)


def encoded_image(format_name: str) -> bytes:
    output = BytesIO()
    Image.new('RGB', (2, 2), color='purple').save(output, format=format_name)
    return output.getvalue()


def stored_cover_path(game_id: str) -> Path:
    with Session(engine) as db:
        game = db.get(Game, game_id)
        assert game is not None and game.cover_image_path is not None
        return Path(game.cover_image_path)


def test_game_creation_and_validation():
    with TestClient(app) as client:
        response = client.post('/api/games', json={'title': '  Wingspan  '})
        assert response.status_code == 201
        assert response.json()['title'] == 'Wingspan'
        assert response.json()['pipeline_state'] == 'no_rulebook'
        assert response.json()['provider_configured'] is False
        assert 'cover_image_path' not in response.json()
        assert 'api_key' not in response.json()
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
        assert 'cover_image_path' not in game
        assert stored_cover_path(game['id']).read_bytes() == image

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
        assert 'cover_image_path' not in cover
        cover_path = stored_cover_path(game['id'])
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
            assert stored_cover_path(game['id']).read_bytes() == image


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


def test_generation_requires_prerequisites(monkeypatch):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Generation prerequisites'}).json()
        scheduled = []
        monkeypatch.setattr('backend.routers.games.run_generation', lambda *args: scheduled.append(args))
        response = client.post(f"/api/games/{game['id']}/generate", json={'confirm': True})
        assert response.status_code == 422
        assert 'extraction' in response.json()['detail'].lower()
        assert scheduled == []


def test_generation_without_provider_key_is_rejected_before_scheduling(monkeypatch):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Missing generation key'}).json()
        extracted = DATA / 'uploads' / 'missing-generation-key.txt'
        extracted.write_text('completed extracted rules', encoding='utf-8')
        with Session(engine) as db:
            db.add(Rulebook(
                id=str(uuid4()),
                game_id=game['id'],
                pdf_path='rules.pdf',
                extracted_text_path=str(extracted),
            ))
            db.commit()

        scheduled = []
        monkeypatch.setattr('backend.routers.games.run_generation', lambda *args: scheduled.append(args))
        response = client.post(f"/api/games/{game['id']}/generate", json={'confirm': True})
        assert response.status_code == 422
        assert 'API key is missing' in response.json()['detail']
        assert scheduled == []
        detail = client.get(f"/api/games/{game['id']}").json()
        assert detail['provider_configured'] is False
        assert detail['pipeline_state'] == 'no_rulebook'
        assert 'cover_image_path' not in detail
        assert 'api_key' not in detail


def test_generation_with_incomplete_extraction_is_rejected_before_scheduling(monkeypatch):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Incomplete extraction'}).json()
        with Session(engine) as db:
            db.add(Rulebook(id=str(uuid4()), game_id=game['id'], pdf_path='rules.pdf'))
            db.commit()

        scheduled = []
        monkeypatch.setattr('backend.routers.games.run_generation', lambda *args: scheduled.append(args))
        response = client.post(f"/api/games/{game['id']}/generate", json={'confirm': True})
        assert response.status_code == 422
        assert 'extraction is not complete' in response.json()['detail'].lower()
        assert scheduled == []


def test_settings_are_host_protected_encrypted_and_content_preserving():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Settings security'}).json()
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.pipeline_state = PipelineState.published
            content.prior_pipeline_state = PipelineState.rejected
            content.draft_quickstart_md = '# Draft'
            content.draft_cheat_sheet_md = '- Draft rule'
            content.published_quickstart_md = '# Published'
            content.published_cheat_sheet_md = '- Published rule'
            content.error_message = 'Existing error'
            content_before = content.model_dump()
            db.add(content)
            db.commit()

        saved = client.put('/api/settings', json={'provider': 'google', 'api_key': 'google-secret'})
        assert saved.status_code == 200
        assert saved.json() == {'provider': 'google', 'configured': True}
        assert 'google-secret' not in saved.text
        with Session(engine) as db:
            settings = db.get(AppSettings, 1)
            assert settings is not None
            assert settings.api_key_encrypted != 'google-secret'
            assert decrypt_api_key(settings.api_key_encrypted) == 'google-secret'
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            assert content.published_quickstart_md == '# Published'
            assert content.published_cheat_sheet_md == '- Published rule'
            assert content.draft_quickstart_md == '# Draft'
            assert content.draft_cheat_sheet_md == '- Draft rule'

        assert client.get('/api/settings').json() == {'provider': 'google', 'configured': True}
        game_detail = client.get(f"/api/games/{game['id']}")
        assert game_detail.json()['provider_configured'] is True
        assert game_detail.json()['has_draft_content'] is True
        assert 'google-secret' not in game_detail.text
        openai_saved = client.put('/api/settings', json={'provider': 'openai', 'api_key': 'openai-secret'})
        assert openai_saved.status_code == 200
        assert openai_saved.json() == {'provider': 'openai', 'configured': True}
        assert 'openai-secret' not in openai_saved.text
        assert client.get('/api/settings').json() == {'provider': 'openai', 'configured': True}
        with Session(engine) as db:
            settings = db.get(AppSettings, 1)
            assert settings is not None
            assert settings.llm_provider == 'openai'
            assert settings.api_key_encrypted != 'openai-secret'
            assert decrypt_api_key(settings.api_key_encrypted) == 'openai-secret'
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            assert content.model_dump() == content_before
        openai_game_detail = client.get(f"/api/games/{game['id']}")
        assert openai_game_detail.json()['provider_configured'] is True
        assert 'openai-secret' not in openai_game_detail.text
        assert client.put('/api/settings', json={'provider': 'invalid', 'api_key': 'invalid-secret'}).status_code == 422
        malformed = client.put('/api/settings', json={'api_key': 'malformed-secret'})
        assert malformed.status_code == 422
        assert 'malformed-secret' not in malformed.text
        with Session(engine) as db:
            before_invalid = db.get(AppSettings, 1)
            assert before_invalid is not None
            before_provider = before_invalid.llm_provider
            before_ciphertext = before_invalid.api_key_encrypted
        assert client.put('/api/settings', json={'provider': 'google', 'api_key': '   '}).status_code == 422
        with Session(engine) as db:
            after_invalid = db.get(AppSettings, 1)
            assert after_invalid is not None
            assert after_invalid.llm_provider == before_provider
            assert after_invalid.api_key_encrypted == before_ciphertext

        settings_config = get_settings()
        previous_auth = settings_config.auth_disabled
        settings_config.auth_disabled = False
        try:
            unauthorized_get = client.get('/api/settings')
            unauthorized_put = client.put('/api/settings', json={'provider': 'openai', 'api_key': 'new-secret'})
            assert unauthorized_get.status_code == unauthorized_put.status_code == 401
            assert 'google' not in unauthorized_get.text
            assert 'new-secret' not in unauthorized_put.text
        finally:
            settings_config.auth_disabled = previous_auth
            with Session(engine) as db:
                db.exec(delete(AppSettings))
                db.commit()


def test_provider_failure_is_sanitized_and_preserves_published_content(monkeypatch):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Provider failure'}).json()
        extracted = DATA / 'uploads' / 'provider-failure.txt'
        extracted.write_text('rules', encoding='utf-8')
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.pipeline_state = PipelineState.generating
            content.prior_pipeline_state = PipelineState.published
            content.published_quickstart_md = '# Existing'
            content.published_cheat_sheet_md = '- Existing rule'
            db.add(content)
            db.add(AppSettings(id=1, llm_provider='openai', api_key_encrypted='ciphertext'))
            db.add(Rulebook(id=str(uuid4()), game_id=game['id'], pdf_path='rules.pdf', extracted_text_path=str(extracted)))
            db.commit()

        async def fail_provider(*_args):
            raise RuntimeError('https://provider.invalid?key=openai-secret')

        monkeypatch.setattr('backend.workers.generation.generate_content', fail_provider)
        rulebook_id = None
        with Session(engine) as db:
            rulebook_id = db.exec(select(Rulebook).where(Rulebook.game_id == game['id'])).one().id
        import asyncio
        asyncio.run(run_generation(game['id'], rulebook_id))

        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            assert content.pipeline_state == PipelineState.published
            assert content.published_quickstart_md == '# Existing'
            assert content.published_cheat_sheet_md == '- Existing rule'
            assert content.error_message == 'OpenAI provider request failed.'
            assert 'openai-secret' not in content.error_message
            assert 'provider.invalid' not in content.error_message
            db.exec(delete(AppSettings))
            db.commit()


def test_generation_read_failure_is_not_reported_as_provider_failure():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Missing extracted text'}).json()
        rulebook_id = str(uuid4())
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.pipeline_state = PipelineState.generating
            content.prior_pipeline_state = PipelineState.ready_to_generate
            db.add(content)
            db.add(AppSettings(id=1, llm_provider='google', api_key_encrypted='ciphertext'))
            db.add(Rulebook(
                id=rulebook_id,
                game_id=game['id'],
                pdf_path='rules.pdf',
                extracted_text_path=str(DATA / 'uploads' / 'missing-extracted-text.txt'),
            ))
            db.commit()

        asyncio.run(run_generation(game['id'], rulebook_id))

        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            assert content.pipeline_state == PipelineState.ready_to_generate
            assert content.error_message == 'Rulebook text could not be read.'


def test_successful_generation_saves_the_paired_draft(monkeypatch):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Generated draft'}).json()
        extracted = DATA / 'uploads' / 'generated-draft.txt'
        extracted.write_text('rules', encoding='utf-8')
        rulebook_id = str(uuid4())
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.pipeline_state = PipelineState.generating
            content.prior_pipeline_state = PipelineState.ready_to_generate
            db.add(content)
            db.add(AppSettings(id=1, llm_provider='openai', api_key_encrypted='ciphertext'))
            db.add(Rulebook(id=rulebook_id, game_id=game['id'], pdf_path='rules.pdf', extracted_text_path=str(extracted)))
            db.commit()

        async def successful_provider(*_args):
            return '# Start', '- Rule'

        monkeypatch.setattr('backend.workers.generation.generate_content', successful_provider)
        asyncio.run(run_generation(game['id'], rulebook_id))

        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            assert content.pipeline_state == PipelineState.draft
            assert content.draft_quickstart_md == '# Start'
            assert content.draft_cheat_sheet_md == '- Rule'
            assert content.published_quickstart_md is None
            assert content.published_cheat_sheet_md is None
            assert len(db.exec(select(Content).where(Content.game_id == game['id'])).all()) == 1


def test_generation_passes_persisted_openai_settings_to_provider_adapter(monkeypatch):
    calls = []
    response_text = '{"quickstart_md":"# Start","cheat_sheet_md":"- Rule"}'

    class MockResponse:
        status_code = 200

        def json(self):
            return {
                'status': 'completed',
                'output': [{
                    'type': 'message',
                    'content': [{'type': 'output_text', 'text': response_text}],
                }],
            }

    class MockAsyncClient:
        def __init__(self, **kwargs):
            assert kwargs['timeout'] == 120

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return MockResponse()

    monkeypatch.setattr('backend.services.llm.httpx.AsyncClient', MockAsyncClient)
    monkeypatch.setattr(
        'backend.services.llm.get_settings',
        lambda: SimpleNamespace(openai_model='configured-openai'),
    )

    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'OpenAI worker integration'}).json()
        extracted = DATA / 'uploads' / 'openai-worker-integration.txt'
        extracted.write_text('persisted extracted rules', encoding='utf-8')
        rulebook_id = str(uuid4())
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.pipeline_state = PipelineState.generating
            content.prior_pipeline_state = PipelineState.ready_to_generate
            db.add(content)
            db.add(AppSettings(
                id=1,
                llm_provider='openai',
                api_key_encrypted=encrypt_api_key('persisted-openai-secret'),
            ))
            db.add(Rulebook(
                id=rulebook_id,
                game_id=game['id'],
                pdf_path='rules.pdf',
                extracted_text_path=str(extracted),
            ))
            db.commit()

        asyncio.run(run_generation(game['id'], rulebook_id))

        assert len(calls) == 1
        url, request = calls[0]
        assert url == 'https://api.openai.com/v1/responses'
        assert request['headers']['Authorization'] == 'Bearer persisted-openai-secret'
        assert request['json']['model'] == 'configured-openai'
        assert request['json']['input'] == 'persisted extracted rules'
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            assert content.pipeline_state == PipelineState.draft
            assert content.draft_quickstart_md == '# Start'
            assert content.draft_cheat_sheet_md == '- Rule'


def test_successful_regeneration_preserves_published_pair(monkeypatch):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Regenerated draft'}).json()
        extracted = DATA / 'uploads' / 'regenerated-draft.txt'
        extracted.write_text('rules', encoding='utf-8')
        rulebook_id = str(uuid4())
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.pipeline_state = PipelineState.generating
            content.prior_pipeline_state = PipelineState.published
            content.published_quickstart_md = '# Existing published guide'
            content.published_cheat_sheet_md = '- Existing published rule'
            db.add(content)
            db.add(AppSettings(id=1, llm_provider='anthropic', api_key_encrypted='ciphertext'))
            db.add(Rulebook(id=rulebook_id, game_id=game['id'], pdf_path='rules.pdf', extracted_text_path=str(extracted)))
            db.commit()

        async def successful_provider(*_args):
            return '# New draft', '- New rule'

        monkeypatch.setattr('backend.workers.generation.generate_content', successful_provider)
        asyncio.run(run_generation(game['id'], rulebook_id))

        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            assert content.pipeline_state == PipelineState.draft
            assert content.draft_quickstart_md == '# New draft'
            assert content.draft_cheat_sheet_md == '- New rule'
            assert content.published_quickstart_md == '# Existing published guide'
            assert content.published_cheat_sheet_md == '- Existing published rule'


def test_generate_route_provider_failure_restores_published_predecessor_and_pair(monkeypatch):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Published regeneration route'}).json()
        extracted = DATA / 'uploads' / 'published-regeneration-route.txt'
        extracted.write_text(' '.join(['rule'] * 500), encoding='utf-8')
        rulebook_id = str(uuid4())
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.pipeline_state = PipelineState.published
            content.published_quickstart_md = '# Published guide'
            content.published_cheat_sheet_md = '- Published rule'
            db.add(content)
            db.add(AppSettings(id=1, llm_provider='anthropic', api_key_encrypted='ciphertext'))
            db.add(Rulebook(
                id=rulebook_id,
                game_id=game['id'],
                pdf_path='rules.pdf',
                extracted_text_path=str(extracted),
            ))
            db.commit()

        scheduled = []
        monkeypatch.setattr('backend.routers.games.run_generation', lambda *args: scheduled.append(args))
        response = client.post(f"/api/games/{game['id']}/generate", json={'confirm': True})

        assert response.status_code == 200
        assert response.json()['pipeline_state'] == 'generating'
        assert scheduled == [(game['id'], rulebook_id)]
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            assert content.pipeline_state == PipelineState.generating
            assert content.published_quickstart_md == '# Published guide'
            assert content.published_cheat_sheet_md == '- Published rule'

        async def fail_with_provider_error(*_args):
            raise ProviderError('anthropic', 'model_not_found')

        monkeypatch.setattr('backend.workers.generation.generate_content', fail_with_provider_error)
        asyncio.run(run_generation(game['id'], rulebook_id))

        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            assert content.pipeline_state == PipelineState.published
            assert content.error_message == 'Anthropic model was not found or is unavailable.'
            assert content.published_quickstart_md == '# Published guide'
            assert content.published_cheat_sheet_md == '- Published rule'


def test_provider_error_message_is_persisted_and_published_content_survives(monkeypatch):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Anthropic model failure'}).json()
        extracted = DATA / 'uploads' / 'anthropic-model-failure.txt'
        extracted.write_text('rules', encoding='utf-8')
        rulebook_id = str(uuid4())
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.pipeline_state = PipelineState.generating
            content.prior_pipeline_state = PipelineState.published
            content.published_quickstart_md = '# Existing guide'
            content.published_cheat_sheet_md = '- Existing rule'
            db.add(content)
            db.add(AppSettings(id=1, llm_provider='anthropic', api_key_encrypted='ciphertext'))
            db.add(Rulebook(id=rulebook_id, game_id=game['id'], pdf_path='rules.pdf', extracted_text_path=str(extracted)))
            db.commit()

        async def fail_with_provider_error(*_args):
            raise ProviderError('anthropic', 'model_not_found')

        monkeypatch.setattr('backend.workers.generation.generate_content', fail_with_provider_error)
        asyncio.run(run_generation(game['id'], rulebook_id))

        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            assert content.pipeline_state == PipelineState.published
            assert content.error_message == 'Anthropic model was not found or is unavailable.'
            assert content.published_quickstart_md == '# Existing guide'
            assert content.published_cheat_sheet_md == '- Existing rule'


def test_llm_provider_branches_use_secret_headers_and_sanitize_failures(monkeypatch):
    calls = []

    class MockResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class MockAsyncClient:
        def __init__(self, **kwargs):
            self.timeout = kwargs['timeout']

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, **kwargs):
            calls.append((url, kwargs))
            if 'anthropic.com' in url:
                payload = {'content': [{'text': '{"quickstart_md":"# Start","cheat_sheet_md":"- Rule"}'}]}
            else:
                payload = {'candidates': [{'content': {'parts': [{'text': '{"quickstart_md":"# Google start","cheat_sheet_md":"- Google rule"}'}]}}]}
            return MockResponse(200, payload)

    monkeypatch.setattr('backend.services.llm.httpx.AsyncClient', MockAsyncClient)
    anthropic = AppSettings(llm_provider='anthropic', api_key_encrypted=encrypt_api_key('anthropic-secret'))
    google = AppSettings(llm_provider='google', api_key_encrypted=encrypt_api_key('google-secret'))
    default_runtime = Settings(secret_key='test-secret', _env_file=None)
    monkeypatch.setattr('backend.services.llm.get_settings', lambda: default_runtime)
    assert asyncio.run(generate_content(anthropic, 'rules')) == ('# Start', '- Rule')
    assert calls[0][1]['json']['model'] == 'claude-haiku-4-5-20251001'
    calls.clear()

    monkeypatch.setattr(
        'backend.services.llm.get_settings',
        lambda: SimpleNamespace(anthropic_model='configured-anthropic', google_model='configured-google'),
    )
    assert asyncio.run(generate_content(anthropic, 'rules')) == ('# Start', '- Rule')
    assert asyncio.run(generate_content(google, 'rules')) == ('# Google start', '- Google rule')
    anthropic_url, anthropic_kwargs = calls[0]
    google_url, google_kwargs = calls[1]
    assert anthropic_url == 'https://api.anthropic.com/v1/messages'
    assert anthropic_kwargs['json']['model'] == 'configured-anthropic'
    assert anthropic_kwargs['headers']['x-api-key'] == 'anthropic-secret'
    assert google_url == 'https://generativelanguage.googleapis.com/v1beta/models/configured-google:generateContent'
    assert '?key=' not in google_url
    assert google_kwargs['headers']['x-goog-api-key'] == 'google-secret'

    class AuthFailureClient(MockAsyncClient):
        async def post(self, url, **kwargs):
            return MockResponse(401, {'error': {'message': 'invalid key google-secret'}})

    monkeypatch.setattr('backend.services.llm.httpx.AsyncClient', AuthFailureClient)
    with pytest.raises(ProviderError) as auth_error:
        asyncio.run(generate_content(google, 'rules'))
    assert str(auth_error.value) == 'Google rejected the API key.'
    assert 'google-secret' not in str(auth_error.value)

    class MalformedClient(MockAsyncClient):
        async def post(self, url, **kwargs):
            return MockResponse(200, {'candidates': []})

    monkeypatch.setattr('backend.services.llm.httpx.AsyncClient', MalformedClient)
    with pytest.raises(ProviderError) as malformed_error:
        asyncio.run(generate_content(google, 'rules'))
    assert str(malformed_error.value) == 'Google returned an invalid response.'
    assert malformed_error.value.__suppress_context__ is True
    assert malformed_error.value.__cause__ is None

    class AnthropicMalformedClient(MockAsyncClient):
        async def post(self, url, **kwargs):
            return MockResponse(200, {'content': []})

    monkeypatch.setattr('backend.services.llm.httpx.AsyncClient', AnthropicMalformedClient)
    with pytest.raises(ProviderError) as anthropic_malformed_error:
        asyncio.run(generate_content(anthropic, 'rules'))
    assert str(anthropic_malformed_error.value) == 'Anthropic returned an invalid response.'

    class GoogleSafetyClient(MockAsyncClient):
        async def post(self, url, **kwargs):
            return MockResponse(200, {'promptFeedback': {'blockReason': 'SAFETY'}})

    monkeypatch.setattr('backend.services.llm.httpx.AsyncClient', GoogleSafetyClient)
    with pytest.raises(ProviderError) as safety_error:
        asyncio.run(generate_content(google, 'rules'))
    assert str(safety_error.value) == 'Google blocked the requested content.'

    class TimeoutClient(MockAsyncClient):
        async def post(self, url, **kwargs):
            raise httpx.ReadTimeout('timed out')

    monkeypatch.setattr('backend.services.llm.httpx.AsyncClient', TimeoutClient)
    with pytest.raises(ProviderError) as timeout_error:
        asyncio.run(generate_content(google, 'rules'))
    assert str(timeout_error.value) == 'Google provider is unavailable.'

    class AnthropicModelFailureClient(MockAsyncClient):
        async def post(self, url, **kwargs):
            return MockResponse(404, {'error': {'message': 'model configured-anthropic is not found'}})

    monkeypatch.setattr('backend.services.llm.httpx.AsyncClient', AnthropicModelFailureClient)
    with pytest.raises(ProviderError) as model_error:
        asyncio.run(generate_content(anthropic, 'rules'))
    assert str(model_error.value) == 'Anthropic model was not found or is unavailable.'
    assert 'configured-anthropic' not in str(model_error.value)

    class AnthropicProviderFailureClient(MockAsyncClient):
        async def post(self, url, **kwargs):
            return MockResponse(503, {'error': {'message': 'provider unavailable'}})

    monkeypatch.setattr('backend.services.llm.httpx.AsyncClient', AnthropicProviderFailureClient)
    with pytest.raises(ProviderError) as provider_error:
        asyncio.run(generate_content(anthropic, 'rules'))
    assert str(provider_error.value) == 'Anthropic provider is unavailable.'

    status_expectations = {
        400: 'Anthropic model or request configuration was rejected.',
        403: 'Anthropic model or provider access was rejected.',
        429: 'Anthropic provider rate limit was reached.',
    }

    for status_code, expected_message in status_expectations.items():
        class StatusFailureClient(MockAsyncClient):
            async def post(self, url, **kwargs):
                return MockResponse(status_code, {'error': {'message': 'sensitive provider response'}})

        monkeypatch.setattr('backend.services.llm.httpx.AsyncClient', StatusFailureClient)
        with pytest.raises(ProviderError) as status_error:
            asyncio.run(generate_content(anthropic, 'rules'))
        assert str(status_error.value) == expected_message
        assert 'sensitive provider response' not in str(status_error.value)


def test_openai_responses_api_uses_private_configuration_and_collects_all_text(monkeypatch):
    calls = []
    content_json = '{"quickstart_md":"# OpenAI start","cheat_sheet_md":"- OpenAI rule"}'
    split_at = len(content_json) // 2
    payload = {
        'status': 'completed',
        'output': [
            {'type': 'reasoning', 'summary': [{'type': 'summary_text', 'text': 'not the answer'}]},
            {'type': 'function_call', 'name': 'unrelated_tool'},
            {
                'type': 'message',
                'content': [
                    {'type': 'image', 'image_url': 'omitted'},
                    {'type': 'output_text', 'text': content_json[:split_at]},
                ],
            },
            {'type': 'message', 'content': [{'type': 'output_text', 'text': content_json[split_at:]}]},
        ],
    }

    class MockResponse:
        status_code = 200

        def json(self):
            return payload

    class MockAsyncClient:
        def __init__(self, **kwargs):
            assert kwargs['timeout'] == 120

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return MockResponse()

    monkeypatch.setattr('backend.services.llm.httpx.AsyncClient', MockAsyncClient)
    monkeypatch.setattr(
        'backend.services.llm.get_settings',
        lambda: SimpleNamespace(openai_model='configured-openai'),
    )
    settings = AppSettings(llm_provider='openai', api_key_encrypted=encrypt_api_key('openai-secret'))

    assert asyncio.run(generate_content(settings, 'locally extracted rulebook text')) == (
        '# OpenAI start', '- OpenAI rule',
    )
    url, request = calls[0]
    assert url == 'https://api.openai.com/v1/responses'
    assert request['json'] == {
        'model': 'configured-openai',
        'instructions': PROMPT,
        'input': 'locally extracted rulebook text',
        'store': False,
        'max_output_tokens': 10000,
    }
    assert request['headers']['Authorization'] == 'Bearer openai-secret'
    assert 'openai-secret' not in url
    assert 'openai-secret' not in str(request['json'])

    monkeypatch.setattr(
        'backend.services.llm.get_settings',
        lambda: SimpleNamespace(openai_model='invalid model'),
    )
    with pytest.raises(ProviderError) as invalid_model_error:
        asyncio.run(generate_content(settings, 'locally extracted rulebook text'))
    assert str(invalid_model_error.value) == 'OpenAI configuration is invalid.'
    assert len(calls) == 1

    monkeypatch.setattr(
        'backend.services.llm.get_settings',
        lambda: SimpleNamespace(openai_model='configured-openai'),
    )
    payload.update({'status': 'incomplete', 'output': []})
    with pytest.raises(ProviderError) as incomplete_error:
        asyncio.run(generate_content(settings, 'rules'))
    assert str(incomplete_error.value) == 'OpenAI returned incomplete content.'

    payload.update({
        'status': 'failed',
        'output': [],
        'error': {'message': 'private failure details'},
    })
    with pytest.raises(ProviderError) as failed_error:
        asyncio.run(generate_content(settings, 'rules'))
    assert str(failed_error.value) == 'OpenAI request failed.'
    assert 'private failure details' not in str(failed_error.value)

    payload.update({'status': 'completed', 'output': [{'type': 'reasoning', 'summary': []}]})
    with pytest.raises(ProviderError) as absent_text_error:
        asyncio.run(generate_content(settings, 'rules'))
    assert str(absent_text_error.value) == 'OpenAI returned an invalid response.'

    payload.update({'status': 'completed', 'output': [{'type': 'message', 'content': 'malformed'}]})
    with pytest.raises(ProviderError) as malformed_error:
        asyncio.run(generate_content(settings, 'rules'))
    assert str(malformed_error.value) == 'OpenAI returned an invalid response.'

    payload.update({
        'status': 'completed',
        'output': [{'type': 'message', 'content': [{'type': 'refusal', 'refusal': 'private text'}]}],
    })
    with pytest.raises(ProviderError) as refusal_error:
        asyncio.run(generate_content(settings, 'rules'))
    assert str(refusal_error.value) == 'OpenAI blocked the requested content.'
    assert 'private text' not in str(refusal_error.value)

    payload.update({
        'status': 'completed',
        'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': '{"quickstart_md":" ","cheat_sheet_md":"# Rules"}'}]}],
    })
    with pytest.raises(ProviderError) as incomplete_pair_error:
        asyncio.run(generate_content(settings, 'rules'))
    assert str(incomplete_pair_error.value) == 'OpenAI returned incomplete content.'


@pytest.mark.parametrize(('status_code', 'expected_message'), [
    (400, 'OpenAI model or request configuration was rejected.'),
    (401, 'OpenAI rejected the API key.'),
    (403, 'OpenAI model or provider access was rejected.'),
    (404, 'OpenAI model was not found or is unavailable.'),
    (408, 'OpenAI provider is unavailable.'),
    (429, 'OpenAI provider rate limit was reached.'),
    (503, 'OpenAI provider is unavailable.'),
])
def test_openai_provider_http_failures_are_sanitized(monkeypatch, status_code, expected_message):
    class MockResponse:
        def __init__(self, code):
            self.status_code = code

        def json(self):
            return {'error': {'message': 'provider response includes openai-secret'}}

    class MockAsyncClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return MockResponse(status_code)

    monkeypatch.setattr('backend.services.llm.httpx.AsyncClient', MockAsyncClient)
    monkeypatch.setattr(
        'backend.services.llm.get_settings',
        lambda: SimpleNamespace(openai_model='configured-openai'),
    )
    settings = AppSettings(llm_provider='openai', api_key_encrypted=encrypt_api_key('openai-secret'))

    with pytest.raises(ProviderError) as provider_error:
        asyncio.run(generate_content(settings, 'rules'))
    assert str(provider_error.value) == expected_message
    assert 'openai-secret' not in str(provider_error.value)
    assert 'provider response' not in str(provider_error.value)


@pytest.mark.parametrize('error_details', [
    {'code': 'credit_balance_exhausted'},
    {'code': 'organization_spend_limit_exceeded'},
    {'code': 'project_spend_limit_exceeded'},
    {'code': 'organization_usage_limit_exceeded'},
    {'type': 'insufficient_quota'},
])
def test_openai_quota_429_errors_are_actionable_and_sanitized(monkeypatch, error_details):
    class MockResponse:
        status_code = 429

        def json(self):
            return {'error': {**error_details, 'message': 'private billing response'}}

    class MockAsyncClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return MockResponse()

    monkeypatch.setattr('backend.services.llm.httpx.AsyncClient', MockAsyncClient)
    monkeypatch.setattr(
        'backend.services.llm.get_settings',
        lambda: SimpleNamespace(openai_model='configured-openai'),
    )
    settings = AppSettings(llm_provider='openai', api_key_encrypted=encrypt_api_key('openai-secret'))

    with pytest.raises(ProviderError) as provider_error:
        asyncio.run(generate_content(settings, 'rules'))
    assert str(provider_error.value) == (
        'OpenAI billing or usage limit was reached; review OpenAI billing and usage limits.'
    )
    assert 'private billing response' not in str(provider_error.value)


def test_anthropic_accepts_json_with_leading_text_and_fence(monkeypatch):
    request_bodies = []

    class MockResponse:
        status_code = 200

        def json(self):
            return {
                'stop_reason': 'end_turn',
                'content': [{
                    'type': 'text',
                    'text': 'Here is the requested content:\n```json\n'
                    '{"quickstart_md":"# Start","cheat_sheet_md":"- Rule"}\n```',
                }],
            }

    class MockAsyncClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **kwargs):
            request_bodies.append(kwargs['json'])
            return MockResponse()

    monkeypatch.setattr('backend.services.llm.httpx.AsyncClient', MockAsyncClient)
    settings = AppSettings(llm_provider='anthropic', api_key_encrypted=encrypt_api_key('anthropic-secret'))
    monkeypatch.setattr(
        'backend.services.llm.get_settings',
        lambda: SimpleNamespace(
            anthropic_model='configured-anthropic',
            google_model='configured-google',
            openai_model='configured-openai',
        ),
    )

    assert asyncio.run(generate_content(settings, 'rules')) == ('# Start', '- Rule')
    assert request_bodies[0]['max_tokens'] == 10000


def test_model_overrides_are_loaded_from_environment(monkeypatch):
    defaults = Settings(secret_key='test-secret', _env_file=None)
    assert defaults.openai_model == 'gpt-6-luna'
    monkeypatch.setenv('ANTHROPIC_MODEL', 'configured-anthropic')
    monkeypatch.setenv('GOOGLE_MODEL', 'configured-google')
    monkeypatch.setenv('OPENAI_MODEL', 'configured-openai')
    settings = Settings(secret_key='test-secret', _env_file=None)
    assert settings.anthropic_model == 'configured-anthropic'
    assert settings.google_model == 'configured-google'
    assert settings.openai_model == 'configured-openai'


def test_compose_configures_openai_model_default():
    compose = Path('docker-compose.yml').read_text(encoding='utf-8')
    api_service = compose.split('  web:', 1)[0]
    assert 'OPENAI_MODEL: ${OPENAI_MODEL:-gpt-6-luna}' in api_service


def test_publish_copies_complete_draft_and_clears_draft_pair():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Publish test'}).json()
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            content.pipeline_state = PipelineState.draft
            content.draft_quickstart_md = '# Draft'
            content.draft_cheat_sheet_md = '- Draft rule'
            content.published_quickstart_md = '# Older Published'
            content.published_cheat_sheet_md = '- Older published rule'
            db.add(content)
            db.commit()
        revision = client.get(f"/api/games/{game['id']}/content").json()['draft_revision']
        response = client.post(
            f"/api/games/{game['id']}/content/publish",
            json={'expected_revision': revision},
        )
        assert response.status_code == 200
        assert response.json()['pipeline_state'] == 'published'
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            assert content.pipeline_state == PipelineState.published
            assert content.draft_quickstart_md is None
            assert content.draft_cheat_sheet_md is None
            assert content.published_quickstart_md == '# Draft'
            assert content.published_cheat_sheet_md == '- Draft rule'


def test_reject_clears_complete_draft_preserves_published_pair_and_allows_regeneration(monkeypatch):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Reject test'}).json()
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            content.pipeline_state = PipelineState.draft
            content.draft_quickstart_md = '# Draft'
            content.draft_cheat_sheet_md = '- Draft rule'
            content.published_quickstart_md = '# Published'
            content.published_cheat_sheet_md = '- Published rule'
            db.add(content)
            db.commit()
        revision = client.get(f"/api/games/{game['id']}/content").json()['draft_revision']
        response = client.post(
            f"/api/games/{game['id']}/content/reject",
            json={'expected_revision': revision},
        )
        assert response.status_code == 200
        assert response.json()['pipeline_state'] == 'rejected'
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            assert content.pipeline_state == PipelineState.rejected
            assert content.draft_quickstart_md is None
            assert content.draft_cheat_sheet_md is None
            assert content.published_quickstart_md == '# Published'
            assert content.published_cheat_sheet_md == '- Published rule'

        extracted = DATA / 'uploads' / f"rejected-regeneration-{uuid4()}.txt"
        extracted.write_text('rules', encoding='utf-8')
        rulebook_id = str(uuid4())
        with Session(engine) as db:
            db.add(Rulebook(id=rulebook_id, game_id=game['id'], pdf_path='rules.pdf', extracted_text_path=str(extracted)))
            db.add(AppSettings(id=1, llm_provider='anthropic', api_key_encrypted='ciphertext'))
            db.commit()
        scheduled = []
        monkeypatch.setattr('backend.routers.games.run_generation', lambda *args: scheduled.append(args))
        response = client.post(
            f"/api/games/{game['id']}/generate",
            json={'confirm': True, 'allow_low_quality': True},
        )
        extracted.unlink(missing_ok=True)
        assert response.status_code == 200
        assert response.json()['pipeline_state'] == 'generating'
        assert scheduled == [(game['id'], rulebook_id)]


@pytest.mark.parametrize('action', ['publish', 'reject'])
def test_publish_and_reject_reject_superseded_draft_revision_without_mutation(action):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': f'Superseded Draft {action} test'}).json()
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            content.pipeline_state = PipelineState.draft
            content.draft_quickstart_md = '# Reviewed Draft'
            content.draft_cheat_sheet_md = '- Reviewed rule'
            content.published_quickstart_md = '# Existing Published'
            content.published_cheat_sheet_md = '- Existing published rule'
            db.add(content)
            db.commit()

        reviewed_revision = client.get(f"/api/games/{game['id']}/content").json()['draft_revision']
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            content.draft_quickstart_md = '# New Draft the Host has not reviewed'
            content.draft_cheat_sheet_md = '- New rule'
            db.add(content)
            db.commit()
        current_revision = client.get(f"/api/games/{game['id']}/content").json()['draft_revision']
        assert current_revision != reviewed_revision

        response = client.post(
            f"/api/games/{game['id']}/content/{action}",
            json={'expected_revision': reviewed_revision},
        )
        assert response.status_code == 409
        assert response.json()['detail'] == 'Draft changed since it was loaded. Reload before acting.'
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            assert content.pipeline_state == PipelineState.draft
            assert content.draft_quickstart_md == '# New Draft the Host has not reviewed'
            assert content.draft_cheat_sheet_md == '- New rule'
            assert content.published_quickstart_md == '# Existing Published'
            assert content.published_cheat_sheet_md == '- Existing published rule'


@pytest.mark.parametrize('action', ['publish', 'reject'])
def test_publish_and_reject_require_a_reviewed_draft_revision(action):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': f'Missing revision {action} test'}).json()
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            content.pipeline_state = PipelineState.draft
            content.draft_quickstart_md = '# Draft'
            content.draft_cheat_sheet_md = '- Draft rule'
            db.add(content)
            db.commit()

        response = client.post(f"/api/games/{game['id']}/content/{action}")
        assert response.status_code == 409
        assert response.json()['detail'] == 'Draft changed since it was loaded. Reload before acting.'
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            assert content.pipeline_state == PipelineState.draft
            assert content.draft_quickstart_md == '# Draft'
            assert content.draft_cheat_sheet_md == '- Draft rule'


@pytest.mark.parametrize('action', ['publish', 'reject'])
@pytest.mark.parametrize(
    ('quickstart_md', 'cheat_sheet_md'),
    [
        ('# Draft', None),
        (None, '- Draft rule'),
        ('', '- Draft rule'),
        ('# Draft', ''),
        ('   ', '- Draft rule'),
        ('# Draft', '\n\t'),
    ],
    ids=[
        'missing-quickstart',
        'missing-cheat-sheet',
        'empty-quickstart',
        'empty-cheat-sheet',
        'whitespace-quickstart',
        'whitespace-cheat-sheet',
    ],
)
def test_publish_and_reject_require_complete_draft_without_mutation(action, quickstart_md, cheat_sheet_md):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': f'Incomplete {action} test'}).json()
        before = {
            'quickstart': quickstart_md,
            'cheat_sheet': cheat_sheet_md,
            'published_quickstart': '# Existing Published',
            'published_cheat_sheet': '- Existing published rule',
        }
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            content.pipeline_state = PipelineState.draft
            content.draft_quickstart_md = before['quickstart']
            content.draft_cheat_sheet_md = before['cheat_sheet']
            content.published_quickstart_md = before['published_quickstart']
            content.published_cheat_sheet_md = before['published_cheat_sheet']
            db.add(content)
            db.commit()

        response = client.post(f"/api/games/{game['id']}/content/{action}")
        assert response.status_code == 409
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            assert content.pipeline_state == PipelineState.draft
            assert content.draft_quickstart_md == before['quickstart']
            assert content.draft_cheat_sheet_md == before['cheat_sheet']
            assert content.published_quickstart_md == before['published_quickstart']
            assert content.published_cheat_sheet_md == before['published_cheat_sheet']


@pytest.mark.parametrize('action', ['publish', 'reject'])
@pytest.mark.parametrize('pipeline_state', [state for state in PipelineState if state != PipelineState.draft])
def test_publish_and_reject_require_draft_state_without_mutation(action, pipeline_state):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': f'Invalid state {action} test'}).json()
        before = {
            'quickstart': '# Draft',
            'cheat_sheet': '- Draft rule',
            'published_quickstart': '# Existing Published',
            'published_cheat_sheet': '- Existing published rule',
        }
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            content.pipeline_state = pipeline_state
            content.draft_quickstart_md = before['quickstart']
            content.draft_cheat_sheet_md = before['cheat_sheet']
            content.published_quickstart_md = before['published_quickstart']
            content.published_cheat_sheet_md = before['published_cheat_sheet']
            db.add(content)
            db.commit()

        response = client.post(f"/api/games/{game['id']}/content/{action}")
        assert response.status_code == 409
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            assert content.pipeline_state == pipeline_state
            assert content.draft_quickstart_md == before['quickstart']
            assert content.draft_cheat_sheet_md == before['cheat_sheet']
            assert content.published_quickstart_md == before['published_quickstart']
            assert content.published_cheat_sheet_md == before['published_cheat_sheet']


@pytest.mark.parametrize(
    'busy_pipeline_state',
    [PipelineState.extracting, PipelineState.generating],
    ids=['extracting', 'generating'],
)
def test_session_room_and_close_state(busy_pipeline_state):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Session test'}).json()
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            content.pipeline_state = busy_pipeline_state
            content.prior_pipeline_state = PipelineState.published
            content.published_quickstart_md = '# Start'
            content.published_cheat_sheet_md = '- Rule'
            db.add(content)
            db.commit()
        created = client.post(f"/api/sessions?game_id={game['id']}")
        assert created.status_code == 201
        record = created.json()
        preview = client.get(f"/api/games/{game['id']}/preview")
        assert preview.status_code == 200
        assert preview.json()['quickstart_md'] == '# Start'
        assert client.get('/api/room/' + record['room_slug']).json()['quickstart_md'] == '# Start'
        assert client.post('/api/sessions/' + record['id'] + '/end').status_code == 200
        assert client.get('/api/room/' + record['room_slug']).json()['ended'] is True


def test_preview_returns_published_pair_without_creating_session_or_provider_work(monkeypatch):
    generation_jobs = []

    async def record_generation_job(*args):
        generation_jobs.append(args)

    monkeypatch.setattr('backend.routers.games.run_generation', record_generation_job)
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Preview without a Session'}).json()
        published_pair = {
            'quickstart_md': '# Published Guide',
            'cheat_sheet_md': '- Published rule',
        }
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.pipeline_state = PipelineState.generating
            content.prior_pipeline_state = PipelineState.published
            content.published_quickstart_md = published_pair['quickstart_md']
            content.published_cheat_sheet_md = published_pair['cheat_sheet_md']
            content.draft_quickstart_md = '# Private Draft Guide'
            content.draft_cheat_sheet_md = '- Private Draft rule'
            db.add(content)
            db.commit()

        preview = client.get(f"/api/games/{game['id']}/preview")
        assert preview.status_code == 200
        assert preview.json()['quickstart_md'] == published_pair['quickstart_md']
        assert preview.json()['cheat_sheet_md'] == published_pair['cheat_sheet_md']
        assert 'Private Draft' not in preview.text
        assert generation_jobs == []
        with Session(engine) as db:
            assert db.exec(select(GameSession).where(GameSession.game_id == game['id'])).all() == []
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            assert content.pipeline_state == PipelineState.generating
            assert content.prior_pipeline_state == PipelineState.published
            assert content.published_quickstart_md == published_pair['quickstart_md']
            assert content.published_cheat_sheet_md == published_pair['cheat_sheet_md']

        started = client.post(f"/api/sessions?game_id={game['id']}")
        assert started.status_code == 201
        room = client.get('/api/room/' + started.json()['room_slug'])
        assert room.status_code == 200
        assert room.json()['quickstart_md'] == preview.json()['quickstart_md']
        assert room.json()['cheat_sheet_md'] == preview.json()['cheat_sheet_md']


@pytest.mark.parametrize(
    ('pipeline_state', 'published_quickstart', 'published_cheat_sheet', 'draft_quickstart', 'draft_cheat_sheet'),
    [
        (PipelineState.draft, None, None, '# Private Draft Guide', '- Private Draft rule'),
        (PipelineState.rejected, None, None, None, None),
        (PipelineState.draft, '# Partial Published Guide', None, '# Private Draft Guide', '- Private Draft rule'),
        (PipelineState.draft, None, '- Partial Published rule', '# Private Draft Guide', '- Private Draft rule'),
        (PipelineState.draft, '', '- Partial Published rule', '# Private Draft Guide', '- Private Draft rule'),
        (PipelineState.draft, '# Partial Published Guide', '', '# Private Draft Guide', '- Private Draft rule'),
    ],
    ids=[
        'draft-only',
        'rejected',
        'missing-published-cheat-sheet',
        'missing-published-guide',
        'empty-published-guide',
        'empty-published-cheat-sheet',
    ],
)
def test_preview_does_not_return_draft_rejected_or_incomplete_published_content(
    pipeline_state, published_quickstart, published_cheat_sheet, draft_quickstart, draft_cheat_sheet
):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Unavailable Preview'}).json()
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.pipeline_state = pipeline_state
            content.published_quickstart_md = published_quickstart
            content.published_cheat_sheet_md = published_cheat_sheet
            content.draft_quickstart_md = draft_quickstart
            content.draft_cheat_sheet_md = draft_cheat_sheet
            before = (
                content.pipeline_state,
                content.published_quickstart_md,
                content.published_cheat_sheet_md,
                content.draft_quickstart_md,
                content.draft_cheat_sheet_md,
            )
            db.add(content)
            db.commit()

        response = client.get(f"/api/games/{game['id']}/preview")
        assert response.status_code == 404
        assert response.json()['detail'] == 'Published Content not found.'
        assert 'Private Draft' not in response.text
        assert 'Partial Published' not in response.text
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            after = (
                content.pipeline_state,
                content.published_quickstart_md,
                content.published_cheat_sheet_md,
                content.draft_quickstart_md,
                content.draft_cheat_sheet_md,
            )
            assert after == before
            assert db.exec(select(GameSession).where(GameSession.game_id == game['id'])).all() == []


def test_preview_requires_host_authentication():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Protected Preview'}).json()
        settings = get_settings()
        previous = settings.auth_disabled
        settings.auth_disabled = False
        try:
            response = client.get(f"/api/games/{game['id']}/preview")
            assert response.status_code == 401
            assert 'Published Guide' not in response.text
        finally:
            settings.auth_disabled = previous


@pytest.mark.parametrize(
    ('quickstart_md', 'cheat_sheet_md'),
    [('# Published guide', None), (None, '- Published rule')],
    ids=['missing-quickstart', 'missing-cheat-sheet'],
)
def test_session_requires_complete_published_pair_during_generation(quickstart_md, cheat_sheet_md):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Incomplete published pair'}).json()
        room_slug = f"incomplete-published-{game['id'][:8]}"
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.pipeline_state = PipelineState.generating
            content.prior_pipeline_state = PipelineState.published
            content.published_quickstart_md = quickstart_md
            content.published_cheat_sheet_md = cheat_sheet_md
            db.add_all([
                content,
                GameSession(
                    id=str(uuid4()),
                    game_id=game['id'],
                    game_title_snapshot=game['title'],
                    room_slug=room_slug,
                ),
            ])
            db.commit()

        response = client.post(f"/api/sessions?game_id={game['id']}")
        assert response.status_code == 422
        assert response.json()['detail'] == 'Published Content is required to start a Session.'
        preview = client.get(f"/api/games/{game['id']}/preview")
        assert preview.status_code == 404
        assert preview.json()['detail'] == 'Published Content not found.'
        room = client.get(f"/api/room/{room_slug}")
        assert room.status_code == 404
        assert room.json()['detail'] == 'Published Content is unavailable for this Room.'


def test_game_deletion_removes_current_assets_and_preserves_session_history(monkeypatch):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Delete safely'}).json()
        cover = client.post(
            f"/api/games/{game['id']}/cover",
            files={'file': ('cover.png', encoded_image('PNG'), 'image/png')},
        ).json()
        with Session(engine) as db:
            rulebook_path = DATA / 'uploads' / 'rulebooks' / game['id'] / 'rules.pdf'
            rulebook_path.parent.mkdir(parents=True, exist_ok=True)
            rulebook_path.write_bytes(b'%PDF-1.4 test')
            rulebook = Rulebook(id=str(uuid4()), game_id=game['id'], pdf_path=str(rulebook_path))
            extracted = DATA / 'uploads' / 'rulebooks' / game['id'] / 'rules.txt'
            extracted.write_text('extracted rules', encoding='utf-8')
            rulebook.extracted_text_path = str(extracted)
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.pipeline_state = PipelineState.published
            content.published_quickstart_md = '# Quick start'
            content.published_cheat_sheet_md = '- Cheat sheet'
            history = GameSession(
                id=str(uuid4()),
                game_id=game['id'],
                game_title_snapshot=game['title'],
                room_slug=f"delete-safely-{uuid4().hex[:4]}",
                ended_at=datetime.now(timezone.utc),
            )
            db.add_all([rulebook, content, history])
            db.commit()
            cover_path = stored_cover_path(game['id'])
            history_id = history.id

        response = client.delete(f"/api/games/{game['id']}")
        assert response.status_code == 204
        assert not rulebook_path.exists()
        assert not extracted.exists()
        assert not cover_path.exists()
        with Session(engine) as db:
            assert db.get(Game, game['id']) is None
            assert db.exec(select(Rulebook).where(Rulebook.game_id == game['id'])).first() is None
            assert db.exec(select(Content).where(Content.game_id == game['id'])).first() is None
            preserved = db.get(GameSession, history_id)
            assert preserved is not None
            assert preserved.game_title_snapshot == 'Delete safely'
        preserved_response = client.get(f'/api/sessions/{history_id}')
        assert preserved_response.status_code == 200
        assert preserved_response.json()['game_title_snapshot'] == 'Delete safely'
        assert all(item['id'] != game['id'] for item in client.get('/api/games').json())


def test_game_deletion_rejects_active_session_before_mutation():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Active session'}).json()
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.pipeline_state = PipelineState.published
            content.published_quickstart_md = '# Start'
            content.published_cheat_sheet_md = '- Rule'
            db.add(content)
            db.commit()
        started = client.post(f"/api/sessions?game_id={game['id']}")
        assert started.status_code == 201
        blocked = client.delete(f"/api/games/{game['id']}")
        assert blocked.status_code == 409
        assert client.get(f"/api/room/{started.json()['room_slug']}").status_code == 200
        with Session(engine) as db:
            assert db.get(Game, game['id']) is not None


def test_game_deletion_storage_failure_restores_assets_and_rows(monkeypatch):
    with TestClient(app, raise_server_exceptions=False) as client:
        game = client.post('/api/games', json={'title': 'Delete storage failure'}).json()
        cover = client.post(
            f"/api/games/{game['id']}/cover",
            files={'file': ('cover.png', encoded_image('PNG'), 'image/png')},
        ).json()
        cover_path = stored_cover_path(game['id'])
        original_replace = Path.replace

        def fail_staging(path: Path, destination: Path):
            if '.game-delete' in str(destination):
                raise OSError('simulated staging failure')
            return original_replace(path, destination)

        monkeypatch.setattr(Path, 'replace', fail_staging)
        response = client.delete(f"/api/games/{game['id']}")
        assert response.status_code == 500
        assert response.json()['detail']
        assert cover_path.exists()
        with Session(engine) as db:
            assert db.get(Game, game['id']) is not None


def test_game_deletion_partial_staging_failure_restores_all_assets(monkeypatch):
    with TestClient(app, raise_server_exceptions=False) as client:
        game = client.post('/api/games', json={'title': 'Delete partial staging'}).json()
        cover = client.post(
            f"/api/games/{game['id']}/cover",
            files={'file': ('cover.png', encoded_image('PNG'), 'image/png')},
        ).json()
        cover_path = stored_cover_path(game['id'])
        with Session(engine) as db:
            rulebook_path = DATA / 'uploads' / 'rulebooks' / game['id'] / 'rules.pdf'
            rulebook_path.parent.mkdir(parents=True, exist_ok=True)
            rulebook_path.write_bytes(b'current rulebook')
            db.add(Rulebook(id=str(uuid4()), game_id=game['id'], pdf_path=str(rulebook_path)))
            db.commit()
        original_replace = Path.replace
        failed = False

        def fail_cover_stage(path: Path, destination: Path):
            nonlocal failed
            if not failed and destination.name == cover_path.name and '.game-delete' in destination.parts:
                failed = True
                raise OSError('simulated partial staging failure')
            return original_replace(path, destination)

        monkeypatch.setattr(Path, 'replace', fail_cover_stage)
        response = client.delete(f"/api/games/{game['id']}")
        assert response.status_code == 500
        assert failed
        assert cover_path.exists()
        assert rulebook_path.exists()
        with Session(engine) as db:
            assert db.get(Game, game['id']) is not None


def test_game_deletion_post_commit_cleanup_is_journaled_and_retried(monkeypatch):
    with TestClient(app, raise_server_exceptions=False) as client:
        game = client.post('/api/games', json={'title': 'Delete cleanup journal'}).json()
        cover = client.post(
            f"/api/games/{game['id']}/cover",
            files={'file': ('cover.png', encoded_image('PNG'), 'image/png')},
        ).json()
        cover_path = stored_cover_path(game['id'])
        original_remove = games_service._remove_path

        def fail_tombstone_unlink(path: Path):
            if '.game-delete' in path.parts:
                return False
            return original_remove(path)

        monkeypatch.setattr(games_service, '_remove_path', fail_tombstone_unlink)
        response = client.delete(f"/api/games/{game['id']}")
        assert response.status_code == 500
        assert not cover_path.exists()
        uploads_root = DATA / 'uploads'
        journal = uploads_root / '.game-delete-cleanup.json'
        assert journal.is_file()
        pending = json.loads(journal.read_text(encoding='utf-8'))
        assert pending
        tombstone = uploads_root / pending[0]
        assert tombstone.is_file()

        monkeypatch.setattr(games_service, '_remove_path', original_remove)
        from backend.services.games import retry_pending_game_cleanup
        retry_pending_game_cleanup(uploads_root.resolve())
        assert not journal.exists()
        assert not tombstone.exists()


def test_game_deletion_rejects_persisted_path_outside_uploads(tmp_path):
    outside = tmp_path / 'outside.pdf'
    outside.write_bytes(b'keep this file')
    with TestClient(app, raise_server_exceptions=False) as client:
        game = client.post('/api/games', json={'title': 'Delete outside path'}).json()
        with Session(engine) as db:
            db.add(Rulebook(id=str(uuid4()), game_id=game['id'], pdf_path=str(outside)))
            db.commit()
        response = client.delete(f"/api/games/{game['id']}")
        assert response.status_code == 500
        assert outside.read_bytes() == b'keep this file'
        with Session(engine) as db:
            assert db.get(Game, game['id']) is not None


def test_game_deletion_database_failure_restores_assets_and_rows(monkeypatch):
    with TestClient(app, raise_server_exceptions=False) as client:
        game = client.post('/api/games', json={'title': 'Delete database failure'}).json()
        cover = client.post(
            f"/api/games/{game['id']}/cover",
            files={'file': ('cover.png', encoded_image('PNG'), 'image/png')},
        ).json()
        cover_path = stored_cover_path(game['id'])
        original_commit = Session.commit

        def fail_commit(self):
            raise RuntimeError('simulated database failure')

        monkeypatch.setattr('backend.services.games.Session.commit', fail_commit)
        response = client.delete(f"/api/games/{game['id']}")
        assert response.status_code == 500
        assert response.json()['detail']
        assert cover_path.exists()
        with Session(engine) as db:
            assert db.get(Game, game['id']) is not None
        monkeypatch.setattr(Session, 'commit', original_commit)


def test_game_deletion_database_failure_restores_all_assets(monkeypatch):
    with TestClient(app, raise_server_exceptions=False) as client:
        game = client.post('/api/games', json={'title': 'Delete all assets'}).json()
        cover = client.post(
            f"/api/games/{game['id']}/cover",
            files={'file': ('cover.png', encoded_image('PNG'), 'image/png')},
        ).json()
        cover_path = stored_cover_path(game['id'])
        with Session(engine) as db:
            rulebook_path = DATA / 'uploads' / 'rulebooks' / game['id'] / 'rules.pdf'
            extracted_path = DATA / 'uploads' / 'rulebooks' / game['id'] / 'rules.txt'
            rulebook_path.parent.mkdir(parents=True, exist_ok=True)
            rulebook_path.write_bytes(b'rules')
            extracted_path.write_text('rules text', encoding='utf-8')
            db.add(Rulebook(id=str(uuid4()), game_id=game['id'], pdf_path=str(rulebook_path), extracted_text_path=str(extracted_path)))
            db.commit()
        original_commit = Session.commit

        def fail_commit(self):
            raise RuntimeError('simulated database failure')

        monkeypatch.setattr('backend.services.games.Session.commit', fail_commit)
        response = client.delete(f"/api/games/{game['id']}")
        assert response.status_code == 500
        assert cover_path.exists()
        assert rulebook_path.exists()
        assert extracted_path.exists()
        with Session(engine) as db:
            assert db.get(Game, game['id']) is not None
            assert db.exec(select(Rulebook).where(Rulebook.game_id == game['id'])).first() is not None
        monkeypatch.setattr(Session, 'commit', original_commit)


def test_game_deletion_recovery_journal_replays_failed_restore(monkeypatch):
    with TestClient(app, raise_server_exceptions=False) as client:
        game = client.post('/api/games', json={'title': 'Delete recovery'}).json()
        cover = client.post(
            f"/api/games/{game['id']}/cover",
            files={'file': ('cover.png', encoded_image('PNG'), 'image/png')},
        ).json()
        cover_path = stored_cover_path(game['id'])
        original_replace = Path.replace
        original_commit = Session.commit

        def fail_commit(self):
            raise RuntimeError('simulated database failure')

        def fail_restore(path: Path, destination: Path):
            if destination == cover_path:
                raise OSError('simulated restore failure')
            return original_replace(path, destination)

        monkeypatch.setattr('backend.services.games.Session.commit', fail_commit)
        monkeypatch.setattr(Path, 'replace', fail_restore)
        response = client.delete(f"/api/games/{game['id']}")
        assert response.status_code == 500
        recovery = DATA / 'uploads' / '.game-delete-recovery.json'
        assert recovery.is_file()

        monkeypatch.setattr(Path, 'replace', original_replace)
        monkeypatch.setattr(Session, 'commit', original_commit)
        games_service.retry_pending_game_cleanup((DATA / 'uploads').resolve())
        assert not recovery.exists()
        assert cover_path.exists()


def test_game_cleanup_journal_is_replayed_during_startup():
    uploads_root = DATA / 'uploads'
    tombstone = uploads_root / '.game-delete' / 'startup-op' / 'covers' / 'startup.png'
    tombstone.parent.mkdir(parents=True, exist_ok=True)
    tombstone.write_bytes(b'pending cleanup')
    (uploads_root / '.game-delete-cleanup.json').write_text(
        json.dumps([str(tombstone.relative_to(uploads_root))]), encoding='utf-8'
    )
    with TestClient(app):
        pass
    assert not tombstone.exists()
    assert not (uploads_root / '.game-delete-cleanup.json').exists()


def test_game_deletion_requires_host_and_returns_not_found():
    with TestClient(app) as client:
        assert client.delete('/api/games/unknown-game').status_code == 404
        game = client.post('/api/games', json={'title': 'Protected deletion'}).json()
        settings = get_settings()
        previous = settings.auth_disabled
        settings.auth_disabled = False
        try:
            assert client.delete(f"/api/games/{game['id']}").status_code == 401
            with Session(engine) as db:
                assert db.get(Game, game['id']) is not None
        finally:
            settings.auth_disabled = previous


def test_missing_cover_file_returns_not_found():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Missing cover'}).json()
        image = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
        )
        uploaded = client.post(f"/api/games/{game['id']}/cover", files={'file': ('cover.png', image, 'image/png')})
        assert uploaded.status_code == 200
        original_cover_path = stored_cover_path(game['id'])
        original_cover_path.unlink()
        assert client.get(uploaded.json()['cover_url']).status_code == 404


def test_cover_filesystem_failure_restores_previous_cover(monkeypatch):
    with TestClient(app, raise_server_exceptions=False) as client:
        game = client.post('/api/games', json={'title': 'Cover rollback'}).json()
        original = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
        )
        uploaded = client.post(f"/api/games/{game['id']}/cover", files={'file': ('cover.png', original, 'image/png')})
        assert uploaded.status_code == 200
        original_cover_path = stored_cover_path(game['id'])
        original_replace = Path.replace

        def fail_temporary_replace(path: Path, destination: Path):
            if path.name.endswith('.tmp'):
                raise OSError('simulated filesystem failure')
            return original_replace(path, destination)

        monkeypatch.setattr(Path, 'replace', fail_temporary_replace)
        failed = client.post(f"/api/games/{game['id']}/cover", files={'file': ('replacement.jpg', encoded_image('JPEG'), 'image/jpeg')})
        assert failed.status_code == 500
        assert original_cover_path.read_bytes() == original
        restored = client.get(f"/api/games/{game['id']}")
        assert restored.status_code == 200
        assert stored_cover_path(game['id']) == original_cover_path
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


def _publish_pair(game_id: str, state: PipelineState):
    with Session(engine) as db:
        content = db.exec(select(Content).where(Content.game_id == game_id)).one()
        content.pipeline_state = state
        content.published_quickstart_md = '# Start'
        content.published_cheat_sheet_md = '- Rule'
        db.add(content)
        db.commit()


@pytest.mark.parametrize(
    'state',
    [PipelineState.no_rulebook, PipelineState.ready_to_generate],
    ids=['no-rulebook', 'extraction-complete'],
)
def test_session_starts_from_published_content_without_extraction_prerequisite(state):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Extraction optional'}).json()
        _publish_pair(game['id'], state)
        created = client.post(f"/api/sessions?game_id={game['id']}")
        assert created.status_code == 201
        room = client.get('/api/room/' + created.json()['room_slug']).json()
        assert room['quickstart_md'] == '# Start'
        assert room['cheat_sheet_md'] == '- Rule'


@pytest.mark.parametrize(
    'state',
    [PipelineState.no_rulebook, PipelineState.ready_to_generate],
    ids=['no-rulebook', 'extraction-complete'],
)
def test_session_refused_without_published_content_regardless_of_extraction(state):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Nothing published'}).json()
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.pipeline_state = state
            db.add(content)
            db.commit()
        response = client.post(f"/api/sessions?game_id={game['id']}")
        assert response.status_code == 422
        assert response.json()['detail'] == 'Published Content is required to start a Session.'


def test_generation_still_requires_extraction_when_content_is_published():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'No extraction'}).json()
        _publish_pair(game['id'], PipelineState.published)
        response = client.post(f"/api/games/{game['id']}/generate", json={'confirm': True})
        assert response.status_code == 422
        assert response.json()['detail'] == 'Rulebook extraction is not complete.'
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            assert content.published_quickstart_md == '# Start'
            assert content.published_cheat_sheet_md == '- Rule'


def test_session_start_persists_identity_slug_and_utc_timestamp():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Wingspan Start'}).json()
        _publish_pair(game['id'], PipelineState.published)
        response = client.post(f"/api/sessions?game_id={game['id']}")
        assert response.status_code == 201
        body = response.json()
        assert str(UUID(body['id'])) == body['id']
        assert body['game_title_snapshot'] == 'Wingspan Start'
        assert re.fullmatch(r'wingspan-start-[0-9a-z]{4}', body['room_slug'])
        started_at = datetime.fromisoformat(body['started_at'])
        assert started_at.utcoffset() == timedelta(0)
        assert body['ended_at'] is None
        with Session(engine) as db:
            record = db.get(GameSession, body['id'])
            assert record.game_id == game['id']
            assert record.room_slug == body['room_slug']


def test_second_session_is_rejected_and_keeps_active_room():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'One at a time'}).json()
        _publish_pair(game['id'], PipelineState.published)
        first = client.post(f"/api/sessions?game_id={game['id']}").json()
        second = client.post(f"/api/sessions?game_id={game['id']}")
        assert second.status_code == 409
        with Session(engine) as db:
            rows = db.exec(select(GameSession).where(GameSession.game_id == game['id'])).all()
            assert [row.id for row in rows] == [first['id']]
            assert rows[0].ended_at is None
        room = client.get('/api/room/' + first['room_slug'])
        assert room.status_code == 200
        assert room.json()['ended'] is False


def test_session_creation_requires_host():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Host only start'}).json()
        _publish_pair(game['id'], PipelineState.published)
        settings = get_settings()
        previous = settings.auth_disabled
        settings.auth_disabled = False
        try:
            assert client.post(f"/api/sessions?game_id={game['id']}").status_code == 401
        finally:
            settings.auth_disabled = previous
        with Session(engine) as db:
            assert db.exec(select(GameSession).where(GameSession.game_id == game['id'])).all() == []


def test_session_creation_failure_is_not_reported_as_success(monkeypatch):
    with TestClient(app, raise_server_exceptions=False) as client:
        game = client.post('/api/games', json={'title': 'Failing start'}).json()
        _publish_pair(game['id'], PipelineState.published)

        def fail_commit(self):
            raise OperationalError('COMMIT', {}, Exception('disk full'))

        monkeypatch.setattr(Session, 'commit', fail_commit)
        response = client.post(f"/api/sessions?game_id={game['id']}")
        monkeypatch.undo()
        assert response.status_code == 500
        assert response.json() == {'detail': 'Session could not be saved. No Room was created.'}
        with Session(engine) as db:
            assert db.exec(select(GameSession).where(GameSession.game_id == game['id'])).all() == []


def test_concurrent_session_starts_create_one_active_session():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Race'}).json()
        _publish_pair(game['id'], PipelineState.published)
        barrier = threading.Barrier(6)
        codes = []

        def start():
            barrier.wait()
            codes.append(client.post(f"/api/sessions?game_id={game['id']}").status_code)

        threads = [threading.Thread(target=start) for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert codes.count(201) == 1
        assert set(codes) == {201, 409}
        with Session(engine) as db:
            assert len(db.exec(select(GameSession).where(GameSession.game_id == game['id'], GameSession.ended_at.is_(None))).all()) == 1


def test_active_session_index_is_added_to_an_existing_database():
    with TestClient(app):
        pass
    with engine.begin() as conn:
        conn.exec_driver_sql('DROP INDEX IF EXISTS ux_gamesession_one_active_per_game')
    initialize_database()
    with engine.connect() as conn:
        names = [row[1] for row in conn.exec_driver_sql("PRAGMA index_list('gamesession')")]
    assert 'ux_gamesession_one_active_per_game' in names
