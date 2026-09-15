from sqlmodel import Session, select
from backend.db.engine import create_db_and_tables, engine
from backend.models import Content, PipelineState

def initialize_database() -> None:
    create_db_and_tables()
    with Session(engine) as session:
        for content in session.exec(select(Content)).all():
            if content.pipeline_state in (PipelineState.extracting, PipelineState.generating):
                content.pipeline_state = content.prior_pipeline_state or PipelineState.no_rulebook
                content.error_message = 'The previous background operation was interrupted; retry when ready.'
                session.add(content)
        session.commit()
