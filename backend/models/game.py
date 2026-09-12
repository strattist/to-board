from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Field, SQLModel

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

class Game(SQLModel, table=True):
    id: str = Field(primary_key=True)
    title: str
    cover_image_path: Optional[str] = None
    room_slug_prefix: str
    created_at: datetime = Field(default_factory=now_utc)

class Rulebook(SQLModel, table=True):
    id: str = Field(primary_key=True)
    game_id: str = Field(foreign_key='game.id', unique=True, index=True)
    pdf_path: str
    extracted_text_path: Optional[str] = None
    uploaded_at: datetime = Field(default_factory=now_utc)
