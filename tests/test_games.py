from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4
import base64
import json

from tests.helpers import DATA, PDF, encoded_image, stored_cover_path
from backend.core.config import get_settings
from backend.db.engine import engine
from backend.main import app
from backend.models import Content, Game, GameSession, PipelineState, Rulebook
from backend.services import games as games_service
from fastapi.testclient import TestClient
from sqlmodel import Session, select


def test_game_creation_and_validation():
    with TestClient(app) as client:
        response = client.post('/api/games', json={'title': '  Wingspan  '})
        assert response.status_code == 201
        assert response.json()['title'] == 'Wingspan'
        assert response.json()['pipeline_state'] == 'no_rulebook'
        assert response.json()['provider_configured'] is False
        assert 'cover_image_path' not in response.json()
        assert 'api_key' not in response.json()
        assert client.post('/api/games', json={'title': '   '}).status_code == 422


def test_game_creation_with_cover_is_atomic():
    with TestClient(app) as client:
        image = encoded_image('PNG')
        created = client.post(
            '/api/games/with-cover',
            data={'title': '  Atomic cover  '},
            files={'file': ('cover.png', image, 'image/png')},
        )
        assert created.status_code == 201
        game = created.json()
        assert game['title'] == 'Atomic cover'
        assert 'cover_image_path' not in game
        assert stored_cover_path(game['id']).read_bytes() == image

        too_long = client.post(
            '/api/games/with-cover',
            data={'title': 'x' * 201},
            files={'file': ('cover.png', image, 'image/png')},
        )
        assert too_long.status_code == 422

        rejected = client.post(
            '/api/games/with-cover',
            data={'title': 'Should not persist'},
            files={'file': ('cover.png', b'not an image', 'image/png')},
        )
        assert rejected.status_code == 422
        assert [item['title'] for item in client.get('/api/games').json()] == ['Atomic cover']


def test_collection_metadata_and_cover_validation():
    with TestClient(app) as client:
        assert client.get('/api/games').json() == []
        created = client.post('/api/games', json={'title': '  Cover test  '})
        assert created.status_code == 201
        game = created.json()
        parsed_id = UUID(game['id'])
        assert parsed_id.version == 4
        assert game['title'] == 'Cover test'
        assert game['created_at'].endswith('+00:00')

        listing = client.get('/api/games')
        assert listing.status_code == 200
        assert any(item['id'] == game['id'] for item in listing.json())

        png = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
        )
        uploaded = client.post(
            f"/api/games/{game['id']}/cover",
            files={'file': ('cover.png', png, 'image/png')},
        )
        assert uploaded.status_code == 200
        cover = uploaded.json()
        assert 'cover_image_path' not in cover
        cover_path = stored_cover_path(game['id'])
        assert cover_path.is_file()
        assert cover_path.read_bytes() == png
        assert cover['cover_url'].startswith(f"/api/games/{game['id']}/cover/file?v=")
        assert client.get(cover['cover_url']).content == png

        invalid = client.post(
            f"/api/games/{game['id']}/cover",
            files={'file': ('replacement.png', b'not an image', 'image/png')},
        )
        assert invalid.status_code == 422
        assert cover_path.read_bytes() == png

        unsupported = client.post(
            f"/api/games/{game['id']}/cover",
            files={'file': ('replacement.gif', b'GIF89a', 'image/gif')},
        )
        assert unsupported.status_code == 422
        assert cover_path.read_bytes() == png

        oversized = client.post(
            f"/api/games/{game['id']}/cover",
            files={'file': ('oversized.png', b'x' * (10 * 1024 * 1024 + 1), 'image/png')},
        )
        assert oversized.status_code == 422
        assert cover_path.read_bytes() == png

        malformed = bytearray(png)
        malformed[29] ^= 0xFF
        invalid_crc = client.post(
            f"/api/games/{game['id']}/cover",
            files={'file': ('malformed.png', bytes(malformed), 'image/png')},
        )
        assert invalid_crc.status_code == 422
        assert cover_path.read_bytes() == png

        mismatched = client.post(
            f"/api/games/{game['id']}/cover",
            files={'file': ('mismatched.jpg', png, 'image/jpeg')},
        )
        assert mismatched.status_code == 422
        assert cover_path.read_bytes() == png

        for filename, image in [('cover.jpg', encoded_image('JPEG')), ('cover.webp', encoded_image('WEBP'))]:
            replacement = client.post(
                f"/api/games/{game['id']}/cover",
                files={'file': (filename, image, 'image/*')},
            )
            assert replacement.status_code == 200
            assert stored_cover_path(game['id']).read_bytes() == image


def test_game_management_requires_host():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Protected game'}).json()
        settings = get_settings()
        previous = settings.auth_disabled
        settings.auth_disabled = False
        try:
            assert client.get('/api/games').status_code == 401
            assert client.post('/api/games', json={'title': 'Should not exist'}).status_code == 401
            assert client.post(
                f"/api/games/{game['id']}/cover",
                files={'file': ('cover.png', b'not an image', 'image/png')},
            ).status_code == 401
            assert client.post(
                f"/api/games/{game['id']}/rulebook",
                files={'file': ('rules.pdf', PDF, 'application/pdf')},
            ).status_code == 401
        finally:
            settings.auth_disabled = previous


def test_game_deletion_removes_current_assets_and_preserves_session_history(monkeypatch):
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Delete safely'}).json()
        cover = client.post(
            f"/api/games/{game['id']}/cover",
            files={'file': ('cover.png', encoded_image('PNG'), 'image/png')},
        ).json()
        with Session(engine) as db:
            rulebook_path = DATA / 'uploads' / 'rulebooks' / game['id'] / 'rules.pdf'
            rulebook_path.parent.mkdir(parents=True, exist_ok=True)
            rulebook_path.write_bytes(b'%PDF-1.4 test')
            rulebook = Rulebook(id=str(uuid4()), game_id=game['id'], pdf_path=str(rulebook_path))
            extracted = DATA / 'uploads' / 'rulebooks' / game['id'] / 'rules.txt'
            extracted.write_text('extracted rules', encoding='utf-8')
            rulebook.extracted_text_path = str(extracted)
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.pipeline_state = PipelineState.published
            content.published_quickstart_md = '# Quick start'
            content.published_cheat_sheet_md = '- Cheat sheet'
            history = GameSession(
                id=str(uuid4()),
                game_id=game['id'],
                game_title_snapshot=game['title'],
                room_slug=f"delete-safely-{uuid4().hex[:4]}",
                ended_at=datetime.now(timezone.utc),
            )
            db.add_all([rulebook, content, history])
            db.commit()
            cover_path = stored_cover_path(game['id'])
            history_id = history.id

        response = client.delete(f"/api/games/{game['id']}")
        assert response.status_code == 204
        assert not rulebook_path.exists()
        assert not extracted.exists()
        assert not cover_path.exists()
        with Session(engine) as db:
            assert db.get(Game, game['id']) is None
            assert db.exec(select(Rulebook).where(Rulebook.game_id == game['id'])).first() is None
            assert db.exec(select(Content).where(Content.game_id == game['id'])).first() is None
            preserved = db.get(GameSession, history_id)
            assert preserved is not None
            assert preserved.game_title_snapshot == 'Delete safely'
        preserved_response = client.get(f'/api/sessions/{history_id}')
        assert preserved_response.status_code == 200
        assert preserved_response.json()['game_title_snapshot'] == 'Delete safely'
        assert all(item['id'] != game['id'] for item in client.get('/api/games').json())


def test_game_deletion_rejects_active_session_before_mutation():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Active session'}).json()
        with Session(engine) as db:
            content = db.exec(select(Content).where(Content.game_id == game['id'])).one()
            content.pipeline_state = PipelineState.published
            content.published_quickstart_md = '# Start'
            content.published_cheat_sheet_md = '- Rule'
            db.add(content)
            db.commit()
        started = client.post(f"/api/sessions?game_id={game['id']}")
        assert started.status_code == 201
        blocked = client.delete(f"/api/games/{game['id']}")
        assert blocked.status_code == 409
        assert client.get(f"/api/room/{started.json()['room_slug']}").status_code == 200
        with Session(engine) as db:
            assert db.get(Game, game['id']) is not None


def test_game_deletion_storage_failure_restores_assets_and_rows(monkeypatch):
    with TestClient(app, raise_server_exceptions=False) as client:
        game = client.post('/api/games', json={'title': 'Delete storage failure'}).json()
        cover = client.post(
            f"/api/games/{game['id']}/cover",
            files={'file': ('cover.png', encoded_image('PNG'), 'image/png')},
        ).json()
        cover_path = stored_cover_path(game['id'])
        original_replace = Path.replace

        def fail_staging(path: Path, destination: Path):
            if '.game-delete' in str(destination):
                raise OSError('simulated staging failure')
            return original_replace(path, destination)

        monkeypatch.setattr(Path, 'replace', fail_staging)
        response = client.delete(f"/api/games/{game['id']}")
        assert response.status_code == 500
        assert response.json()['detail']
        assert cover_path.exists()
        with Session(engine) as db:
            assert db.get(Game, game['id']) is not None


def test_game_deletion_partial_staging_failure_restores_all_assets(monkeypatch):
    with TestClient(app, raise_server_exceptions=False) as client:
        game = client.post('/api/games', json={'title': 'Delete partial staging'}).json()
        cover = client.post(
            f"/api/games/{game['id']}/cover",
            files={'file': ('cover.png', encoded_image('PNG'), 'image/png')},
        ).json()
        cover_path = stored_cover_path(game['id'])
        with Session(engine) as db:
            rulebook_path = DATA / 'uploads' / 'rulebooks' / game['id'] / 'rules.pdf'
            rulebook_path.parent.mkdir(parents=True, exist_ok=True)
            rulebook_path.write_bytes(b'current rulebook')
            db.add(Rulebook(id=str(uuid4()), game_id=game['id'], pdf_path=str(rulebook_path)))
            db.commit()
        original_replace = Path.replace
        failed = False

        def fail_cover_stage(path: Path, destination: Path):
            nonlocal failed
            if not failed and destination.name == cover_path.name and '.game-delete' in destination.parts:
                failed = True
                raise OSError('simulated partial staging failure')
            return original_replace(path, destination)

        monkeypatch.setattr(Path, 'replace', fail_cover_stage)
        response = client.delete(f"/api/games/{game['id']}")
        assert response.status_code == 500
        assert failed
        assert cover_path.exists()
        assert rulebook_path.exists()
        with Session(engine) as db:
            assert db.get(Game, game['id']) is not None


def test_game_deletion_post_commit_cleanup_is_journaled_and_retried(monkeypatch):
    with TestClient(app, raise_server_exceptions=False) as client:
        game = client.post('/api/games', json={'title': 'Delete cleanup journal'}).json()
        cover = client.post(
            f"/api/games/{game['id']}/cover",
            files={'file': ('cover.png', encoded_image('PNG'), 'image/png')},
        ).json()
        cover_path = stored_cover_path(game['id'])
        original_remove = games_service._remove_path

        def fail_tombstone_unlink(path: Path):
            if '.game-delete' in path.parts:
                return False
            return original_remove(path)

        monkeypatch.setattr(games_service, '_remove_path', fail_tombstone_unlink)
        response = client.delete(f"/api/games/{game['id']}")
        assert response.status_code == 500
        assert not cover_path.exists()
        uploads_root = DATA / 'uploads'
        journal = uploads_root / '.game-delete-cleanup.json'
        assert journal.is_file()
        pending = json.loads(journal.read_text(encoding='utf-8'))
        assert pending
        tombstone = uploads_root / pending[0]
        assert tombstone.is_file()

        monkeypatch.setattr(games_service, '_remove_path', original_remove)
        from backend.services.games import retry_pending_game_cleanup
        retry_pending_game_cleanup(uploads_root.resolve())
        assert not journal.exists()
        assert not tombstone.exists()


def test_game_deletion_rejects_persisted_path_outside_uploads(tmp_path):
    outside = tmp_path / 'outside.pdf'
    outside.write_bytes(b'keep this file')
    with TestClient(app, raise_server_exceptions=False) as client:
        game = client.post('/api/games', json={'title': 'Delete outside path'}).json()
        with Session(engine) as db:
            db.add(Rulebook(id=str(uuid4()), game_id=game['id'], pdf_path=str(outside)))
            db.commit()
        response = client.delete(f"/api/games/{game['id']}")
        assert response.status_code == 500
        assert outside.read_bytes() == b'keep this file'
        with Session(engine) as db:
            assert db.get(Game, game['id']) is not None


def test_game_deletion_database_failure_restores_assets_and_rows(monkeypatch):
    with TestClient(app, raise_server_exceptions=False) as client:
        game = client.post('/api/games', json={'title': 'Delete database failure'}).json()
        cover = client.post(
            f"/api/games/{game['id']}/cover",
            files={'file': ('cover.png', encoded_image('PNG'), 'image/png')},
        ).json()
        cover_path = stored_cover_path(game['id'])
        original_commit = Session.commit

        def fail_commit(self):
            raise RuntimeError('simulated database failure')

        monkeypatch.setattr('backend.services.games.Session.commit', fail_commit)
        response = client.delete(f"/api/games/{game['id']}")
        assert response.status_code == 500
        assert response.json()['detail']
        assert cover_path.exists()
        with Session(engine) as db:
            assert db.get(Game, game['id']) is not None
        monkeypatch.setattr(Session, 'commit', original_commit)


def test_game_deletion_database_failure_restores_all_assets(monkeypatch):
    with TestClient(app, raise_server_exceptions=False) as client:
        game = client.post('/api/games', json={'title': 'Delete all assets'}).json()
        cover = client.post(
            f"/api/games/{game['id']}/cover",
            files={'file': ('cover.png', encoded_image('PNG'), 'image/png')},
        ).json()
        cover_path = stored_cover_path(game['id'])
        with Session(engine) as db:
            rulebook_path = DATA / 'uploads' / 'rulebooks' / game['id'] / 'rules.pdf'
            extracted_path = DATA / 'uploads' / 'rulebooks' / game['id'] / 'rules.txt'
            rulebook_path.parent.mkdir(parents=True, exist_ok=True)
            rulebook_path.write_bytes(b'rules')
            extracted_path.write_text('rules text', encoding='utf-8')
            db.add(Rulebook(id=str(uuid4()), game_id=game['id'], pdf_path=str(rulebook_path), extracted_text_path=str(extracted_path)))
            db.commit()
        original_commit = Session.commit

        def fail_commit(self):
            raise RuntimeError('simulated database failure')

        monkeypatch.setattr('backend.services.games.Session.commit', fail_commit)
        response = client.delete(f"/api/games/{game['id']}")
        assert response.status_code == 500
        assert cover_path.exists()
        assert rulebook_path.exists()
        assert extracted_path.exists()
        with Session(engine) as db:
            assert db.get(Game, game['id']) is not None
            assert db.exec(select(Rulebook).where(Rulebook.game_id == game['id'])).first() is not None
        monkeypatch.setattr(Session, 'commit', original_commit)


def test_game_deletion_recovery_journal_replays_failed_restore(monkeypatch):
    with TestClient(app, raise_server_exceptions=False) as client:
        game = client.post('/api/games', json={'title': 'Delete recovery'}).json()
        cover = client.post(
            f"/api/games/{game['id']}/cover",
            files={'file': ('cover.png', encoded_image('PNG'), 'image/png')},
        ).json()
        cover_path = stored_cover_path(game['id'])
        original_replace = Path.replace
        original_commit = Session.commit

        def fail_commit(self):
            raise RuntimeError('simulated database failure')

        def fail_restore(path: Path, destination: Path):
            if destination == cover_path:
                raise OSError('simulated restore failure')
            return original_replace(path, destination)

        monkeypatch.setattr('backend.services.games.Session.commit', fail_commit)
        monkeypatch.setattr(Path, 'replace', fail_restore)
        response = client.delete(f"/api/games/{game['id']}")
        assert response.status_code == 500
        recovery = DATA / 'uploads' / '.game-delete-recovery.json'
        assert recovery.is_file()

        monkeypatch.setattr(Path, 'replace', original_replace)
        monkeypatch.setattr(Session, 'commit', original_commit)
        games_service.retry_pending_game_cleanup((DATA / 'uploads').resolve())
        assert not recovery.exists()
        assert cover_path.exists()


def test_game_cleanup_journal_is_replayed_during_startup():
    uploads_root = DATA / 'uploads'
    tombstone = uploads_root / '.game-delete' / 'startup-op' / 'covers' / 'startup.png'
    tombstone.parent.mkdir(parents=True, exist_ok=True)
    tombstone.write_bytes(b'pending cleanup')
    (uploads_root / '.game-delete-cleanup.json').write_text(
        json.dumps([str(tombstone.relative_to(uploads_root))]), encoding='utf-8'
    )
    with TestClient(app):
        pass
    assert not tombstone.exists()
    assert not (uploads_root / '.game-delete-cleanup.json').exists()


def test_game_deletion_requires_host_and_returns_not_found():
    with TestClient(app) as client:
        assert client.delete('/api/games/unknown-game').status_code == 404
        game = client.post('/api/games', json={'title': 'Protected deletion'}).json()
        settings = get_settings()
        previous = settings.auth_disabled
        settings.auth_disabled = False
        try:
            assert client.delete(f"/api/games/{game['id']}").status_code == 401
            with Session(engine) as db:
                assert db.get(Game, game['id']) is not None
        finally:
            settings.auth_disabled = previous


def test_missing_cover_file_returns_not_found():
    with TestClient(app) as client:
        game = client.post('/api/games', json={'title': 'Missing cover'}).json()
        image = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
        )
        uploaded = client.post(f"/api/games/{game['id']}/cover", files={'file': ('cover.png', image, 'image/png')})
        assert uploaded.status_code == 200
        original_cover_path = stored_cover_path(game['id'])
        original_cover_path.unlink()
        assert client.get(uploaded.json()['cover_url']).status_code == 404


def test_cover_filesystem_failure_restores_previous_cover(monkeypatch):
    with TestClient(app, raise_server_exceptions=False) as client:
        game = client.post('/api/games', json={'title': 'Cover rollback'}).json()
        original = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
        )
        uploaded = client.post(f"/api/games/{game['id']}/cover", files={'file': ('cover.png', original, 'image/png')})
        assert uploaded.status_code == 200
        original_cover_path = stored_cover_path(game['id'])
        original_replace = Path.replace

        def fail_temporary_replace(path: Path, destination: Path):
            if path.name.endswith('.tmp'):
                raise OSError('simulated filesystem failure')
            return original_replace(path, destination)

        monkeypatch.setattr(Path, 'replace', fail_temporary_replace)
        failed = client.post(f"/api/games/{game['id']}/cover", files={'file': ('replacement.jpg', encoded_image('JPEG'), 'image/jpeg')})
        assert failed.status_code == 500
        assert original_cover_path.read_bytes() == original
        restored = client.get(f"/api/games/{game['id']}")
        assert restored.status_code == 200
        assert stored_cover_path(game['id']) == original_cover_path
        assert client.get(restored.json()['cover_url']).content == original
