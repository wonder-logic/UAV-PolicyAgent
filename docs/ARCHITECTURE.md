# UAVGuard Policy Agent Architecture

## Overview

This repository implements the Policy Agent portion of the UAVGuard research platform. The system is intentionally conservative:

`mission chat -> typed mission update -> validated mission state -> Knowledge Agent facts -> deterministic policy rules -> decision aggregation -> explanation verification -> simulator package`

The safety-critical decision is produced by deterministic rules, not by the LLM.

## Main Boundaries

- `policy_agent/api`: HTTP routes, dependency wiring, CORS, error handling, request IDs
- `policy_agent/services`: business orchestration for auth, profiles, drones, missions, chat, and evaluation
- `policy_agent/repositories`: persistence access for user-owned resources
- `policy_agent/integrations`: mock and HTTP adapters for the LLM and Knowledge Agent
- `policy_agent/policies`: policy retrieval facade, trusted citations, deterministic rules, decision engine, explanation verification
- `policy_agent/db`: SQLAlchemy models and session/bootstrap helpers
- `policy_agent/web`: static research-platform UI served by FastAPI

## Persistence Model

The local schema is managed through Alembic and includes:

- `user_accounts`
- `auth_sessions`
- `user_policy_profiles`
- `profile_credentials`
- `drone_profiles`
- `missions`
- `mission_conversation_messages`
- `mission_evaluations`

Mission evaluations persist the Knowledge Agent request, Knowledge Agent response, rule evaluations, explanation payload, final decision payload, and simulator package payload. That keeps reevaluation traceable and supports idempotent mission evaluation.

## Orchestration Flow

### Auth and ownership

- Registration creates a user and a session token.
- Every profile, drone, mission, conversation, decision, and simulator package request is scoped to the authenticated user.

### Mission drafting

- The user creates a mission attached to one of their drones.
- The chat service loads the current mission state, profile, and drone context.
- The LLM provider returns a typed `MissionUpdateExtraction`.
- The service merges only non-null fields into the mission record.
- Missing mission fields are recalculated after each chat turn.

### Evaluation

1. Load the mission, profile, and selected drone.
2. Build a typed `KnowledgeAgentRequest`.
3. Fetch facts from the configured Knowledge Agent adapter.
4. Validate the Knowledge Agent response with Pydantic.
5. Run each deterministic rule independently.
6. Aggregate rule outcomes into `APPROVED`, `DENIED`, or `NEEDS_REVIEW`.
7. Build a simulator grid package from the same policy outcomes.
8. Generate a natural-language explanation from validated mission and decision data.
9. Verify that the explanation stays inside the trusted citation set.
10. Persist the decision and simulator package.

If the Knowledge Agent is unavailable, the evaluation falls back to `NEEDS_REVIEW` rather than fabricating facts.

## Deterministic Policy Engine

The engine ships with modular rules for:

- maximum altitude
- pilot certification presence and validity
- night operation readiness
- anti-collision lighting
- controlled airspace
- authorization validity
- operations over people
- operations over moving vehicles
- Remote ID
- visual line of sight
- waiver requirements

Each rule returns a typed `PolicyEvaluation` with applicability, severity, result, observed facts, required conditions, reason, and citations.

## LLM Guardrails

The LLM provider is allowed to:

- extract mission updates from natural-language chat
- identify uncertainty and missing fields
- produce a readable explanation after deterministic evaluation

The LLM provider is not allowed to:

- approve or deny a mission directly
- invent policy citations
- override deterministic rule results
- silently fill unknown safety-critical facts

The mock provider is heuristic and intentionally conservative. The HTTP provider is hidden behind a small interface so a structured-output provider can be swapped in without changing the service layer.

## Policy Retrieval and Citation Safety

The policy layer exposes a simple retrieval facade backed by trusted policy metadata and citations. The current implementation favors reliability over a large retrieval stack, but the interfaces are prepared for richer backends.

Every user-facing policy explanation is constrained to validated citations. Unsupported explanation text is replaced with the deterministic summary.

## Frontend

The frontend is a static ES module application served from `/` by FastAPI. It provides:

- sign-in and registration
- profile setup and credential management
- drone management
- mission drafting
- mission chat
- decision rendering
- simulator package viewing
- mission history

The interface uses a restrained TAMU-CC-inspired palette and keeps the backend and frontend deployable together without a separate build pipeline.

## Operational Notes

- SQLite is the default local database fallback.
- PostgreSQL can be used by setting `DATABASE_URL`.
- `database.create_all()` still runs on app startup for local convenience, but Alembic migrations are the intended production schema path.
- Rate limiting is applied to mission chat and evaluation endpoints.
- Request IDs are attached through middleware for easier tracing.

## Current Limitations

- The shipped Knowledge Agent and LLM integrations are local mocks by default.
- The simulator package is returned by the API but not pushed to an external simulator service.
- Chat responses are non-streaming.
- The local retrieval layer is intentionally lightweight and not yet backed by a production vector or search system by default.
