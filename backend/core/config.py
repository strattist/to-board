from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    db_path: Path = Path('/data/db/to-board.db')
    uploads_path: Path = Path('/data/uploads')
    authentik_issuer: str = ''
    authentik_audience: str = ''
    secret_key: str = 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='
    llm_provider: str = 'anthropic'
    anthropic_model: str = 'claude-3-5-haiku-latest'
    google_model: str = 'gemini-2.0-flash'
    auth_disabled: bool = False
    extraction_min_tokens: int = 500
    app_base_url: str = 'http://localhost'
    max_upload_mb: int = 100

    @property
    def db_dir(self) -> Path:
        return self.db_path.parent

@lru_cache
def get_settings() -> Settings:
    value = Settings()
    value.db_dir.mkdir(parents=True, exist_ok=True)
    value.uploads_path.mkdir(parents=True, exist_ok=True)
    return value
