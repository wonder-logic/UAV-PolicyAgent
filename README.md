# UAVGuard Policy Agent

UAVGuard Policy Agent is a production-oriented research platform for UAV mission policy review. It provides account registration, persistent operator profiles, drone profiles, mission drafting, a mission-specific conversational assistant, deterministic policy evaluation, citation-backed decision reports, and simulator grid packages.

The current implementation keeps the critical safety boundary explicit:

`Natural-language input -> structured extraction -> validation -> Knowledge Agent facts -> deterministic policy evaluation -> explanation generation`

The LLM layer can help extract and explain. It does not decide whether a mission is approved, denied, or needs review.

## Delivered Scope

- User registration, login, and session-backed authentication
- Persistent user policy profiles with certifications, authorizations, and waivers
- Multi-drone management with ownership checks
- Mission creation, editing, submission, history, and conversation history
- Mission chat that reuses stored profile and drone context
- Mock and HTTP-based Knowledge Agent adapters
- Deterministic policy engine with typed rule evaluations and citations
- Simulator policy package generation with per-cell status and traversal cost
- TAMU-CC-inspired static web UI served directly by FastAPI
- Alembic migration support, tests, linting, and type-checking

## Stack

- Python 3.12+
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x
- Alembic
- SQLite for local development, PostgreSQL-compatible `DATABASE_URL` support for production
- `httpx` for remote integration adapters
- `pytest`, `pytest-asyncio`, `ruff`, `mypy`
- Semantic HTML, CSS, and ES modules for the served frontend

## Project Layout

```text
policy_agent/
  api/             FastAPI routes and dependencies
  core/            domain exceptions, security, rate limiting
  db/              SQLAlchemy models and session/bootstrap
  integrations/    LLM and Knowledge Agent adapters
  policies/        retrieval facade, rules, engine, verification
  repositories/    database access layer
  schemas/         Pydantic contracts
  services/        profile, drone, mission, chat, evaluation services
  web/             static frontend served at /
alembic/           migrations
scripts/           local run helpers
tests/             backend tests
frontend-tests/    frontend helper tests
docs/              architecture notes
```

## Quick Start

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
py -3 -m pip install -e .[dev]
Copy-Item .env.example .env
py -3 -m alembic upgrade head
py -3 scripts/run_api.py
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

The FastAPI app serves both the backend and the frontend. There is no separate frontend dev server in this implementation.

## Configuration

Copy `.env.example` to `.env` and set the values appropriate for your environment.

Common settings:

- `DATABASE_URL`: production-style database connection string
- `POLICY_AGENT_DB_PATH`: local SQLite fallback path when `DATABASE_URL` is unset
- `KNOWLEDGE_AGENT_MODE`: `mock` or `remote`
- `KNOWLEDGE_AGENT_BASE_URL`: required when `KNOWLEDGE_AGENT_MODE=remote`
- `LLM_PROVIDER`: `mock` or `http`
- `LLM_BASE_URL`: required when `LLM_PROVIDER=http`
- `LLM_API_KEY`: optional for mock mode, required for secured HTTP providers
- `POLICY_STORE_PATH`: local trusted citation bundle path
- `CORS_ORIGINS`: comma-separated frontend origins

Startup validation fails fast when a required remote integration URL is missing.

## Run Checks

Backend tests:

```powershell
py -3 -m pytest -q
```

Frontend tests:

```powershell
node --test frontend-tests\app.test.mjs
```

Lint:

```powershell
py -3 -m ruff check .
```

Format check:

```powershell
py -3 -m ruff format --check .
```

Type check:

```powershell
py -3 -m mypy policy_agent
```

Migration check:

```powershell
py -3 -m alembic upgrade head
```

## Main Routes

Frontend and health:

- `GET /`
- `GET /health`

Platform API:

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/profiles`
- `GET /api/profiles/me`
- `PATCH /api/profiles/me`
- `POST /api/profiles/me/certifications`
- `PATCH /api/profiles/me/certifications/{credential_id}`
- `DELETE /api/profiles/me/certifications/{credential_id}`
- `POST /api/drones`
- `GET /api/drones`
- `GET /api/drones/{drone_id}`
- `PATCH /api/drones/{drone_id}`
- `DELETE /api/drones/{drone_id}`
- `POST /api/missions`
- `GET /api/missions`
- `GET /api/missions/{mission_id}`
- `PATCH /api/missions/{mission_id}`
- `POST /api/missions/{mission_id}/submit`
- `POST /api/missions/{mission_id}/evaluate`
- `GET /api/missions/{mission_id}/decision`
- `GET /api/missions/{mission_id}/simulator-package`
- `POST /api/missions/{mission_id}/chat`
- `GET /api/missions/{mission_id}/conversation`

Legacy PDP-style compatibility routes are still available under `/policy-agent/*`.

## End-to-End Flow

1. Register a user and sign in.
2. Create a policy profile.
3. Add at least one drone.
4. Record certifications or authorizations on the profile.
5. Create a mission draft.
6. Use the mission chat to fill in mission details.
7. Submit the mission.
8. Evaluate the mission against Knowledge Agent facts and deterministic rules.
9. Review the human-readable decision and simulator package.

## Architecture Notes

See [docs/ARCHITECTURE.md](/C:/Users/17372/Documents/Guard_policyAgent/docs/ARCHITECTURE.md) for the module boundaries, orchestration flow, persistence model, and known extension points.

## Known Limitations

- The default LLM and Knowledge Agent adapters are mocked for local development.
- The chat UI is non-streaming by design to keep the implementation stable.
- Geographic facts are only as strong as the configured Knowledge Agent response.
- The simulator package is generated locally as JSON; no external simulator push is implemented yet.
- FastAPI currently emits upstream deprecation warnings during tests on Python 3.14 because of `asyncio.iscoroutinefunction` usage inside FastAPI itself.

## Recommended Next Step

Replace the mock Knowledge Agent with a verified remote deployment and connect the policy retrieval layer to a production-grade policy store plus authoritative geographic context.
