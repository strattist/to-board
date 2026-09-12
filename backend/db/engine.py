from sqlmodel import Session, SQLModel, create_engine
from backend.core.config import get_settings

settings = get_settings()
engine = create_engine(
    f'sqlite:///{settings.db_path}',
    connect_args={'check_same_thread': False},
)

def get_session():
    with Session(engine) as session:
        yield session

def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
