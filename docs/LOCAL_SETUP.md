# Local Setup

The canonical setup is summarized in the root README and demonstrated in
[DEMO_GUIDE.md](DEMO_GUIDE.md). All paths below are project-relative.

## Docker

Prerequisites: Docker Desktop/Compose and an OpenAI Platform API key.

```powershell
cd <project-root>
$env:OPENAI_API_KEY="<runtime-secret>"
docker compose up --build
```

The Compose startup runs Alembic migrations, idempotent demo seeding, FastAPI with its
in-process scheduler, and the React production build.

Endpoints:

- Frontend: `http://localhost:3000`
- API: `http://localhost:8000`
- OpenAPI: `http://localhost:8000/api/docs`
- Liveness: `http://localhost:8000/health`
- Readiness: `http://localhost:8000/ready`

Stop without deleting data:

```powershell
docker compose down
```

Delete all local database data:

```powershell
docker compose down -v
```

## Native Backend

Prerequisites: Python 3.11+, PostgreSQL 15+ with pgvector, and an OpenAI key.

```powershell
cd <project-root>\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set secure values in `.env`, especially `DATABASE_URL`, `SECRET_KEY`,
`JWT_SECRET_KEY`, and `OPENAI_API_KEY`.

```powershell
alembic -c alembic\alembic.ini upgrade head
python scripts\seed_db.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

APScheduler runs in the API lifespan. There is no separate worker command.

## Native Frontend

```powershell
cd <project-root>\frontend
npm ci
$env:VITE_API_URL="http://localhost:8000/api/v1"
npm run dev
```

## Validation

```powershell
cd <project-root>\backend
python -m ruff check app tests
python -m compileall -q app tests
python -m pytest -q

cd <project-root>\frontend
npm run type-check
npm test
npm run build

cd <project-root>
$env:OPENAI_API_KEY="compose-validation-placeholder"
docker compose config --quiet
```

Do not commit `.env`, tokens, employee exports, or production URLs.
