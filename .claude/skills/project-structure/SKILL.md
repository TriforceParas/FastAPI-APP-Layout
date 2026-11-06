---
name: project-structure
description: Directory layout and module boundaries for this FastAPI + React template, built to scale to a large codebase. Load before creating any new file, folder, feature, router, model, service, integration, page or component, before moving code, or when unsure where something belongs or what may import what.
---

# Project Structure

The codebase is organised **by feature** (vertical slices), with a thin shared layer underneath. A feature owns its API routes, schemas, models, business logic, frontend page and tests, so a change to "orders" touches the `orders` folders and little else. This keeps a large project navigable and cuts merge conflicts between teams.

## 1. Top level

```
.
├── main.py                 # entry point: builds the UI if stale, runs uvicorn; exports `app`
├── app/                    # backend (Python package)
├── frontend/               # React + Vite source; compiled to frontend/dist and served by FastAPI
├── tests/                  # backend tests, mirrored by feature
├── migrations/             # Alembic (see db-migrations)
├── docs/                   # architecture decisions and long-form docs (see documentation)
├── .claude/skills/         # agent skills (this file and the others)
├── .github/workflows/      # CI + deploy
├── Dockerfile  alembic.ini  pyproject.toml  requirements*.in/.txt  .env.example
└── AGENTS.md  CLAUDE.md  README.md
```

## 2. Backend: `app/`

```
app/
├── main.py                 # create_app(): middleware, error handlers, routers, SPA
├── core/                   # cross-cutting, feature-agnostic building blocks
│   ├── config.py           #   Settings (env vars); production safety checks
│   ├── errors.py           #   AppError hierarchy (NotFound, Conflict, …)
│   ├── logging.py          #   text/JSON logging, request-id filter
│   ├── security.py         #   password hashing + policy, tokens, HMAC
│   ├── crypto.py  totp.py  #   encryption at rest, RFC 6238 codes
│   ├── rate_limit.py       #   rate_limit(...) dependency
│   ├── request_info.py     #   client IP / user agent helpers
│   └── auth_mode.py        #   dev-only auth bypass guard
├── db/
│   ├── base.py             # Base (naming convention), UTCDateTime, utcnow, new_id
│   ├── models.py           # REGISTRY: imports every feature's models (Alembic, tests)
│   ├── session.py          # engine + get_db / new_session
│   └── migrate.py          # alembic upgrade head on startup
├── api/
│   ├── deps.py             # Principal, require_user / require_screen, DbSession
│   ├── schemas.py          # shared schema pieces: Strict, Name, Email, Password, Message, LookupItem
│   └── router.py           # REGISTRY: includes every feature router under /api
├── middleware/             # pure-ASGI: request id, access log, security headers, CSRF, body limit, host check
├── integrations/           # clients for external systems (no FastAPI imports)
│   ├── mail.py             #   console / Microsoft Graph email + templates
│   └── turnstile.py        #   Cloudflare Turnstile verification
├── web/spa.py              # serves frontend/dist with SPA fallback
└── features/
    └── <feature>/          # one package per business capability
        ├── router.py       #   HTTP layer: APIRouter, guards, request/response mapping
        ├── schemas.py      #   Pydantic request/response models
        ├── models.py       #   SQLAlchemy models (tables owned by this feature)
        ├── service.py      #   business logic (optional: add when the router gets heavy)
        └── *.py            #   feature-specific helpers (e.g. auth/sessions.py, rbac/registry.py)
```

Existing features: `auth` (sign-in, setup, reset, sessions), `account` (/api/me), `mfa`, `users`, `rbac` (roles, screens, permissions; `registry.py` lists pages and features), `lookups`, `audit`, `dashboard`, `system` (health, system flags).

### Growing a feature

Start with `router.py` + `schemas.py` (+ `models.py`). When a file passes ~400 lines or mixes concerns, split it **inside the feature**:

```
features/orders/
├── router.py               # or routers/{orders.py, items.py, exports.py} when it grows
├── schemas.py              # or schemas/{order.py, item.py}
├── models.py
├── service.py              # or services/{pricing.py, fulfilment.py}
├── repository.py           # optional: complex queries reused by several services
├── tasks.py                # optional: background jobs
└── events.py               # optional: audit/notification helpers
```

Very large domains may group features (`features/sales/orders`, `features/sales/quotations`); keep the same inner layout.

## 3. Dependency rules (what may import what)

```
main.py → app.main → api/router → features/* → (api/deps, api/schemas, core, db, integrations)
middleware → core
integrations → core
core → (nothing in app except core)
db/base → (nothing in app)
```

1. **`core/`, `db/base.py`, `integrations/` never import from `features/` or `api/`.** They are reusable infrastructure.
2. **`integrations/` and `service.py` modules never import FastAPI.** Raise `app.core.errors` exceptions; only routers and `api/deps.py` know about HTTP.
3. **A feature may import another feature's `models`, `schemas` and `service`, never its `router`.** Shared helpers belong in the owning feature's `schemas.py`/`service.py` (e.g. `users.schemas.user_out`) or in `core/`.
4. **No import cycles.** Model-to-model references across features use `if TYPE_CHECKING:` imports; SQLAlchemy resolves relationships by class name.
5. **Registries are the only places that know every feature:** `app/db/models.py`, `app/api/router.py`, `app/features/rbac/registry.py`, `frontend/src/app/App.tsx`, `frontend/src/app/navigation.ts`.

## 4. Frontend: `frontend/src/`

```
src/
├── main.tsx                # mounts <App />
├── app/                    # application shell
│   ├── App.tsx             #   providers, AuthGate, routes (REGISTRY)
│   ├── navigation.ts       #   sidebar + ⌘K entries (REGISTRY, keys match rbac/registry.py)
│   └── status-pages.tsx    #   404 / forbidden
├── components/
│   ├── ui/                 # design system: import from "@/components/ui" only
│   └── layout/             # AppShell, Sidebar, Topbar, PageHeader, ThemeToggle
├── lib/                    # framework-level utilities, no feature knowledge
│   ├── api.ts              #   fetch wrapper (CSRF, errors, request ids)
│   ├── types.ts            #   types shared by several features (User, AuthStatus, Page, LookupItem…)
│   ├── use-resource.ts  lookups.ts  format.ts
├── features/
│   └── <feature>/
│       ├── <feature>-page.tsx   # route component(s)
│       ├── components/          # components used only by this feature
│       ├── types.ts             # types for this feature's API
│       ├── api.ts               # optional: typed API calls used by several components
│       └── hooks.ts             # optional: feature hooks
└── styles/globals.css
```

Frontend rules: `components/` and `lib/` never import from `features/`. A feature may import another feature's `types.ts` and the auth context (`@/features/auth/auth-context`), nothing else. Always import through the `@/` alias. Details in `frontend-conventions`.

## 5. Tests: `tests/`

```
tests/
├── conftest.py             # app fixture, Client, make_user / make_role helpers
├── <feature>/test_*.py     # mirrors app/features/<feature>
└── platform/               # cross-cutting: security headers, route guards, naming, logging, mail
```

One test module per behaviour area (`test_login.py`, `test_lockout.py`), not per source file.

## 6. Naming

| Thing | Convention | Example |
|---|---|---|
| Feature package (backend) | singular or domain noun, snake_case | `features/purchase_orders/` |
| Feature folder (frontend) | kebab-case | `features/purchase-orders/` |
| Python modules | snake_case | `service.py`, `setup_token.py` |
| TS/TSX files | kebab-case | `users-page.tsx`, `role-picker.tsx` |
| React components | PascalCase | `RolePicker` |
| Tables | category prefix (db-naming-conventions) | `txn_purchase_order` |
| URLs / screen keys | api-conventions | `/api/purchase-orders`, `purchase_orders` |

## 7. Adding a feature (checklist)

1. `app/features/<name>/` with `__init__.py`, `router.py`, `schemas.py` (+ `models.py`, `service.py`).
2. Models: import them in `app/db/models.py`; migration per db-migrations.
3. Router: include it in `app/api/router.py`; permissions in `app/features/rbac/registry.py`.
4. Tests in `tests/<name>/`.
5. Frontend: `src/features/<name>/<name>-page.tsx` (+ `types.ts`), route in `src/app/App.tsx`, entry in `src/app/navigation.ts`.
6. If the change is a notable design decision, add an ADR (documentation skill).

## 8. What does not belong in the repo

Generated or local files stay out of git (`.gitignore`): `frontend/dist`, `node_modules`, `.venv`, `data/`, `.env`, `.auth-bypass`, caches. Never commit build output, databases, secrets or editor folders.
