from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session
from backend.core.auth import require_host
from backend.core.crypto import encrypt_api_key
from backend.db.engine import get_session
from backend.models import AppSettings

router = APIRouter(prefix='/api/settings', tags=['settings'])
class SettingsUpdate(BaseModel):
    provider: str = Field(pattern='^(anthropic|google|openai)$')
    api_key: str = Field(min_length=1)

    def normalized_api_key(self) -> str:
        """Return the submitted key after rejecting empty whitespace-only values."""
        key = self.api_key.strip()
        if not key:
            raise ValueError('API key is required.')
        return key

def safe(settings: AppSettings) -> dict:
    return {'provider': settings.llm_provider, 'configured': bool(settings.api_key_encrypted)}

@router.get('')
def read_settings(session: Session = Depends(get_session), _host=Depends(require_host)):
    settings = session.get(AppSettings, 1)
    if not settings:
        settings = AppSettings(id=1); session.add(settings); session.commit(); session.refresh(settings)
    return safe(settings)

@router.put('')
def update_settings(body: SettingsUpdate, session: Session = Depends(get_session), _host=Depends(require_host)):
    try:
        api_key = body.normalized_api_key()
    except ValueError as exc:
        # Keep validation in the standard FastAPI error shape without ever
        # persisting a blank replacement over a previously valid key.
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    settings = session.get(AppSettings, 1) or AppSettings(id=1)
    encrypted_key = encrypt_api_key(api_key)
    settings.llm_provider = body.provider
    settings.api_key_encrypted = encrypted_key
    session.add(settings); session.commit(); session.refresh(settings)
    return safe(settings)
