import json

import httpx

from backend.core.config import get_settings
from backend.core.crypto import decrypt_api_key
from backend.models import AppSettings


PROMPT = '''You are generating board game reference content from an official rulebook. Return JSON only with two Markdown strings: quickstart_md (a concise narrative guide) and cheat_sheet_md (a structured lookup). Never invent rules; preserve uncertainty explicitly.'''
_PROVIDER_LABELS = {'anthropic': 'Anthropic', 'google': 'Google'}


class ProviderError(ValueError):
    """A provider failure whose message is safe to persist."""


def _provider_label(provider: str) -> str:
    return _PROVIDER_LABELS.get(provider, 'LLM provider')


def _provider_error(provider: str, reason: str) -> ValueError:
    """Create an error safe to persist and display to the Host."""
    return ProviderError(f'{_provider_label(provider)} {reason}.')


def safe_provider_failure(provider: str) -> str:
    """Fallback message for errors raised outside the provider adapter."""
    return f'{_provider_label(provider)} provider request failed.'


def _status_error(provider: str, status_code: int) -> ProviderError:
    """Map provider HTTP statuses to actionable, secret-safe messages."""
    if status_code == 404:
        return _provider_error(provider, 'model was not found or is unavailable')
    if status_code == 400:
        return _provider_error(provider, 'model or request configuration was rejected')
    if status_code == 429:
        return _provider_error(provider, 'provider rate limit was reached')
    if status_code >= 500:
        return _provider_error(provider, 'provider is unavailable')
    return _provider_error(provider, 'request was rejected')


async def generate_content(settings: AppSettings, extracted_text: str) -> tuple[str, str]:
    provider = settings.llm_provider
    if provider not in _PROVIDER_LABELS:
        raise _provider_error(provider, 'configuration is invalid')
    if not settings.api_key_encrypted:
        raise _provider_error(provider, 'API key is missing')
    try:
        key = decrypt_api_key(settings.api_key_encrypted)
    except Exception:
        raise _provider_error(provider, 'rejected the API key') from None

    try:
        prompt = PROMPT + '\n\nRULEBOOK:\n' + extracted_text
        runtime_settings = get_settings()
        if provider == 'anthropic':
            model = runtime_settings.anthropic_model
            body = {
                'model': model,
                'max_tokens': 5000,
                'messages': [{'role': 'user', 'content': prompt}],
            }
            headers = {
                'x-api-key': key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            }
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post('https://api.anthropic.com/v1/messages', json=body, headers=headers)
        else:
            model = runtime_settings.google_model
            body = {'contents': [{'parts': [{'text': prompt}]}]}
            # Keep the Google key out of the URL so it cannot be disclosed by
            # an exception string, reverse proxy, or access log.
            headers = {'x-goog-api-key': key, 'content-type': 'application/json'}
            url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(url, json=body, headers=headers)
        if response.status_code == 401:
            raise _provider_error(provider, 'rejected the API key')
        if response.status_code == 403:
            raise _provider_error(provider, 'model or provider access was rejected')
        if response.status_code >= 400:
            raise _status_error(provider, response.status_code)
        if provider == 'anthropic':
            text = response.json()['content'][0]['text']
        else:
            text = response.json()['candidates'][0]['content']['parts'][0]['text']
    except ProviderError:
        raise
    except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError):
        raise _provider_error(provider, 'returned an invalid response') from None
    except Exception:
        raise _provider_error(provider, 'request failed') from None

    try:
        text = text.strip()
        if text.startswith('```'):
            text = text.split('\n', 1)[1].rsplit('```', 1)[0]
        data = json.loads(text)
        quickstart, cheat_sheet = data.get('quickstart_md'), data.get('cheat_sheet_md')
        if not isinstance(quickstart, str) or not isinstance(cheat_sheet, str) or not quickstart.strip() or not cheat_sheet.strip():
            raise ValueError
    except Exception:
        raise _provider_error(provider, 'returned incomplete content') from None
    return quickstart, cheat_sheet
