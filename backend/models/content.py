from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from sqlmodel import Field, SQLModel

class PipelineState(str, Enum):
    no_rulebook = 'no_rulebook'
    extracting = 'extracting'
    ready_to_generate = 'ready_to_generate'
    generating = 'generating'
    draft = 'draft'
    published = 'published'
    rejected = 'rejected'

class Content(SQLModel, table=True):
    id: str = Field(primary_key=True)
    game_id: str = Field(foreign_key='game.id', unique=True, index=True)
    pipeline_state: PipelineState = Field(default=PipelineState.no_rulebook)
    prior_pipeline_state: Optional[PipelineState] = None
    draft_quickstart_md: Optional[str] = None
    draft_cheat_sheet_md: Optional[str] = None
    published_quickstart_md: Optional[str] = None
    published_cheat_sheet_md: Optional[str] = None
    generated_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    error_message: Optional[str] = None

    @staticmethod
    def now():
        return datetime.now(timezone.utc)
