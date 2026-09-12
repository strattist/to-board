from functools import lru_cache
from typing import Any
import httpx
import jwt
from fastapi import Header, HTTPException, status
from backend.core.config import get_settings

@lru_cache
def _jwks() -> dict[str, Any]:
    settings = get_settings()
    issuer = settings.authentik_issuer.rstrip('/')
    candidates = [f'{issuer}/jwks.json', f'{issuer}/.well-known/jwks.json']
    for url in candidates:
        try:
            response = httpx.get(url, timeout=5)
            if response.is_success: return response.json()
        except httpx.HTTPError: continue
    raise HTTPException(status_code=503, detail='Host identity provider is unavailable.')

async def require_host(authorization: str | None = Header(default=None)) -> dict:
    settings = get_settings()
    if settings.auth_disabled:
        return {'sub': 'local-host'}
    if not settings.authentik_issuer:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Host authentication is not configured.')
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication required.')
    token = authorization[7:].strip()
    try:
        header = jwt.get_unverified_header(token)
        jwks = _jwks()
        key_data = next((key for key in jwks.get('keys', []) if key.get('kid') == header.get('kid')), None)
        if not key_data: raise ValueError('Signing key not found')
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key_data)
        options = {'verify_aud': bool(settings.authentik_audience)}
        claims = jwt.decode(token, public_key, algorithms=['RS256'], issuer=settings.authentik_issuer, audience=settings.authentik_audience or None, options=options)
        return claims
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid Host authentication token.') from exc
