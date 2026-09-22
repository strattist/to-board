from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.db.init import initialize_database
from backend.routers import games, room, sessions, settings
from backend.core.config import get_settings
from backend.services.games import retry_pending_game_cleanup
from backend.services.rulebooks import retry_pending_cleanup

@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    retry_pending_cleanup(get_settings().uploads_path.resolve())
    retry_pending_game_cleanup(get_settings().uploads_path.resolve())
    yield

initialize_database()
app = FastAPI(title='to-board API', lifespan=lifespan)


def _redact_settings_validation(errors: list[dict]) -> list[dict]:
    redacted: list[dict] = []
    for raw_error in errors:
        error = dict(raw_error)
        location = tuple(error.get('loc', ()))
        input_value = error.get('input')
        if 'api_key' in location:
            error['input'] = '[redacted]'
        elif isinstance(input_value, dict) and 'api_key' in input_value:
            error['input'] = {**input_value, 'api_key': '[redacted]'}
        redacted.append(error)
    return redacted


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    if request.url.path == '/api/settings':
        errors = _redact_settings_validation(errors)
    return JSONResponse(status_code=422, content={'detail': jsonable_encoder(errors)})


app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])
app.include_router(games.router)
app.include_router(sessions.router)
app.include_router(room.router)
app.include_router(settings.router)

@app.get('/api/health')
def health(): return {'status': 'ok'}
