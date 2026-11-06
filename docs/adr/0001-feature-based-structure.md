# 0001. Organise code by feature, with a thin shared layer

- **Status:** accepted
- **Date:** 2026-11-06

## Context

The template started with a layer-based layout (`app/api/routes/`, `app/services/`, one `schemas.py`, one `models.py`; `src/pages/` on the frontend). Projects built from it are expected to grow large, with many features and several people or agents working at once. With layers, every feature change touches four or five folders, shared files (`schemas.py`, `models.py`) become merge-conflict hotspots, and it is hard to see what belongs to a feature.

## Decision

- Backend code lives in `app/features/<feature>/` (`router.py`, `schemas.py`, `models.py`, `service.py`, helpers). Shared infrastructure stays in `app/core`, `app/db`, `app/api`, `app/middleware`, `app/integrations`.
- Frontend code lives in `src/features/<feature>/`; shared UI in `src/components`, utilities in `src/lib`, the shell in `src/app`.
- Tests mirror features in `tests/<feature>/`.
- Explicit registries are the only places that list every feature: `app/db/models.py`, `app/api/router.py`, `app/features/rbac/registry.py`, `src/app/App.tsx`, `src/app/navigation.ts`.
- Dependency rules (in the `project-structure` skill): core/integrations never import features; services and integrations never import FastAPI; features never import another feature's router.

## Consequences

- A feature change is mostly confined to its folders; ownership and code review are clearer.
- Cross-feature model relationships need `TYPE_CHECKING` imports (SQLAlchemy resolves them by name), and every model module must be listed in `app/db/models.py` so Alembic sees it.
- New contributors must learn the dependency rules; `tests/test_route_guards.py` and code review enforce the most important ones.

## Alternatives considered

- **Keep the layer-based layout:** simple at first, but scales poorly (see Context).
- **Separate services/packages per domain (microservices or a monorepo of packages):** stronger isolation, but much more operational cost than the projects need; the feature layout can be split along the same boundaries later if required.
