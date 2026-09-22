# to-board

to-board is a self-hosted board-game-night companion. It provides a Host interface for managing games and sessions, and a shareable Guest Room for reading published game content.

## Run the example stack

### Prerequisites

- Docker Engine with the Compose plugin
- A machine that can store the database and uploaded rulebooks

### 1. Prepare local data directories

The Compose file uses bind mounts so data survives container rebuilds. For a local example, create directories in the project folder:

```bash
mkdir -p data/db data/uploads
```

### 2. Create the environment file

```bash
cp .env.example .env
```

For a local, unauthenticated example, edit `.env` to use:

```dotenv
SECRET_KEY=replace-with-a-long-random-value
AUTH_DISABLED=true
APP_BASE_URL=http://localhost
TO_BOARD_DB_DATASET=./data/db
TO_BOARD_UPLOADS_DATASET=./data/uploads
```

Generate a suitable secret instead of using the example value:

```bash
openssl rand -hex 32
```

Set the output as `SECRET_KEY` in `.env`. `AUTH_DISABLED=true` is for local development only. In a deployed instance, set it to `false` and configure `AUTHENTIK_ISSUER`.

### Provider model overrides

The API uses `ANTHROPIC_MODEL` and `GOOGLE_MODEL` at runtime. The defaults are
`claude-haiku-4-5-20251001` and `gemini-2.0-flash`; set either variable in the
host `.env` to change the model, then recreate the API container:

```dotenv
ANTHROPIC_MODEL=claude-haiku-4-5-20251001
GOOGLE_MODEL=gemini-2.0-flash
```

Model IDs are provider configuration, not application data. Use the provider's
official model catalog or console to choose an ID; do not put API keys in model
URLs, `.env` examples, logs, or frontend code. Anthropic's current lifecycle
and replacement guidance is available in its [model deprecations
documentation](https://docs.anthropic.com/en/docs/about-claude/model-deprecations).

To list the Anthropic model IDs enabled for your key, enter it without putting
the secret in shell history, then call the Models API:

```bash
read -r -s -p 'Anthropic API key: ' ANTHROPIC_API_KEY; printf '\n'; export ANTHROPIC_API_KEY
curl -fsS https://api.anthropic.com/v1/models \
  -H "x-api-key: ${ANTHROPIC_API_KEY}" \
  -H 'anthropic-version: 2023-06-01' \
  | jq -r '.data[] | [.id, .display_name] | @tsv'
```

Do not paste the key into shell history, logs, or support requests. Anthropic
documents that `GET /v1/models` returns the models available to the API key in
its [List Models reference](https://docs.anthropic.com/en/api/models-list).

### 3. Build and start the server

From the repository root:

```bash
docker compose up --build
```

The first build installs the backend and frontend dependencies and may take a few minutes. Leave this command running. To start the stack in the background instead:

```bash
docker compose up --build -d
```

Check that the API is responding:

```bash
curl http://localhost/api/health
```

Expected response:

```json
{"status":"ok"}
```

View logs or stop the stack with:

```bash
docker compose logs -f
docker compose down
```

## Connect to the server

### Host interface

Open the following URL in a browser on the server machine:

<http://localhost/>

With local authentication disabled, the Host interface is immediately available. Use it to create a game, upload a PDF rulebook, generate or add content, publish that content, and start a session.

### Guest Room

After starting a session, to-board displays a room slug. Guests connect by opening:

```text
http://<server-hostname-or-ip>/room/<room-slug>
```

For example:

```text
http://192.168.1.20/room/abc123
```

Guest Room routes do not require Host authentication. Share the URL or the QR code shown by the Host interface with players on the same LAN.

### Connect from another device on the LAN

Find the server's LAN address, then set the public URL in `.env` before starting the stack:

```dotenv
APP_BASE_URL=http://192.168.1.20
```

Replace `192.168.1.20` with the server's actual address. Other devices can then open `http://192.168.1.20/`. Ensure the server firewall allows TCP port 80.

## Local development without the frontend container

The backend and frontend can also be run separately during development.

Start the backend from the repository root:

```bash
export SECRET_KEY="$(openssl rand -hex 32)"
export AUTH_DISABLED=true
export DB_PATH="$PWD/data/db/to-board.db"
export UPLOADS_PATH="$PWD/data/uploads"
mkdir -p data/db data/uploads
.venv/bin/uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

In a second terminal, start the frontend:

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

Open the Vite URL printed in the terminal, normally <http://localhost:5173/>. The Vite configuration proxies `/api` requests to the backend at `http://localhost:8000`.

## Production notes

- Keep `AUTH_DISABLED=false` outside local development and configure Authentik OIDC with `AUTHENTIK_ISSUER`.
- Use named host datasets for `TO_BOARD_DB_DATASET` and `TO_BOARD_UPLOADS_DATASET`; do not rely on Docker-managed volumes for persistent data.
- Keep Guest Room access restricted to the intended LAN or reverse-proxy network.
- Do not commit `.env`; it contains deployment secrets and configuration.
