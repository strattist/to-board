from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import asyncio

from tests.helpers import DATA
import httpx
import pytest
from backend.core.config import Settings
from backend.core.crypto import encrypt_api_key
from backend.db.engine import engine
from backend.main import app
from backend.models import AppSettings, Content, PipelineState, Rulebook
from backend.services.llm import PROMPT, ProviderError, generate_content
from backend.workers.generation import run_generation
from fastapi.testclient import TestClient
from sqlmodel import Session, select


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
