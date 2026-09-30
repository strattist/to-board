from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Index, text
from sqlmodel import Field, SQLModel

ACTIVE_SESSION_INDEX = 'ux_gamesession_one_active_per_game'

class GameSession(SQLModel, table=True):
    __table_args__ = (Index(ACTIVE_SESSION_INDEX, 'game_id', unique=True, sqlite_where=text('ended_at IS NULL')),)

    id: str = Field(primary_key=True)
    game_id: str = Field(foreign_key='game.id', index=True)
    game_title_snapshot: str
    room_slug: str = Field(unique=True, index=True)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    ended_at: Optional[datetime] = None
    players_json: str = '[]'
    outcomes_json: str = '[]'
