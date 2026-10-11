from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4
import re
import threading

from tests.helpers import _publish_pair, _published_game, _make_queue
import pytest
from backend.core.config import get_settings
from backend.db.engine import engine
from backend.db.init import initialize_database
from backend.main import app
from backend.models import Content, GameSession, PipelineState
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from sqlmodel import Session, select


@pytest.mark.parametrize(
    'busy_pipeline_state',
    [PipelineState.extracting, PipelineState.generating],
    ids=['extracting', 'generating'],
)
def test_session_room_and_close_state(busy_pipeline_state):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Session test'}).json()
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            content.pipeline_state = busy_pipeline_state
            content.prior_pipeline_state = PipelineState.published
            content.published_quickstart_md = '# Start'
            content.published_cheat_sheet_md = '- Rule'
            db.add(content)
            db.commit()
        created = client.post(f"/api/sessions?game_id={game['id']}")
        assert created.status_code == 201
        record = created.json()
        preview = client.get(f"/api/games/{game['id']}/preview")
        assert preview.status_code == 200
        assert preview.json()['quickstart_md'] == '# Start'
        assert client.get('/api/room/' + record['room_slug']).json()['quickstart_md'] == '# Start'
        assert client.post('/api/sessions/' + record['id'] + '/end').status_code == 200
        assert client.get('/api/room/' + record['room_slug']).json()['ended'] is True


@pytest.mark.parametrize(
    ('quickstart_md', 'cheat_sheet_md'),
    [('# Published guide', None), (None, '- Published rule')],
    ids=['missing-quickstart', 'missing-cheat-sheet'],
)
def test_session_requires_complete_published_pair_during_generation(quickstart_md, cheat_sheet_md):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Incomplete published pair'}).json()
        room_slug = f"incomplete-published-{game['id'][:8]}"
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.pipeline_state = PipelineState.generating
            content.prior_pipeline_state = PipelineState.published
            content.published_quickstart_md = quickstart_md
            content.published_cheat_sheet_md = cheat_sheet_md
            db.add_all([
                content,
                GameSession(
                    id=str(uuid4()),
                    game_id=game['id'],
                    game_title_snapshot=game['title'],
                    room_slug=room_slug,
                ),
            ])
            db.commit()

        response = client.post(f"/api/sessions?game_id={game['id']}")
        assert response.status_code == 422
        assert response.json()['detail'] == 'Published Content is required to start a Session.'
        preview = client.get(f"/api/games/{game['id']}/preview")
        assert preview.status_code == 404
        assert preview.json()['detail'] == 'Published Content not found.'
        room = client.get(f"/api/room/{room_slug}")
        assert room.status_code == 404
        assert room.json()['detail'] == 'Published Content is unavailable for this Room.'


@pytest.mark.parametrize(
    'state',
    [PipelineState.no_rulebook, PipelineState.ready_to_generate],
    ids=['no-rulebook', 'extraction-complete'],
)
def test_session_starts_from_published_content_without_extraction_prerequisite(state):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Extraction optional'}).json()
        _publish_pair(game['id'], state)
        created = client.post(f"/api/sessions?game_id={game['id']}")
        assert created.status_code == 201
        room = client.get('/api/room/' + created.json()['room_slug']).json()
        assert room['quickstart_md'] == '# Start'
        assert room['cheat_sheet_md'] == '- Rule'


@pytest.mark.parametrize(
    'state',
    [PipelineState.no_rulebook, PipelineState.ready_to_generate],
    ids=['no-rulebook', 'extraction-complete'],
)
def test_session_refused_without_published_content_regardless_of_extraction(state):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Nothing published'}).json()
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.pipeline_state = state
            db.add(content)
            db.commit()
        response = client.post(f"/api/sessions?game_id={game['id']}")
        assert response.status_code == 422
        assert response.json()['detail'] == 'Published Content is required to start a Session.'


def test_session_start_persists_identity_slug_and_utc_timestamp():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Wingspan Start'}).json()
        _publish_pair(game['id'], PipelineState.published)
        response = client.post(f"/api/sessions?game_id={game['id']}")
        assert response.status_code == 201
        body = response.json()
        assert str(UUID(body['id'])) == body['id']
        assert body['game_title_snapshot'] == 'Wingspan Start'
        assert re.fullmatch(r'wingspan-start-[0-9a-z]{4}', body['room_slug'])
        started_at = datetime.fromisoformat(body['started_at'])
        assert started_at.utcoffset() == timedelta(0)
        assert body['ended_at'] is None
        with Session(engine) as db:
            record = db.get(GameSession, body['id'])
            assert record.game_id == game['id']
            assert record.room_slug == body['room_slug']


def test_second_session_is_rejected_and_keeps_active_room():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'One at a time'}).json()
        _publish_pair(game['id'], PipelineState.published)
        first = client.post(f"/api/sessions?game_id={game['id']}").json()
        second = client.post(f"/api/sessions?game_id={game['id']}")
        assert second.status_code == 409
        with Session(engine) as db:
            rows = db.exec(select(GameSession).where(GameSession.game_id == game['id'])).all()
            assert [row.id for row in rows] == [first['id']]
            assert rows[0].ended_at is None
        room = client.get('/api/room/' + first['room_slug'])
        assert room.status_code == 200
        assert room.json()['ended'] is False


def test_session_creation_requires_host():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Host only start'}).json()
        _publish_pair(game['id'], PipelineState.published)
        settings = get_settings()
        previous = settings.auth_disabled
        settings.auth_disabled = False
        try:
            assert client.post(f"/api/sessions?game_id={game['id']}").status_code == 401
        finally:
            settings.auth_disabled = previous
        with Session(engine) as db:
            assert db.exec(select(GameSession).where(GameSession.game_id == game['id'])).all() == []


def test_session_room_url_uses_app_base_url_and_strips_trailing_slash():
    settings = get_settings()
    previous = settings.app_base_url
    try:
        with TestClient(app) as client:
            game = client.post('/api/games', json={'title': 'Room Url'}).json()
            _publish_pair(game['id'], PipelineState.published)
            settings.app_base_url = 'http://192.168.1.20/'
            created = client.post(f"/api/sessions?game_id={game['id']}").json()
            assert created['room_url'] == f"http://192.168.1.20/room/{created['room_slug']}"
            fetched = client.get(f"/api/sessions/{created['id']}").json()
            assert fetched['room_url'] == created['room_url']
            settings.app_base_url = 'http://localhost'
            assert client.get(f"/api/sessions/{created['id']}").json()['room_url'] == f"http://localhost/room/{created['room_slug']}"
    finally:
        settings.app_base_url = previous


def test_session_get_requires_host():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Host only get'}).json()
        _publish_pair(game['id'], PipelineState.published)
        created = client.post(f"/api/sessions?game_id={game['id']}").json()
        settings = get_settings()
        previous = settings.auth_disabled
        settings.auth_disabled = False
        try:
            assert client.get(f"/api/sessions/{created['id']}").status_code == 401
        finally:
            settings.auth_disabled = previous


def test_session_creation_failure_is_not_reported_as_success(monkeypatch):
    with TestClient(app, raise_server_exceptions=False) as client:
        game = client.post('/api/games', json={'title': 'Failing start'}).json()
        _publish_pair(game['id'], PipelineState.published)

        def fail_commit(self):
            raise OperationalError('COMMIT', {}, Exception('disk full'))

        monkeypatch.setattr(Session, 'commit', fail_commit)
        response = client.post(f"/api/sessions?game_id={game['id']}")
        monkeypatch.undo()
        assert response.status_code == 500
        assert response.json() == {'detail': 'Session could not be saved. No Room was created.'}
        with Session(engine) as db:
            assert db.exec(select(GameSession).where(GameSession.game_id == game['id'])).all() == []


def test_concurrent_session_starts_create_one_active_session():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Race'}).json()
        _publish_pair(game['id'], PipelineState.published)
        barrier = threading.Barrier(6)
        codes = []

        def start():
            barrier.wait()
            codes.append(client.post(f"/api/sessions?game_id={game['id']}").status_code)

        threads = [threading.Thread(target=start) for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert codes.count(201) == 1
        assert set(codes) == {201, 409}
        with Session(engine) as db:
            assert len(db.exec(select(GameSession).where(GameSession.game_id == game['id'], GameSession.ended_at.is_(None))).all()) == 1


def test_active_session_index_is_added_to_an_existing_database():
    with TestClient(app):
        pass
    with engine.begin() as conn:
        conn.exec_driver_sql('DROP INDEX IF EXISTS ux_gamesession_one_active_per_game')
    initialize_database()
    with engine.connect() as conn:
        names = [row[1] for row in conn.exec_driver_sql("PRAGMA index_list('gamesession')")]
    assert 'ux_gamesession_one_active_per_game' in names


def test_room_unknown_slug_is_not_found_without_content():
    with TestClient(app) as client:
        response = client.get('/api/room/no-such-room-0000')
        assert response.status_code == 404
        assert set(response.json()) == {'detail'}
        assert client.get('/api/room/no-such-room-0000/events').status_code == 404


def test_room_never_exposes_draft_content_and_ended_room_hides_published():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Draft Guard'}).json()
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).first()
            content.pipeline_state = PipelineState.draft
            content.prior_pipeline_state = PipelineState.published
            content.published_quickstart_md = '# Published'
            content.published_cheat_sheet_md = '- Published rule'
            content.draft_quickstart_md = '# SECRET DRAFT'
            content.draft_cheat_sheet_md = '- SECRET DRAFT'
            db.add(content)
            db.commit()
        started = client.post(f"/api/sessions?game_id={game['id']}").json()
        room = client.get('/api/room/' + started['room_slug'])
        assert room.status_code == 200
        assert 'SECRET DRAFT' not in room.text
        assert room.json()['quickstart_md'] == '# Published'
        assert client.post('/api/sessions/' + started['id'] + '/end').status_code == 200
        ended = client.get('/api/room/' + started['room_slug'])
        assert ended.status_code == 200
        assert ended.json() == {'ended': True, 'game_title': 'Draft Guard', 'room_slug': started['room_slug']}
        assert client.get('/api/room/' + started['room_slug'] + '/events').text == 'event: session-ended\ndata: {}\n\n'


def test_guest_ip_is_not_logged_by_the_stack():
    root = Path(__file__).resolve().parent.parent
    assert '--no-access-log' in (root / 'backend/Dockerfile').read_text()
    nginx = (root / 'nginx/nginx.conf').read_text()
    assert 'access_log off;' in nginx
    assert 'proxy_buffering off;' in nginx


def test_end_session_sets_utc_ended_at_and_deactivates_room():
    with TestClient(app) as client:
        game = _published_game(client, 'End Persist')
        started = client.post(f"/api/sessions?game_id={game['id']}").json()
        ended = client.post('/api/sessions/' + started['id'] + '/end')
        assert ended.status_code == 200
        body = ended.json()
        assert body['active'] is False
        assert datetime.fromisoformat(body['ended_at']).utcoffset() == timedelta(0)
        with Session(engine) as db:
            assert db.get(GameSession, started['id']).ended_at is not None
        assert client.get('/api/room/' + started['room_slug']).json()['ended'] is True


def test_end_session_notifies_connected_guests_once(monkeypatch):
    sent = []
    monkeypatch.setattr('backend.routers.sessions.notify_session_ended', lambda slug: sent.append(slug))
    with TestClient(app) as client:
        game = _published_game(client, 'End Notify')
        started = client.post(f"/api/sessions?game_id={game['id']}").json()
        first = client.post('/api/sessions/' + started['id'] + '/end').json()
        second = client.post('/api/sessions/' + started['id'] + '/end')
        assert second.status_code == 200
        assert second.json()['ended_at'] == first['ended_at']
        assert sent == [started['room_slug']]


def test_end_session_failure_is_not_reported_as_ended(monkeypatch):
    sent = []
    monkeypatch.setattr('backend.routers.sessions.notify_session_ended', lambda slug: sent.append(slug))
    with TestClient(app) as client:
        game = _published_game(client, 'End Failure')
        started = client.post(f"/api/sessions?game_id={game['id']}").json()

        def fail_commit(self):
            raise SQLAlchemyError('disk full')

        with monkeypatch.context() as patched:
            patched.setattr(Session, 'commit', fail_commit)
            failed = client.post('/api/sessions/' + started['id'] + '/end')
        assert failed.status_code == 500
        assert 'could not be ended' in failed.json()['detail']
        assert sent == []
        with Session(engine) as db:
            assert db.get(GameSession, started['id']).ended_at is None
        assert client.get('/api/room/' + started['room_slug']).json()['ended'] is False


def test_end_session_unknown_id_is_not_found():
    with TestClient(app) as client:
        assert client.post('/api/sessions/does-not-exist/end').status_code == 404


def test_end_session_requires_host():
    with TestClient(app) as client:
        game = _published_game(client, 'End Auth')
        started = client.post(f"/api/sessions?game_id={game['id']}").json()
        settings = get_settings()
        previous = settings.auth_disabled
        settings.auth_disabled = False
        try:
            assert client.post('/api/sessions/' + started['id'] + '/end').status_code == 401
        finally:
            settings.auth_disabled = previous
        with Session(engine) as db:
            assert db.get(GameSession, started['id']).ended_at is None


def test_end_session_delivers_session_ended_to_a_real_room_stream():
    import asyncio, threading
    from backend.routers import room as room_router
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    try:
        with TestClient(app) as client:
            game = _published_game(client, 'End Stream')
            started = client.post(f"/api/sessions?game_id={game['id']}").json()
            queue = asyncio.run_coroutine_threadsafe(_make_queue(), loop).result(2)
            room_router._connections[started['room_slug']].add((queue, loop))
            assert client.post('/api/sessions/' + started['id'] + '/end').status_code == 200
            event = asyncio.run_coroutine_threadsafe(queue.get(), loop).result(2)
            assert event == 'event: session-ended\ndata: {}\n\n'
            client.post('/api/sessions/' + started['id'] + '/end')
            assert queue.empty()
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(2)
        room_router._connections.clear()


def test_end_session_notification_failure_does_not_undo_the_end(monkeypatch):
    def boom(slug):
        raise RuntimeError('stream registry broke')

    monkeypatch.setattr('backend.routers.sessions.notify_session_ended', boom)
    with TestClient(app) as client:
        game = _published_game(client, 'End Notify Boom')
        started = client.post(f"/api/sessions?game_id={game['id']}").json()
        response = client.post('/api/sessions/' + started['id'] + '/end')
        assert response.status_code == 200
        assert response.json()['active'] is False


def test_room_stream_receives_an_end_that_lands_while_it_connects(monkeypatch):
    import asyncio
    from backend.routers import room as room_router

    def end_lands_during_lookup(slug):
        room_router.notify_session_ended(slug)
        return False  # the state was read just before the end committed

    monkeypatch.setattr(room_router, '_lookup_ended', end_lands_during_lookup)

    async def run():
        response = await room_router.room_events('race-room')
        return [chunk async for chunk in response.body_iterator]

    assert asyncio.run(run()) == [': connected\n\n', 'event: session-ended\ndata: {}\n\n']
    assert 'race-room' not in room_router._connections


def test_room_stream_for_unknown_slug_leaves_no_registration():
    from backend.routers import room as room_router

    with TestClient(app) as client:
        assert client.get('/api/room/nope-0000/events').status_code == 404
    assert 'nope-0000' not in room_router._connections


def _restart_application():
    """Simulate an API container restart over the same database file."""
    engine.dispose()
    with TestClient(app):
        pass


def test_active_session_survives_an_api_restart_and_stays_active():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Restart active'}).json()
        _publish_pair(game['id'], PipelineState.published)
        started = client.post(f"/api/sessions?game_id={game['id']}").json()

    _restart_application()

    with TestClient(app) as client:
        reloaded = client.get(f"/api/sessions/{started['id']}").json()
        for key in ('id', 'game_id', 'game_title_snapshot', 'room_slug', 'started_at'):
            assert reloaded[key] == started[key]
        assert reloaded['ended_at'] is None
        assert reloaded['active'] is True
        assert client.post(f"/api/sessions?game_id={game['id']}").status_code == 409
        assert client.get(f"/api/room/{started['room_slug']}").json()['ended'] is False


def test_ended_session_stays_ended_after_an_api_restart():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Restart ended'}).json()
        _publish_pair(game['id'], PipelineState.published)
        started = client.post(f"/api/sessions?game_id={game['id']}").json()
        ended = client.post(f"/api/sessions/{started['id']}/end").json()

    _restart_application()

    with TestClient(app) as client:
        reloaded = client.get(f"/api/sessions/{started['id']}").json()
        assert reloaded['ended_at'] == ended['ended_at']
        assert reloaded['active'] is False
        assert client.get(f"/api/room/{started['room_slug']}").json()['ended'] is True


def test_compose_persists_data_only_through_dataset_bind_mounts():
    lines = Path('docker-compose.yml').read_text().splitlines()
    assert not any(line.startswith('volumes:') for line in lines), 'top-level named volumes are Docker-managed'
    bind_targets = []
    for index, line in enumerate(lines):
        if line.strip() == '- type: bind':
            block = [item.strip() for item in lines[index + 1:index + 3]]
            bind_targets.append(next(item for item in block if item.startswith('target:')).split(':', 1)[1].strip())
    assert sorted(bind_targets) == ['/data/db', '/data/uploads']
    assert not any(':/data/' in line for line in lines), 'short-form volume entries could name Docker-managed volumes'
