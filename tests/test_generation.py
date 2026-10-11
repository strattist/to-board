from uuid import uuid4
import asyncio

from tests.helpers import DATA, _publish_pair
from backend.core.config import get_settings
from backend.core.crypto import decrypt_api_key
from backend.db.engine import engine
from backend.main import app
from backend.models import AppSettings, Content, PipelineState, Rulebook
from backend.services.llm import ProviderError
from backend.workers.generation import run_generation
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select


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
