from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Field, SQLModel

class GameSession(SQLModel, table=True):
    id: str = Field(primary_key=True)
    game_id: str = Field(foreign_key='game.id', index=True)
    game_title_snapshot: str
    room_slug: str = Field(unique=True, index=True)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    ended_at: Optional[datetime] = None
    players_json: str = '[]'
    outcomes_json: str = '[]'
