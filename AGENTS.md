# AGENTS.md — rules for AI coding agents (and humans)

Full-stack template: **FastAPI** backend + **React (Vite, Tailwind v4)** UI. The UI is compiled to static
files and served by FastAPI. **There is no Node server at runtime.** Read this file before changing anything,
then load the skill for your task.

## Skills (`.claude/skills/<name>/SKILL.md`)

| Skill | Load before |
|---|---|
| `project-structure` | creating files/folders/features, moving code, deciding what may import what |
| `api-conventions` | endpoints, schemas, query params, status codes, error shapes, frontend API calls |
| `fastapi-security` | auth, permissions, input, data access, files, outbound calls, secrets, Docker, deploy |
| `error-handling-logging` | raising/catching errors, log statements, audit events, frontend error display |
| `observability` | health checks, middleware, logging setup, alerts, production debugging |
| `frontend-conventions` | anything under `frontend/src` |
| `db-naming-conventions` | creating or renaming tables, columns, indexes, constraints |
| `db-migrations` | model changes, anything in `migrations/`, deploying schema changes |
| `documentation` | README/AGENTS/skills/ADRs, docstrings, `.env.example` |
| `code-review` | reviewing a diff, or checking your own work before saying it's done |
| `fullstack-app` | starting a new project from this template |

Agents that cannot load skills automatically should open the file directly.

## Run / verify

```bash
python main.py --dev          # http://127.0.0.1:8000 — API + UI, auto-reload + UI rebuild on save
pytest                        # backend tests (must pass)
ruff check app tests main.py migrations .claude && ruff format app tests main.py migrations .claude
cd frontend && npm run build  # typecheck + build (must pass)
alembic check                 # models and migrations agree
```

Never add a Vite dev server, proxy, SSR or any Node runtime dependency.

## Layout (details: `project-structure`)

```
app/
  main.py          create_app(): middleware, error handlers, routers, SPA
  core/            config, errors, logging, security, crypto, totp, rate limiting (feature-agnostic)
  db/              base.py (Base, UTCDateTime), models.py (registry of all models), session, migrate
  api/             deps.py (require_user / require_screen), schemas.py (shared pieces), router.py (registry)
  middleware/      request id, access log, security headers, CSRF, body limit, host validation
  integrations/    mail.py (console / Microsoft Graph), turnstile.py — no FastAPI imports
  features/<name>/ router.py, schemas.py, models.py, service.py, helpers
                   auth, account, mfa, users, rbac (registry.py = pages + features), lookups, audit, dashboard, system
frontend/src/
  app/             App.tsx (routes), navigation.ts (sidebar), status pages
  components/      ui/ (design system, "@/components/ui"), layout/
  lib/             api.ts, types.ts (shared), use-resource.ts, lookups.ts, format.ts
  features/<name>/ <name>-page.tsx, components/, types.ts
tests/<feature>/   mirrors app/features; tests/platform/ for cross-cutting checks
docs/adr/          architecture decision records
```

## Adding a feature (short version; see the skills)

**Backend:** `app/features/<name>/` → models (named per `db-naming-conventions`, registered in
`app/db/models.py`, migration per `db-migrations`) → `Strict` request schemas → `router.py` with
`Depends(require_screen("<name>"))` on reads and `write=True` on changes → include it in `app/api/router.py`
→ add the page (and features) to `app/features/rbac/registry.py` → `audit.record(...)` on security-relevant
changes → tests in `tests/<name>/` (403 without the page, Read-only can't write, IDOR returns 404).

**Frontend:** `src/features/<name>/<name>-page.tsx` + `types.ts` → `<Route>` in `src/app/App.tsx` wrapped in
`<RequireScreen screen="<name>">` → nav entry in `src/app/navigation.ts` with `screen: "<name>"` → gate write
actions with `useAuth().can("<name>", "write")`. Build only from `@/components/ui` (gallery at `/components`); list
pages use `DataTablePage` + `DataTable` (sticky header, Columns menu); dialogs are controlled with `open`.

## Non-negotiable rules

- Every API route has a guard; data-changing routes require Write. `tests/platform/test_route_guards.py` enforces it.
- Lookups by id check ownership and return 404 for records the user may not see.
- Request models inherit `Strict` with length limits; every route has a `response_model`.
- No string-built SQL; escape LIKE wildcards; lists are paginated with a server-side maximum.
- Services and integrations raise `app.core.errors` exceptions and never import FastAPI.
- Never put secrets, tokens, codes or passwords in responses or logs. Log through `logging` (every line carries the request id).
- Don't disable CSP/HSTS/CSRF/host validation, add CORS, or expose `/api/docs` in production.
- `AUTH_ENABLED=false` works only with the `.auth-bypass` file and a non-production `APP_ENV`. Never commit that file.
- A feature never imports another feature's router; `core/` and `integrations/` never import features.

## Built-in behaviour you must preserve

**RBAC.** `md_screen` is a tree of pages and their features, synced at startup from
`app/features/rbac/registry.py`. It works with `md_role`, `map_role_screen` (Read/Write per leaf; Write
implies Read, which is also a DB check) and `map_user_role` (ordered roles per user).
- Effective permissions are the union of a user's roles. A user lands on the first role's default page.
- The Administrator system role always has every permission and can't be edited.
- At least one active Administrator must always remain.
- No privilege escalation: users can only grant or manage access they hold themselves (`Permissions.covers`).
- Settings and `/api/me/*` are outside RBAC.

**Cloudflare Turnstile.** Protects login, setup and forgot-password.
- Tokens are verified server-side, bound to the form's `action` and our hostname, and verification fails closed.
- `.env.example` ships Cloudflare's test keys, which production refuses.

**Email, password reset, 2FA.**
- `MAIL_PROVIDER`: `console` (dev only), `microsoft` (Graph), or `disabled`. Send email with `background.add_task(send_safely, render(...))`.
- Forgot password always gives the same reply. Reset links are single-use, expiring and stored hashed. Resetting signs the user out everywhere but keeps 2FA.
- 2FA is optional per user (authenticator app or emailed code, plus 10 recovery codes). Wrong codes count toward the same lockout as wrong passwords. Admins can reset a user's 2FA.

**Sign in with Microsoft** (OIDC, `MICROSOFT_SSO_ENABLED`). Allowed tenant plus allowed email domains
(`MICROSOFT_SSO_ALLOWED_DOMAINS`). Users are linked by Entra tenant + object id in `md_user_identity`, never
re-matched by email, and app 2FA still applies. Rules: `fastapi-security` §1.

## Lookups: dropdown data from pages the user doesn't own

A user may be allowed to use page B (e.g. creating a task) without access to page A (employee details), yet
B needs a dropdown of A's records. Never grant access to A or call A's management endpoint: use a **lookup**.

- One lookup per entity: `GET /api/lookups/<entity>` in `app/features/lookups/router.py`.
- Return only `LookupItem` (`id`, `label`, at most one extra disambiguating field). Select only those columns, active records only, with `q` (≤100 chars) and `limit` (default 20, max 50).
- Register who may use it: `LOOKUPS = {"employees": ("tasks.create",)}` and guard with `require_lookup("employees")`. Only users with access to a consuming screen get data; everyone else gets 403.
- Frontend: `useLookup("employees", q)` from `src/lib/lookups.ts`.
- Tests for every lookup: exact fields; 403 without a consuming screen; 200 with only the consuming screen; inactive records excluded; `limit` capped. Reference: `GET /api/lookups/roles` and `tests/rbac/test_lookups.py`.
