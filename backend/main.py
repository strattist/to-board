from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.db.init import initialize_database
from backend.routers import games, room, sessions, settings
from backend.core.config import get_settings
from backend.services.rulebooks import retry_pending_cleanup

@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    retry_pending_cleanup(get_settings().uploads_path.resolve())
    yield

initialize_database()
app = FastAPI(title='to-board API', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])
app.include_router(games.router)
app.include_router(sessions.router)
app.include_router(room.router)
app.include_router(settings.router)

@app.get('/api/health')
def health(): return {'status': 'ok'}
