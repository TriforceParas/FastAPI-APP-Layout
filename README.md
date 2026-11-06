# App template: FastAPI + React, no Node at runtime

A reusable full-stack starting point:

- **Backend:** FastAPI, SQLAlchemy 2 + Alembic (SQLite by default; Postgres works too), Argon2id.
- **Frontend:** React 19 + Vite + Tailwind v4 + lucide icons. It is compiled to `frontend/dist` and served **by FastAPI**.
- **Included features:** initial registration (only when no users exist), login with Cloudflare Turnstile, optional "Sign in with Microsoft" (OpenID Connect, limited to your email domains), forgot password by email, optional two-factor (authenticator app or emailed code, with recovery codes), email through Microsoft 365 / Outlook, role-based access control (roles with per-page and per-feature Read/Write and a landing page; several roles per user), dashboard, user management (create, edit, assign ordered roles, deactivate, reset password, unlock, sign out everywhere, delete), roles page, audit log, account settings (profile, password, sessions, theme), a ⌘K command palette, and a live component gallery at `/components`.

Node.js is only needed to **build** the UI (locally or in the Docker build stage). The deployed container runs only Python.

## Quick start

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
python main.py --dev        # → http://127.0.0.1:8000
```

`python main.py` installs the frontend dependencies and builds the UI on first run, or whenever the UI sources have changed, then starts the server. `--dev` also turns on backend auto-reload and rebuilds the UI on every save (`vite build --watch`). Refresh the browser to see changes.

On first visit, you'll see **initial registration**, which creates the first administrator. After that, registration is closed and new users are added from **Users**.

| Command | What it does |
| --- | --- |
| `python main.py` | Build the UI if stale, then serve app + UI |
| `python main.py --dev` | Same, plus auto-reload and rebuild-on-save |
| `python main.py --rebuild` / `--skip-build` | Force or skip the UI build |
| `uvicorn main:app` | Serve only (what Docker runs) |
| `pytest` | Backend tests |
| `cd frontend && npm run build` | Typecheck and build the UI |
| `alembic revision --autogenerate -m "..."` | New DB migration |

> **NTFS/exFAT drives:** these filesystems don't support symlinks, which breaks `python -m venv` there. Create the venv on a Linux filesystem instead, e.g. `uv venv ~/.venvs/myapp`. The frontend already works on such drives: `.npmrc` disables bin symlinks, and the scripts call the tools directly.

## Roles and permissions

- **Pages and features** that can be granted live in `app/features/rbac/registry.py` and are synced into the database at startup. A page can have features (the dashboard has five), and each can be given Read or Write.
- **Roles page:** tick a page to grant everything on it, expand it to pick individual features, and choose the role's default landing page.
- **Several roles per user:** permissions combine, and the user's **first** role decides where they land after signing in. Reorder roles on the Users page.
- **Administrator:** a system role that always has full access and can't be edited.
- **Outside RBAC:** Settings (own profile, password, devices) is available to every signed-in user.

## Sign in with Microsoft (optional)

Adds a "Sign in with Microsoft" button next to the email/password form. It's off by default. Password sign-in keeps working either way.

1. In Entra ID (Azure portal) go to **App registrations** and use the app you send mail with or create a new one. Under **Authentication**, add a **Web** platform with the redirect URI `https://<your-domain>/api/auth/microsoft/callback` (locally: `http://localhost:8000/api/auth/microsoft/callback`). Then create a client secret under **Certificates & secrets**.
2. In `.env`:
   ```env
   MICROSOFT_SSO_ENABLED=true
   MICROSOFT_SSO_TENANT_ID=<your tenant GUID>       # empty = AZURE_TENANT_ID
   MICROSOFT_SSO_CLIENT_ID=                         # empty = AZURE_CLIENT_ID
   MICROSOFT_SSO_CLIENT_SECRET=                     # empty = AZURE_CLIENT_SECRET
   MICROSOFT_SSO_ALLOWED_DOMAINS=example.com,example.org
   MICROSOFT_SSO_AUTO_CREATE_ROLE=                  # e.g. Member; empty = admins add users first
   ```

Who can sign in:
- Only Microsoft work or school accounts from your tenant, and only if the email domain is listed. Personal Microsoft accounts are never accepted.
- By default, the person must already have an account here with the same email. On their first Microsoft sign-in it's linked to their Microsoft account, and after that it's matched by Microsoft's internal id, not by email.
- With `MICROSOFT_SSO_AUTO_CREATE_ROLE` set, new people from those domains get an account with that role. It can never be the Administrator role.
- If the user turned on 2FA in Settings, they still enter their code after Microsoft.
- The first administrator is still created through the setup screen.

## Turning auth off for local development

Bypass needs **three** conditions at once. This keeps a forgotten flag from ever exposing a server.

1. `AUTH_ENABLED=false` in `.env`
2. The sentinel file exists: `touch .auth-bypass`
3. `APP_ENV` is not `production`

When all three hold, every request acts as a built-in admin, and the UI shows an amber warning banner. `.auth-bypass` is in `.gitignore` **and** `.dockerignore`, so it can't reach a server through git or an image. The prod deploy workflow also deletes it. The file is checked on every request, so `rm .auth-bypass` re-enables auth immediately, with no restart.

## Security (OWASP Top 10 / ASVS)

| Area | What the template does |
| --- | --- |
| Passwords | Argon2id (auto-rehash); 12–128 chars; common-password and name/email checks; no composition rules |
| Sessions | Server-side, random 256-bit token in a `__Host-` `HttpOnly` `Secure` `SameSite=Strict` cookie; only an HMAC of it is stored; idle + absolute timeout; rotated on login; revoked on password, role or status change |
| Brute force | Per-IP rate limits on login/setup; per-account lockout (DB-backed); generic error messages; constant-time responses for unknown e-mails |
| CSRF | Origin/Fetch-Metadata check + double-submit token, bound to the session |
| Access control | Role-based: every endpoint guarded server-side with `require_screen(page_or_feature, write=…)`; Write implies Read (also a DB constraint); no privilege escalation (you can only grant or manage access you hold); at least one active Administrator always kept; 404 for other users' objects; lookups return only id + label |
| Account recovery | Single-use, expiring reset links (only an HMAC stored); identical reply for unknown addresses; resetting signs out everywhere but keeps 2FA |
| Two-factor | Optional per user: TOTP (encrypted seed, replay-protected) or emailed codes; 10 single-use recovery codes; code failures share the password lockout; admin reset |
| Bots | Cloudflare Turnstile on login and first-run setup, verified server-side before any password check, fails closed; production refuses Cloudflare's test keys |
| First-run takeover | In production, initial registration needs a one-time **setup token** (printed in the log, stored at `data/setup-token`, mode 0600) |
| Input | Pydantic models with `extra="forbid"` and length limits; validation errors never echo input; 1 MiB body limit |
| Headers | Strict CSP (no inline script/style), HSTS, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: no-referrer`, COOP/CORP, Permissions-Policy, `Cache-Control: no-store` on the API |
| Hosts | Host-header validation (`ALLOWED_HOSTS`) |
| Config | Production refuses to start with a weak `SECRET_KEY`, non-HTTPS origins, wildcard hosts or insecure cookies; API docs are off in production |
| Tracing | `X-Request-ID` on every response and log line; 500s return only a generic message plus the id (shown to the user as a reference) |
| Logging | Audit trail for every auth and admin action; errors are logged server-side with no stack traces sent to clients |
| CI security | `pip-audit`, `npm audit`, gitleaks secret scan, Trivy image scan, `alembic check`, and a test that every API route has the right permission guard |
| Container | Non-root user, healthcheck, trusted-proxy allowlist; run it read-only with dropped capabilities (see Deployment) |

## Deployment

The setup mirrors the ISO-DMS flow: GitHub Actions SSH into the VPS, run `git pull`, then `docker compose up -d --build`.

- `Dockerfile` has two stages. Node builds the UI, and a slim Python image serves everything on **:8080**.
- In your server's `/opt/app/{test,prod}/docker-compose.yml`, give the service: `env_file` pointing at its `.env`, a volume for `/app/data`, `ports: ["127.0.0.1:8080:8080"]` (reachable only through your reverse proxy), `read_only: true` with `tmpfs: [/tmp]`, `cap_drop: [ALL]`, `security_opt: ["no-new-privileges:true"]`, memory/CPU limits, and `FORWARDED_ALLOW_IPS` set to your proxy's address.
- `.github/workflows/test-deploy.yml` runs on push to `main`: lint + tests + UI build, then deploy to test.
- `.github/workflows/prod-deploy.yml` is a manual dispatch that deploys to prod.

Edit the `/opt/app/.../app` paths and the `app` service name in both workflows to match your server. They use the same `VPS_HOST`, `VPS_USERNAME` and `VPS_PASSWORD` secrets as ISO-DMS.

Minimum production `.env`:

```env
APP_ENV=production
SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(48))">
ALLOWED_HOSTS=app.example.com
ALLOWED_ORIGINS=https://app.example.com
TURNSTILE_ENABLED=true
TURNSTILE_SITE_KEY=<your Cloudflare site key>
TURNSTILE_SECRET_KEY=<your Cloudflare secret key>
PUBLIC_URL=https://app.example.com
MAIL_PROVIDER=microsoft          # or disabled
AZURE_TENANT_ID=<tenant id>
AZURE_CLIENT_ID=<app registration client id>
AZURE_CLIENT_SECRET=<client secret>
SENDER_EMAIL=noreply@yourdomain.com
```

Put a TLS-terminating reverse proxy (nginx, Caddy, Traefik) in front of it. On first start, copy the setup token from `docker compose logs app` to create the first admin.

## Project structure

Code is organised by feature: `app/features/<feature>/` holds the backend (`router.py`, `schemas.py`, `models.py`, `service.py`), and `frontend/src/features/<feature>/` holds the UI. Shared infrastructure lives in `app/core`, `app/db`, `app/api`, `app/middleware` and `app/integrations`. Tests mirror the features in `tests/<feature>/`. The full map and import rules are in the `project-structure` skill, and the reasoning is in `docs/adr/0001-feature-based-structure.md`.

Logs go to stdout: readable text in development, one JSON object per line in production (`LOG_FORMAT`). Every line and every response carries an `X-Request-ID`. See the `observability` skill for health checks and alerting.

## Working with AI agents

`AGENTS.md` (also loaded through `CLAUDE.md`) tells coding agents where everything lives, how to add a screen or endpoint, which components to use, and which security rules they must not weaken. The `/components` page is a live reference for every UI building block.

## Starting a new project from this template

The repo includes a Claude Code skill at `.claude/skills/fullstack-app/`, so it travels with the repo when you push it. Inside this repo, ask Claude to "start a new project called …", or run the script directly:

```bash
python3 .claude/skills/fullstack-app/scripts/new_project.py ../acme --name "Acme Ops" --tagline "Field operations"
```

The script copies this repo into the new folder and skips `.git`, `node_modules`, `dist`, `data`, `.env` and `.auth-bypass`. It then renames the app, compose service and deploy paths, installs dependencies, builds the UI and runs the tests. The new project gets a copy of the skill too.
