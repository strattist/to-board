from typing import Optional
from sqlmodel import Field, SQLModel

class AppSettings(SQLModel, table=True):
    id: int = Field(default=1, primary_key=True)
    llm_provider: str = 'anthropic'
    api_key_encrypted: Optional[str] = None
