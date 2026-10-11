from uuid import uuid4

from tests.helpers import DATA
import pytest
from backend.core.config import get_settings
from backend.db.engine import engine
from backend.main import app
from backend.models import AppSettings, Content, GameSession, PipelineState, Rulebook
from fastapi.testclient import TestClient
from sqlmodel import Session, select


def test_publish_copies_complete_draft_and_clears_draft_pair():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Publish test'}).json()
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            content.pipeline_state = PipelineState.draft
            content.draft_quickstart_md = '# Draft'
            content.draft_cheat_sheet_md = '- Draft rule'
            content.published_quickstart_md = '# Older Published'
            content.published_cheat_sheet_md = '- Older published rule'
            db.add(content)
            db.commit()
        revision = client.get(f"/api/games/{game['id']}/content").json()['draft_revision']
        response = client.post(
            f"/api/games/{game['id']}/content/publish",
            json={'expected_revision': revision},
        )
        assert response.status_code == 200
        assert response.json()['pipeline_state'] == 'published'
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            assert content.pipeline_state == PipelineState.published
            assert content.draft_quickstart_md is None
            assert content.draft_cheat_sheet_md is None
            assert content.published_quickstart_md == '# Draft'
            assert content.published_cheat_sheet_md == '- Draft rule'


def test_reject_clears_complete_draft_preserves_published_pair_and_allows_regeneration(monkeypatch):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Reject test'}).json()
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            content.pipeline_state = PipelineState.draft
            content.draft_quickstart_md = '# Draft'
            content.draft_cheat_sheet_md = '- Draft rule'
            content.published_quickstart_md = '# Published'
            content.published_cheat_sheet_md = '- Published rule'
            db.add(content)
            db.commit()
        revision = client.get(f"/api/games/{game['id']}/content").json()['draft_revision']
        response = client.post(
            f"/api/games/{game['id']}/content/reject",
            json={'expected_revision': revision},
        )
        assert response.status_code == 200
        assert response.json()['pipeline_state'] == 'rejected'
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            assert content.pipeline_state == PipelineState.rejected
            assert content.draft_quickstart_md is None
            assert content.draft_cheat_sheet_md is None
            assert content.published_quickstart_md == '# Published'
            assert content.published_cheat_sheet_md == '- Published rule'

        extracted = DATA / 'uploads' / f"rejected-regeneration-{uuid4()}.txt"
        extracted.write_text('rules', encoding='utf-8')
        rulebook_id = str(uuid4())
        with Session(engine) as db:
            db.add(Rulebook(id=rulebook_id, game_id=game['id'], pdf_path='rules.pdf', extracted_text_path=str(extracted)))
            db.add(AppSettings(id=1, llm_provider='anthropic', api_key_encrypted='ciphertext'))
            db.commit()
        scheduled = []
        monkeypatch.setattr('backend.routers.games.run_generation', lambda *args: scheduled.append(args))
        response = client.post(
            f"/api/games/{game['id']}/generate",
            json={'confirm': True, 'allow_low_quality': True},
        )
        extracted.unlink(missing_ok=True)
        assert response.status_code == 200
        assert response.json()['pipeline_state'] == 'generating'
        assert scheduled == [(game['id'], rulebook_id)]


@pytest.mark.parametrize('action', ['publish', 'reject'])
def test_publish_and_reject_reject_superseded_draft_revision_without_mutation(action):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': f'Superseded Draft {action} test'}).json()
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            content.pipeline_state = PipelineState.draft
            content.draft_quickstart_md = '# Reviewed Draft'
            content.draft_cheat_sheet_md = '- Reviewed rule'
            content.published_quickstart_md = '# Existing Published'
            content.published_cheat_sheet_md = '- Existing published rule'
            db.add(content)
            db.commit()

        reviewed_revision = client.get(f"/api/games/{game['id']}/content").json()['draft_revision']
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            content.draft_quickstart_md = '# New Draft the Host has not reviewed'
            content.draft_cheat_sheet_md = '- New rule'
            db.add(content)
            db.commit()
        current_revision = client.get(f"/api/games/{game['id']}/content").json()['draft_revision']
        assert current_revision != reviewed_revision

        response = client.post(
            f"/api/games/{game['id']}/content/{action}",
            json={'expected_revision': reviewed_revision},
        )
        assert response.status_code == 409
        assert response.json()['detail'] == 'Draft changed since it was loaded. Reload before acting.'
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            assert content.pipeline_state == PipelineState.draft
            assert content.draft_quickstart_md == '# New Draft the Host has not reviewed'
            assert content.draft_cheat_sheet_md == '- New rule'
            assert content.published_quickstart_md == '# Existing Published'
            assert content.published_cheat_sheet_md == '- Existing published rule'


@pytest.mark.parametrize('action', ['publish', 'reject'])
def test_publish_and_reject_require_a_reviewed_draft_revision(action):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': f'Missing revision {action} test'}).json()
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            content.pipeline_state = PipelineState.draft
            content.draft_quickstart_md = '# Draft'
            content.draft_cheat_sheet_md = '- Draft rule'
            db.add(content)
            db.commit()

        response = client.post(f"/api/games/{game['id']}/content/{action}")
        assert response.status_code == 409
        assert response.json()['detail'] == 'Draft changed since it was loaded. Reload before acting.'
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            assert content.pipeline_state == PipelineState.draft
            assert content.draft_quickstart_md == '# Draft'
            assert content.draft_cheat_sheet_md == '- Draft rule'


@pytest.mark.parametrize('action', ['publish', 'reject'])
@pytest.mark.parametrize(
    ('quickstart_md', 'cheat_sheet_md'),
    [
        ('# Draft', None),
        (None, '- Draft rule'),
        ('', '- Draft rule'),
        ('# Draft', ''),
        ('   ', '- Draft rule'),
        ('# Draft', '\n\t'),
    ],
    ids=[
        'missing-quickstart',
        'missing-cheat-sheet',
        'empty-quickstart',
        'empty-cheat-sheet',
        'whitespace-quickstart',
        'whitespace-cheat-sheet',
    ],
)
def test_publish_and_reject_require_complete_draft_without_mutation(action, quickstart_md, cheat_sheet_md):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': f'Incomplete {action} test'}).json()
        before = {
            'quickstart': quickstart_md,
            'cheat_sheet': cheat_sheet_md,
            'published_quickstart': '# Existing Published',
            'published_cheat_sheet': '- Existing published rule',
        }
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            content.pipeline_state = PipelineState.draft
            content.draft_quickstart_md = before['quickstart']
            content.draft_cheat_sheet_md = before['cheat_sheet']
            content.published_quickstart_md = before['published_quickstart']
            content.published_cheat_sheet_md = before['published_cheat_sheet']
            db.add(content)
            db.commit()

        response = client.post(f"/api/games/{game['id']}/content/{action}")
        assert response.status_code == 409
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            assert content.pipeline_state == PipelineState.draft
            assert content.draft_quickstart_md == before['quickstart']
            assert content.draft_cheat_sheet_md == before['cheat_sheet']
            assert content.published_quickstart_md == before['published_quickstart']
            assert content.published_cheat_sheet_md == before['published_cheat_sheet']


@pytest.mark.parametrize('action', ['publish', 'reject'])
@pytest.mark.parametrize('pipeline_state', [state for state in PipelineState if state != PipelineState.draft])
def test_publish_and_reject_require_draft_state_without_mutation(action, pipeline_state):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': f'Invalid state {action} test'}).json()
        before = {
            'quickstart': '# Draft',
            'cheat_sheet': '- Draft rule',
            'published_quickstart': '# Existing Published',
            'published_cheat_sheet': '- Existing published rule',
        }
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            content.pipeline_state = pipeline_state
            content.draft_quickstart_md = before['quickstart']
            content.draft_cheat_sheet_md = before['cheat_sheet']
            content.published_quickstart_md = before['published_quickstart']
            content.published_cheat_sheet_md = before['published_cheat_sheet']
            db.add(content)
            db.commit()

        response = client.post(f"/api/games/{game['id']}/content/{action}")
        assert response.status_code == 409
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            assert content.pipeline_state == pipeline_state
            assert content.draft_quickstart_md == before['quickstart']
            assert content.draft_cheat_sheet_md == before['cheat_sheet']
            assert content.published_quickstart_md == before['published_quickstart']
            assert content.published_cheat_sheet_md == before['published_cheat_sheet']


def test_preview_returns_published_pair_without_creating_session_or_provider_work(monkeypatch):
    generation_jobs = []

    async def record_generation_job(*args):
        generation_jobs.append(args)

    monkeypatch.setattr('backend.routers.games.run_generation', record_generation_job)
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Preview without a Session'}).json()
        published_pair = {
            'quickstart_md': '# Published Guide',
            'cheat_sheet_md': '- Published rule',
        }
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.pipeline_state = PipelineState.generating
            content.prior_pipeline_state = PipelineState.published
            content.published_quickstart_md = published_pair['quickstart_md']
            content.published_cheat_sheet_md = published_pair['cheat_sheet_md']
            content.draft_quickstart_md = '# Private Draft Guide'
            content.draft_cheat_sheet_md = '- Private Draft rule'
            db.add(content)
            db.commit()

        preview = client.get(f"/api/games/{game['id']}/preview")
        assert preview.status_code == 200
        assert preview.json()['quickstart_md'] == published_pair['quickstart_md']
        assert preview.json()['cheat_sheet_md'] == published_pair['cheat_sheet_md']
        assert 'Private Draft' not in preview.text
        assert generation_jobs == []
        with Session(engine) as db:
            assert db.exec(select(GameSession).where(GameSession.game_id == game['id'])).all() == []
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            assert content.pipeline_state == PipelineState.generating
            assert content.prior_pipeline_state == PipelineState.published
            assert content.published_quickstart_md == published_pair['quickstart_md']
            assert content.published_cheat_sheet_md == published_pair['cheat_sheet_md']

        started = client.post(f"/api/sessions?game_id={game['id']}")
        assert started.status_code == 201
        room = client.get('/api/room/' + started.json()['room_slug'])
        assert room.status_code == 200
        assert room.json()['quickstart_md'] == preview.json()['quickstart_md']
        assert room.json()['cheat_sheet_md'] == preview.json()['cheat_sheet_md']


@pytest.mark.parametrize(
    ('pipeline_state', 'published_quickstart', 'published_cheat_sheet', 'draft_quickstart', 'draft_cheat_sheet'),
    [
        (PipelineState.draft, None, None, '# Private Draft Guide', '- Private Draft rule'),
        (PipelineState.rejected, None, None, None, None),
        (PipelineState.draft, '# Partial Published Guide', None, '# Private Draft Guide', '- Private Draft rule'),
        (PipelineState.draft, None, '- Partial Published rule', '# Private Draft Guide', '- Private Draft rule'),
        (PipelineState.draft, '', '- Partial Published rule', '# Private Draft Guide', '- Private Draft rule'),
        (PipelineState.draft, '# Partial Published Guide', '', '# Private Draft Guide', '- Private Draft rule'),
    ],
    ids=[
        'draft-only',
        'rejected',
        'missing-published-cheat-sheet',
        'missing-published-guide',
        'empty-published-guide',
        'empty-published-cheat-sheet',
    ],
)
def test_preview_does_not_return_draft_rejected_or_incomplete_published_content(
    pipeline_state, published_quickstart, published_cheat_sheet, draft_quickstart, draft_cheat_sheet
):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Unavailable Preview'}).json()
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.pipeline_state = pipeline_state
            content.published_quickstart_md = published_quickstart
            content.published_cheat_sheet_md = published_cheat_sheet
            content.draft_quickstart_md = draft_quickstart
            content.draft_cheat_sheet_md = draft_cheat_sheet
            before = (
                content.pipeline_state,
                content.published_quickstart_md,
                content.published_cheat_sheet_md,
                content.draft_quickstart_md,
                content.draft_cheat_sheet_md,
            )
            db.add(content)
            db.commit()

        response = client.get(f"/api/games/{game['id']}/preview")
        assert response.status_code == 404
        assert response.json()['detail'] == 'Published Content not found.'
        assert 'Private Draft' not in response.text
        assert 'Partial Published' not in response.text
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            after = (
                content.pipeline_state,
                content.published_quickstart_md,
                content.published_cheat_sheet_md,
                content.draft_quickstart_md,
                content.draft_cheat_sheet_md,
            )
            assert after == before
            assert db.exec(select(GameSession).where(GameSession.game_id == game['id'])).all() == []


def test_preview_requires_host_authentication():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Protected Preview'}).json()
        settings = get_settings()
        previous = settings.auth_disabled
        settings.auth_disabled = False
        try:
            response = client.get(f"/api/games/{game['id']}/preview")
            assert response.status_code == 401
            assert 'Published Guide' not in response.text
        finally:
            settings.auth_disabled = previous
