import json
import httpx
from backend.core.crypto import decrypt_api_key
from backend.models import AppSettings

PROMPT = '''You are generating board game reference content from an official rulebook. Return JSON only with two Markdown strings: quickstart_md (a concise narrative guide) and cheat_sheet_md (a structured lookup). Never invent rules; preserve uncertainty explicitly.'''

async def generate_content(settings: AppSettings, extracted_text: str) -> tuple[str, str]:
    if not settings.api_key_encrypted:
        raise ValueError('API key is missing — add one in Settings.')
    key = decrypt_api_key(settings.api_key_encrypted)
    provider = settings.llm_provider
    if provider == 'anthropic':
        body = {'model': 'claude-3-5-haiku-latest', 'max_tokens': 5000, 'messages': [{'role': 'user', 'content': PROMPT + '\n\nRULEBOOK:\n' + extracted_text}]}
        headers = {'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'}
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post('https://api.anthropic.com/v1/messages', json=body, headers=headers)
        response.raise_for_status()
        text = response.json()['content'][0]['text']
    elif provider == 'google':
        body = {'contents': [{'parts': [{'text': PROMPT + '\n\nRULEBOOK:\n' + extracted_text}]}]}
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}', json=body)
        response.raise_for_status()
        text = response.json()['candidates'][0]['content']['parts'][0]['text']
    else:
        raise ValueError(f'Unsupported LLM provider: {provider}.')
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1].rsplit('```', 1)[0]
    data = json.loads(text)
    quickstart, cheat_sheet = data.get('quickstart_md'), data.get('cheat_sheet_md')
    if not isinstance(quickstart, str) or not isinstance(cheat_sheet, str) or not quickstart.strip() or not cheat_sheet.strip():
        raise ValueError('The provider returned incomplete content.')
    return quickstart, cheat_sheet
