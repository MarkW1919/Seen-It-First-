# Local Development Guide (without Jetson hardware)

This guide covers running the RepoScan Pro stack on a standard development machine — no NVIDIA Jetson, GPU, or physical camera required.

## Prerequisites

- **Docker & Docker Compose** v2+
- **Node.js** 20+ and npm
- **Python** 3.12+
- **Git**

## Quick Start

```bash
# 1. Clone and enter the repo
git clone <repo-url> && cd Seen-It-First-

# 2. Generate a .env with random secrets
./scripts/generate-env.sh

# 3. Start database + redis (the only services needed for local dev)
docker compose up -d db redis

# 4. Start the backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head            # run migrations
uvicorn app.main:app --reload   # http://localhost:8000

# 5. Start the frontend (new terminal)
cd frontend
npm install --legacy-peer-deps
npm run dev                     # http://localhost:5173
```

## Running Without Docker

If you prefer a local PostgreSQL + PostGIS and Redis:

1. Install PostGIS: `brew install postgis` (macOS) or `apt install postgresql-16-postgis-3` (Ubuntu)
2. Create the database: `createdb reposcan`
3. Enable PostGIS: `psql reposcan -c "CREATE EXTENSION postgis;"`
4. Update `.env` with `POSTGRES_HOST=localhost`
5. Install Redis: `brew install redis` or `apt install redis-server`

## Demo Mode (no backend needed)

The frontend has a built-in demo mode that works without any backend services:

1. `cd frontend && npm run dev`
2. Open http://localhost:5173
3. Click **"Enter Demo Mode"** on the login screen

This provides mock data for all views: live scan feed, alerts, map, search, hot list management, and settings.

## Running Tests

### Frontend
```bash
cd frontend
npm test              # run once
npm run test:watch    # watch mode
npm run test:coverage # with coverage
```

### Backend
```bash
cd backend
pip install -r requirements-dev.txt
pytest -v
```

### Linting
```bash
# Frontend
cd frontend && npx eslint .

# Backend (from repo root)
ruff check backend/ ai/ camera/
ruff format --check backend/ ai/ camera/
```

## Project Structure

```
├── frontend/       React + TypeScript + Vite PWA
├── backend/        FastAPI + SQLAlchemy + async PostgreSQL
├── ai/             YOLOv8 + CRNN inference pipeline
├── camera/         GStreamer camera service
├── deploy/         Nginx, Prometheus, Grafana, systemd
├── docs/           Documentation
├── scripts/        Helper scripts
└── tests/          Integration / E2E tests
```

## AI Pipeline (CPU-only development)

The AI pipeline is designed for Jetson GPU but can run in CPU mode for development:

1. Set `AI_DEVICE=cpu` in your `.env`
2. Run `cd ai && pip install -r requirements.txt`
3. Download model stubs: `./download_models.sh`
4. The pipeline reads frames from Redis pub/sub — in dev you can push test frames manually

## Useful Endpoints

| URL | Description |
|-----|-------------|
| http://localhost:5173 | Frontend (Vite dev server) |
| http://localhost:8000 | Backend API |
| http://localhost:8000/docs | Swagger/OpenAPI docs |
| http://localhost:8000/health | Health check |
| http://localhost:9090 | Prometheus (if running full stack) |
| http://localhost:3000 | Grafana (if running full stack) |
