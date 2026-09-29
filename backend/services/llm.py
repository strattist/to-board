import json
import re

import httpx

from backend.core.config import get_settings
from backend.core.crypto import decrypt_api_key
from backend.models import AppSettings


PROMPT = '''You are generating board game reference content from an official rulebook. Return exactly one JSON object with two Markdown strings: quickstart_md (a concise narrative guide, at most 1200 words) and cheat_sheet_md (a structured lookup, at most 1000 words). Do not include a preamble, explanation, or code fence. Never invent rules; preserve uncertainty explicitly.'''
_PROVIDER_LABELS = {'anthropic': 'Anthropic', 'google': 'Google', 'openai': 'OpenAI'}
_ERROR_REASONS = {
    'invalid_configuration': 'configuration is invalid',
    'missing_api_key': 'API key is missing',
    'rejected_api_key': 'rejected the API key',
    'model_not_found': 'model was not found or is unavailable',
    'request_rejected': 'model or request configuration was rejected',
    'rate_limited': 'provider rate limit was reached',
    'usage_limit': 'billing or usage limit was reached; review OpenAI billing and usage limits',
    'provider_unavailable': 'provider is unavailable',
    'access_rejected': 'model or provider access was rejected',
    'invalid_response': 'returned an invalid response',
    'request_failed': 'request failed',
    'incomplete_content': 'returned incomplete content',
    'content_blocked': 'blocked the requested content',
}
_MODEL_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')
_ANTHROPIC_MAX_TOKENS = 10000
_OPENAI_MAX_OUTPUT_TOKENS = 10000
_OPENAI_BILLING_ERROR_CODES = {
    'credit_balance_exhausted',
    'organization_spend_limit_exceeded',
    'project_spend_limit_exceeded',
    'organization_usage_limit_exceeded',
}


class ProviderError(ValueError):
    """A provider failure whose message is safe to persist."""

    def __init__(self, provider: str, reason: str):
        self.provider = provider
        self.reason = reason if reason in _ERROR_REASONS else 'request_failed'
        super().__init__(f'{_provider_label(provider)} {_ERROR_REASONS[self.reason]}.')


def _provider_label(provider: str) -> str:
    return _PROVIDER_LABELS.get(provider, 'LLM provider')


def _provider_error(provider: str, reason: str) -> ProviderError:
    """Create an error safe to persist and display to the Host."""
    return ProviderError(provider, reason)


def safe_provider_failure(provider: str) -> str:
    """Fallback message for errors raised outside the provider adapter."""
    return f'{_provider_label(provider)} provider request failed.'


def _status_error(
    provider: str,
    status_code: int,
    provider_error_code: str | None = None,
    provider_error_type: str | None = None,
) -> ProviderError:
    """Map provider HTTP statuses to actionable, secret-safe messages."""
    if status_code == 408:
        return _provider_error(provider, 'provider_unavailable')
    if status_code == 404:
        return _provider_error(provider, 'model_not_found')
    if status_code == 400:
        return _provider_error(provider, 'request_rejected')
    if status_code == 429:
        if provider == 'openai' and (
            provider_error_code in _OPENAI_BILLING_ERROR_CODES
            or provider_error_type == 'insufficient_quota'
        ):
            return _provider_error(provider, 'usage_limit')
        return _provider_error(provider, 'rate_limited')
    if status_code >= 500:
        return _provider_error(provider, 'provider_unavailable')
    return _provider_error(provider, 'request_rejected')


def _validated_model(provider: str, model: str) -> str:
    if not isinstance(model, str) or not _MODEL_PATTERN.fullmatch(model):
        raise _provider_error(provider, 'invalid_configuration')
    return model


async def generate_content(settings: AppSettings, extracted_text: str) -> tuple[str, str]:
    provider = settings.llm_provider
    if provider not in _PROVIDER_LABELS:
        raise _provider_error(provider, 'invalid_configuration')
    if not settings.api_key_encrypted:
        raise _provider_error(provider, 'missing_api_key')
    try:
        key = decrypt_api_key(settings.api_key_encrypted)
    except Exception:
        raise _provider_error(provider, 'rejected_api_key') from None

    try:
        prompt = PROMPT + '\n\nRULEBOOK:\n' + extracted_text
        runtime_settings = get_settings()
        if provider == 'anthropic':
            model = _validated_model(provider, runtime_settings.anthropic_model)
            body = {
                'model': model,
                'max_tokens': _ANTHROPIC_MAX_TOKENS,
                'messages': [{'role': 'user', 'content': prompt}],
            }
            headers = {
                'x-api-key': key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            }
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post('https://api.anthropic.com/v1/messages', json=body, headers=headers)
        elif provider == 'google':
            model = _validated_model(provider, runtime_settings.google_model)
            body = {'contents': [{'parts': [{'text': prompt}]}]}
            # Keep the Google key out of the URL so it cannot be disclosed by
            # an exception string, reverse proxy, or access log.
            headers = {'x-goog-api-key': key, 'content-type': 'application/json'}
            url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(url, json=body, headers=headers)
        else:
            model = _validated_model(provider, runtime_settings.openai_model)
            body = {
                'model': model,
                'instructions': PROMPT,
                'input': extracted_text,
                'store': False,
                'max_output_tokens': _OPENAI_MAX_OUTPUT_TOKENS,
            }
            headers = {'Authorization': f'Bearer {key}', 'content-type': 'application/json'}
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post('https://api.openai.com/v1/responses', json=body, headers=headers)
        if response.status_code == 401:
            raise _provider_error(provider, 'rejected_api_key')
        if response.status_code == 403:
            raise _provider_error(provider, 'access_rejected')
        if response.status_code >= 400:
            provider_error_code = None
            provider_error_type = None
            if provider == 'openai' and response.status_code == 429:
                try:
                    error_payload = response.json()
                    error = error_payload.get('error') if isinstance(error_payload, dict) else None
                    if isinstance(error, dict):
                        code = error.get('code')
                        error_type = error.get('type')
                        provider_error_code = code if isinstance(code, str) else None
                        provider_error_type = error_type if isinstance(error_type, str) else None
                except Exception:
                    pass
            raise _status_error(provider, response.status_code, provider_error_code, provider_error_type)
        if provider == 'anthropic':
            payload = response.json()
            if payload.get('stop_reason') in {'refusal', 'safety'}:
                raise _provider_error(provider, 'content_blocked')
            blocks = payload['content']
            text = ''.join(
                block['text']
                for block in blocks
                if block.get('type', 'text') == 'text' and isinstance(block.get('text'), str)
            )
            if not text:
                raise _provider_error(provider, 'invalid_response')
        elif provider == 'google':
            payload = response.json()
            if payload.get('promptFeedback', {}).get('blockReason'):
                raise _provider_error(provider, 'content_blocked')
            candidate = payload['candidates'][0]
            if candidate.get('finishReason') in {'SAFETY', 'BLOCKLIST', 'PROHIBITED_CONTENT'}:
                raise _provider_error(provider, 'content_blocked')
            text = candidate['content']['parts'][0]['text']
        else:
            payload = response.json()
            if payload.get('status') == 'failed':
                raise _provider_error(provider, 'request_failed')
            if payload.get('status') != 'completed':
                raise _provider_error(provider, 'incomplete_content')
            output = payload.get('output')
            if not isinstance(output, list):
                raise _provider_error(provider, 'invalid_response')
            output_text = []
            for item in output:
                if not isinstance(item, dict):
                    raise _provider_error(provider, 'invalid_response')
                if item.get('type') != 'message':
                    continue
                content = item.get('content')
                if not isinstance(content, list):
                    raise _provider_error(provider, 'invalid_response')
                for content_item in content:
                    if not isinstance(content_item, dict):
                        raise _provider_error(provider, 'invalid_response')
                    if content_item.get('type') == 'refusal':
                        raise _provider_error(provider, 'content_blocked')
                    if content_item.get('type') == 'output_text':
                        value = content_item.get('text')
                        if not isinstance(value, str):
                            raise _provider_error(provider, 'invalid_response')
                        output_text.append(value)
            text = ''.join(output_text)
            if not text.strip():
                raise _provider_error(provider, 'invalid_response')
    except ProviderError:
        raise
    except (httpx.TimeoutException, httpx.RequestError):
        raise _provider_error(provider, 'provider_unavailable') from None
    except (AttributeError, KeyError, IndexError, TypeError, json.JSONDecodeError):
        raise _provider_error(provider, 'invalid_response') from None
    except Exception:
        raise _provider_error(provider, 'request_failed') from None

    try:
        text = text.strip()
        decoder = json.JSONDecoder()
        data = None
        # Models occasionally add a short preamble or Markdown fences despite
        # the JSON-only instruction. Decode the first complete JSON object and
        # ignore only surrounding presentation text; malformed/truncated JSON
        # still fails below.
        for match in re.finditer(r'\{', text):
            try:
                candidate, _ = decoder.raw_decode(text[match.start():])
            except json.JSONDecodeError:
                continue
            if (
                isinstance(candidate, dict)
                and isinstance(candidate.get('quickstart_md'), str)
                and isinstance(candidate.get('cheat_sheet_md'), str)
                and candidate['quickstart_md'].strip()
                and candidate['cheat_sheet_md'].strip()
            ):
                data = candidate
                break
        if data is None:
            raise ValueError
        quickstart, cheat_sheet = data.get('quickstart_md'), data.get('cheat_sheet_md')
        if not isinstance(quickstart, str) or not isinstance(cheat_sheet, str) or not quickstart.strip() or not cheat_sheet.strip():
            raise ValueError
    except Exception:
        raise _provider_error(provider, 'incomplete_content') from None
    return quickstart, cheat_sheet
