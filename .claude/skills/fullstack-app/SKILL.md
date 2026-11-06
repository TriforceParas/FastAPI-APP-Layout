---
name: fullstack-app
description: Scaffold and extend the user's standard full-stack app, a FastAPI backend that serves a compiled React/Vite/Tailwind UI with no Node server at runtime. It ships with login, first-run admin registration, user management, an audit log, a dashboard, OWASP hardening and Docker/GitHub Actions deploys to a VPS. Use when the user wants to start a new project, app, dashboard, admin panel or internal tool, or "my usual stack/layout". Also use when they want to add a page, endpoint, model or feature to a project built from it (it has AGENTS.md, main.py, app/ and frontend/src/components/ui).
---

# Full-stack app (FastAPI + static React)

The user builds every project on the same base: FastAPI serves `/api/*` **and** the
compiled UI from `frontend/dist`. Node is only used to *build* the UI (locally or in the
Docker build stage). Never add a Vite dev server, SSR, a proxy or any Node runtime.

**The template is this repository** (the skill lives at `.claude/skills/fullstack-app/`
inside it). Its `AGENTS.md` is the full convention guide; read it before editing a project.
New projects get a copy of this skill too, so agents working in them follow the same rules.

Companion skills in this repo: `api-conventions` (endpoints and schemas), `fastapi-security`
(mandatory security rules and known gaps), `db-naming-conventions` (table names) and
`db-migrations` (Alembic workflow). Load the relevant one before working in that area.

## 1. New project

1. Get a **product name**, and optionally a tagline and a target directory. Ask only for the name if it's missing.
   Use `--service` for the server folder / compose service name (defaults to a slug of the name).
2. Scaffold. This copies the template, personalises it, installs deps, builds the UI and runs the tests:
   ```bash
   python3 <template-repo>/.claude/skills/fullstack-app/scripts/new_project.py <dest> --name "Acme Ops" --tagline "Field operations"
   ```
   `<template-repo>` is the root of this repository; from inside it, the path is just `.claude/skills/...`.
   Add `--no-install` to only copy the files. The script refuses to write into a non-empty directory
   and skips `.git`, `node_modules`, `dist`, `data`, `.env` and `.auth-bypass`.
3. Start it with `<venv>/bin/python main.py --dev` (the script prints the venv path) and open
   http://127.0.0.1:8000. The first visit shows **initial registration**.
4. Then build the requested features (section 2). Remove nothing from auth or security.

## 2. Adding features to a project

Read the project's `AGENTS.md` first. In short:

**Backend** (layout and import rules: `project-structure`): `app/features/<feature>/` → models in its
`models.py` (names per `db-naming-conventions`; register the module in `app/db/models.py`) →
`alembic revision --autogenerate -m "..."` and review it (`db-migrations`) → `Strict` request schemas in its
`schemas.py` → page/feature entries in `app/features/rbac/registry.py` → `router.py` guarded with
`require_screen("<key>")` / `require_screen("<key>", write=True)`, included in `app/api/router.py` →
`audit.record(...)` on security-relevant writes → tests in `tests/<feature>/` using the `admin_client` /
`make_role` / `make_user` fixtures.

**Frontend** (`frontend-conventions`): `src/features/<feature>/<feature>-page.tsx` + `types.ts`, starting with
`<PageHeader>`, data via `useResource(() => api.get(...), [deps])`, mutations via `api.post/patch/delete` +
`useToast()` → `<Route>` in `src/app/App.tsx` wrapped in `<RequireScreen screen="<key>">` → nav entry in
`src/app/navigation.ts`.

**Dropdowns that need another page's data** (e.g. an "assignee" list on a task form when the user has no
access to Employees): use a **lookup** (`GET /api/lookups/<entity>`), never the management endpoint and never
by widening the user's permissions. A lookup returns only `id` + `label` (plus at most one disambiguating
field) through its own minimal Pydantic model, is read-only, active-only and paginated, and is allowed only
for users who hold Read/Write on a screen registered as a consumer of that lookup. Every lookup needs tests
for: exact fields, 403 without a consumer screen, 200 with only the consumer screen. Full rules are in
`AGENTS.md` ("Lookups").

**UI rules:**
- Compose only from `@/components/ui` (see the live gallery at `/components`).
- If a component is missing, add a reusable one to `components/ui/` and export it from `index.ts`, so it also appears in the gallery.
- Reuse the existing colour classes (`bg-[#1b1b1b]`, `border-white/[0.09]`, `text-[#888]`, emerald accent). Light mode remaps those exact classes in `globals.css`, so new hex values break it.
- The CSP is strict: no inline `<script>`, no HTML `style=` attributes, no CDNs or web fonts. React's `style={{}}` prop is fine.

**Security (do not weaken):** auth on every non-public route; ownership checks with a 404
for other users' objects; no secrets in responses or logs; length limits on every field;
SQLAlchemy expressions only (escape LIKE wildcards); keep the CSRF, CSP, HSTS and host
validation middleware; no CORS; `/api/docs` stays off in production.

## 3. Verify before saying it's done

```bash
<venv>/bin/python -m pytest -q && <venv>/bin/ruff check app tests main.py migrations
cd frontend && npm run build          # tsc + vite; must be clean
```

For UI work, check it in a real browser. Run the app (`main.py --port 8765 --skip-build`),
then drive Google Chrome headless with `playwright-core` (`channel: "chrome"`). Sign in,
visit the changed pages, take screenshots and **read them**, and collect console errors.
Any CSP violation shows up there. Check both dark mode and light mode
(`localStorage.app_theme = "light"`).

## 4. Auth bypass (local dev only)

It needs `AUTH_ENABLED=false` **and** a `.auth-bypass` file **and** an `APP_ENV` other than production.
`rm .auth-bypass` re-enables auth instantly. Never commit, copy or deploy that file.

## 5. Deploy

This follows the user's ISO-DMS pattern. `test-deploy.yml` runs on push to main (tests, then SSH
`git pull` + `docker compose up -d --build <service>` in `/opt/app/test`). `prod-deploy.yml` is
manual. Both use the `VPS_HOST`, `VPS_USERNAME` and `VPS_PASSWORD` secrets. A production `.env` needs
`APP_ENV=production`, a 32+ character `SECRET_KEY`, `ALLOWED_HOSTS` and `https://` `ALLOWED_ORIGINS`.
The first admin is created with the setup token from `docker compose logs <service>`.

## Gotchas

- **Email**: `MAIL_PROVIDER=console` prints mails (reset links, codes) to the server log, which is how you test
  forgot-password and email 2FA locally. Use `microsoft` (Graph) or `disabled` in production.

- **Turnstile**: `.env` ships Cloudflare's TEST keys (widget always passes). Production refuses to start with
  them, so set real `TURNSTILE_SITE_KEY` / `TURNSTILE_SECRET_KEY` before deploying. Tests force it off.
- **RBAC**: never check roles by name in code. Check permissions with `require_screen(key)` (API) and
  `can(key)` (UI). A new page is invisible to every role except Administrator until it is granted on the Roles page.

- **NTFS/exFAT** (e.g. `/media/.../New Volume`) can't hold symlinks, so `.venv` fails there. Use
  `~/.venvs/<slug>` (the scaffold script does this automatically). `frontend/.npmrc` sets
  `bin-links=false`, and the npm scripts call `node ./node_modules/...` directly. Keep it that way.
- `main.py` rebuilds the UI only when the sources are newer than `dist/index.html`. Use `--rebuild` to force it.
- New dependencies: add them to `requirements.in`, then
  `uv pip compile requirements.in -o requirements.txt` (and the same for the `-dev` files).
- If `Field` wraps a non-input element, pass `htmlFor` and set the `id` on the inner input yourself.
  For password + strength meter, use `<PasswordInput showStrength />`.

## Improving the template

Changes made to this repository are used by the next scaffold automatically, since there's no
separate copy. Push them to GitHub like any other change.
