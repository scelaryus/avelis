# Avelis — Agentic AI Financial & Operations Platform

## Architecture
- **Backend:** FastAPI + PostgreSQL + S3/MinIO
- **Agent Engine:** LangGraph-like orchestrator with typed artifacts
- **Frontend:** React SPA
- **Deployment:** VPS-centralized, no Docker

## Quick Start
```bash
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

## Project Structure
```
app/
├── main.py                 # FastAPI app entry
├── config.py               # Settings
├── database.py             # DB session
├── models/                 # SQLAlchemy ORM
├── schemas/                # Pydantic schemas (artifacts)
├── api/                    # API routers
├── agents/                 # Agent implementations
├── orchestrator/           # Workflow engine
├── services/               # Business logic
├── storage/                # Object storage
└── auth/                   # RBAC & auth
frontend/                   # React UI
tests/                      # Unit + golden tests
alembic/                    # Migrations
```
