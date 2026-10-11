import shutil

from tests.helpers import DATA
import pytest
from backend.db.engine import engine
from backend.models import AppSettings, Content, Game, GameSession, Rulebook
from sqlmodel import Session, delete


@pytest.fixture(autouse=True)
def reset_test_data():
    with Session(engine) as db:
        db.exec(delete(GameSession))
        db.exec(delete(Rulebook))
        db.exec(delete(Content))
        db.exec(delete(Game))
        db.exec(delete(AppSettings))
        db.commit()
    shutil.rmtree(DATA / 'uploads', ignore_errors=True)
    (DATA / 'uploads').mkdir(parents=True, exist_ok=True)
    for generated_text in DATA.glob('*.txt'):
        generated_text.unlink(missing_ok=True)
    try:
        yield
    finally:
        # Tests may create provider settings; do not let a failed test leak a
        # secret or provider selection into the next test.
        with Session(engine) as db:
            db.exec(delete(AppSettings))
            db.commit()
        for generated_text in DATA.glob('*.txt'):
            generated_text.unlink(missing_ok=True)
