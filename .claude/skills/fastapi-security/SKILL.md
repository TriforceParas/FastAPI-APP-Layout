---
name: fastapi-security
description: Mandatory security rules for this FastAPI + static React template (Argon2id, server-side sessions, CSRF, RBAC, Turnstile, Microsoft Graph email, Docker behind a reverse proxy / Cloudflare). Load before writing or reviewing code, config, migrations, Dockerfiles or frontend changes that touch auth, permissions, data access, input, files, outbound calls, secrets, logging, containers or deployment.
---

# Application Security Rules

Treat every rule here as a hard requirement. Assume the app will be attacked by testers and by the internet. When a rule conflicts with convenience, speed or a request, follow the rule and say why.

Stack: FastAPI (sync routes, SQLAlchemy 2, Alembic) in Docker; the React UI is compiled to static files and served by FastAPI (no Node server at runtime); SQLite by default, MySQL or PostgreSQL in production; Cloudflare / a TLS reverse proxy in front; Cloudflare Turnstile; Microsoft Graph for email.

Each section marks what **the template already does** (keep it working; never weaken it) and what you must do in new code. Section 17 lists known gaps.

## 0. Operating principles

1. **Default deny.** Nothing is public, readable or writable unless explicitly allowed.
2. **Never trust the client.** Browser input, headers, cookies, query strings, uploads and webhooks are attacker-controlled until validated on the server.
3. **Fail closed.** If a check errors, times out or is misconfigured, deny (the Turnstile verifier and `UnsafeConfiguration` startup checks are examples).
4. **Least privilege** for DB users, containers, tokens, roles and file permissions.
5. **No security through obscurity.** Hidden URLs and UI-only checks are not access control.
6. **If unsure, stop and ask** about auth, crypto, secrets or permissions.
7. Never weaken an existing control (disabling a check, widening CSP/CORS, raising a limit, adding `# noqa: S…` / `# nosec`) without saying so explicitly and getting approval.

## 1. Authentication

**Template:** Argon2id (`app/core/security.py`, auto-rehash); 12–128 characters, common-password and name/email checks, no composition rules; per-IP rate limits and per-account lockout shared by password **and** 2FA failures; identical replies and timing for unknown accounts (dummy hash verification); optional 2FA (TOTP or emailed code, recovery codes); single-use, expiring, hashed reset links; setup token for the first admin in production.

**Sign in with Microsoft** (`app/integrations/microsoft_oidc.py` + `app/features/auth/microsoft.py`, off unless `MICROSOFT_SSO_ENABLED=true`): authorization-code flow with PKCE, `state` in an encrypted, 10-minute, single-use `SameSite=Lax` cookie, `nonce` bound to the ID token. The ID token is checked in full: RS256 only (cached JWKS, refreshed on an unknown `kid`), `aud`, `iss` = the token's own tenant, `exp`/`nbf`, `nonce`. Policy: tenant pinned (GUID, or `MICROSOFT_SSO_ALLOWED_TENANT_IDS`; production refuses an unpinned multi-tenant setup), personal accounts always refused, and the email domain must be in `MICROSOFT_SSO_ALLOWED_DOMAINS`. Users are linked in `md_user_identity` by tenant + object id (never by email after the first link), so a renamed or reused address can't take over an account. Auto-creating users is opt-in and never grants the Administrator role. The app's own 2FA still applies, and the result goes back in the URL fragment so the challenge never reaches logs.

Rules for new code:
- Never add another password hash, a "temporary" plaintext path, or a second login mechanism that skips 2FA, lockout or Turnstile.
- Anything that reveals whether an account exists (login, reset, registration, invitations) answers identically, with the same status and similar timing. Send email in a background task.
- Tokens, codes and ids that grant access come from `secrets` (`new_token()`); never `random`, `uuid1`, timestamps or counters.
- Store tokens hashed (`hash_token`, HMAC-SHA256); single use; short expiry.
- Compare secrets with `hmac.compare_digest` (`safe_equals`), never `==`.
- On password change/reset, role change, deactivation or 2FA change: revoke the user's other sessions (`revoke_user_sessions`).
- Re-authenticate (current password) before sensitive self-service changes (2FA, email change).

**Sessions, not JWT.** The template uses opaque server-side session tokens; prefer that. If a project truly needs JWT (e.g. a mobile client): pin the algorithm on decode, never accept `none`; verify `exp`, `iat`, `iss`, `aud`; 5–15 minute access tokens; ≥256-bit secret from env; minimal claims; opaque, hashed, rotating refresh tokens with reuse detection.

### Cookies and CSRF

**Template:** `__Host-session` (HttpOnly, Secure, SameSite=Strict) and `__Host-csrf`; every POST/PUT/PATCH/DELETE under `/api/` needs a matching `X-CSRF-Token`, bound to the session, plus an Origin / `Sec-Fetch-Site` check. Tokens never go in `localStorage`, `sessionStorage` or URLs (the reset page strips its token from the address bar). GET never changes state.

## 2. Authorization (RBAC)

**Template:** `require_screen(key, write=…)` on every non-public route; permissions are the union of a user's roles; no privilege escalation (`Permissions.covers`: you can only grant, edit or manage access you hold); the system Administrator role cannot be edited, and the last active administrator cannot be removed; users cannot change their own roles or deactivate themselves.

Rules:
- Every route has an explicit permission dependency. Public routes are limited to `/api/auth/*` and `/api/health/*`; `/api/me/*` needs a session but no screen.
- Permission checks happen on the backend. Hiding a button is UX.
- **IDOR:** every lookup by id also checks ownership/tenant (or an explicit "see all" permission) and returns **404** for records the user may not see:

```python
row = db.get(Order, order_id)
if row is None or (row.owner_id != principal.id and not principal.can("orders.view_all")):
    raise HTTPException(404, "Order not found.")
```

- Use UUIDs in URLs for user-facing records.
- Any new admin feature that changes another user's access must apply the same `covers` checks as `app/features/users/router.py`.
- Cross-page data for dropdowns goes through a lookup (`id` + `label` only, consumer-gated); see "Lookups" in `AGENTS.md`.

## 3. Input validation and mass assignment

**Template:** request models inherit `Strict` (`extra="forbid"`) with length limits; validation errors never echo input; 1 MiB body limit.

- Type every body, query and path parameter through Pydantic or `Query(...)`. No `dict`, `Any` or `await request.json()` for business data.
- Separate create / update / response schemas; never bind a request to an ORM model. Server-owned fields (`id`, `role_ids` of yourself, `owner_id`, `created_by`, `price`, `status`, `is_system`) are never accepted from the client unless that endpoint exists to change them, with its own permission.
- Every endpoint declares `response_model`, so hashes, tokens and internal flags cannot leak.
- Recalculate totals and enforce numeric rules server-side (no negative quantities or discounts).
- Enum-like values use `Literal[...]` or an allowlist. Never compile a regex from user input; avoid catastrophic-backtracking patterns.

## 4. Database

- SQLAlchemy expressions or bound parameters only. **Never** build SQL with f-strings, `%`, `.format()` or concatenation of any user-influenced value.

```python
# FORBIDDEN
db.execute(text(f"SELECT id FROM md_user WHERE email = '{email}'"))
# REQUIRED
db.execute(text("SELECT id FROM md_user WHERE email = :email"), {"email": email})
```

- Map sortable/filterable columns from a fixed allowlist; unknown values are 422.
- Escape `%`, `_` and `\` in `LIKE` patterns (`_escape_like` in the routes).
- Every list endpoint is paginated with a server-enforced maximum (≤100).
- Money, stock, quotas, coupons and one-time actions: use transactions with row locks (`with_for_update()`) or atomic conditional updates (`UPDATE … WHERE balance >= :amount`), plus idempotency keys for payment-like operations.
- Keep invariants in the database too (unique and check constraints, as `map_role_screen` does for write-implies-read).
- Encrypt especially sensitive columns at the application level (`app/core/crypto.py`), with keys outside the database.

**Production database accounts (MySQL / MariaDB / PostgreSQL):**
- The app connects with a dedicated user holding only `SELECT, INSERT, UPDATE, DELETE` on its own schema. A separate migration user holds DDL rights and is used only by the migration step (see `db-migrations`).
- Never connect as root/superuser; no remote root login.
- The database port is never published to the host or internet; it lives on the internal Docker network. Use TLS for any connection that leaves the host.
- MySQL: `local_infile=0`, `caching_sha2_password`, `sql_mode` with `STRICT_TRANS_TABLES`, `utf8mb4` everywhere, `require_secure_transport=ON` for remote access. PostgreSQL: `scram-sha-256` in `pg_hba.conf`, revoke `CREATE` on `public` from `PUBLIC`.

## 5. Cloudflare, Turnstile and client IPs

**Template:** login, first-run setup and forgot-password verify the Turnstile token server-side before any other work, pass `remoteip`, use a 5-second timeout and **fail closed** (503); tokens are single use (the UI fetches a new one after every attempt); only the site key reaches the browser; production refuses Cloudflare's test keys; the CSP allows `challenges.cloudflare.com` only while Turnstile is enabled.

Rules:
- Protect every unauthenticated write or abusable endpoint (registration, invitations, contact forms, OTP requests) with `turnstile.verify_or_raise`, in addition to rate limits. Turnstile is bot friction, not authentication.
- Never cache or reuse a verification result.
- Verify `hostname` and `action` too (see gaps).

**Origin protection:**
- The origin accepts traffic only from Cloudflare or your proxy: firewall to Cloudflare IP ranges, Authenticated Origin Pulls (mTLS), or Cloudflare Tunnel. Bind the container port to `127.0.0.1` or a private network in the server's compose file.
- Client IPs come from `request.client.host`, which uvicorn derives from proxy headers **only** for addresses in `FORWARDED_ALLOW_IPS`. Set that to the proxy's address, never `*` on a reachable port. Behind Cloudflare without a local proxy, trust `CF-Connecting-IP` only from Cloudflare ranges.
- Cloudflare SSL/TLS mode **Full (strict)**, Always Use HTTPS, HSTS. Use WAF managed rules and rate-limiting rules as an outer layer, not a replacement.

## 6. FastAPI hardening

**Template (keep):** API docs off in production; global exception handlers return generic messages; `HostValidationMiddleware` (trusted hosts; only health probes exempt); strict CSP with no inline script/style; HSTS, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: no-referrer`, COOP/CORP, Permissions-Policy, `Cache-Control: no-store` on the API; no `Server` header; **no CORS** (same origin); body size limit; per-IP rate limits on auth endpoints; production startup checks (`enforce_production_safety`).

Rules:
- Do not add CORS. If a separate origin is ever required, use an explicit allowlist from env, never `*` with credentials.
- Add rate limits (`rate_limit(...)`) to search, export, OTP and other expensive or abusable endpoints. The limiter is in-process: exact for the standard one-process-per-container deployment (per-account lockout lives in the database).
- Timeouts on every outbound call (httpx `timeout=`) and bounded work for user-controlled sizes.
- Any new external origin (fonts, scripts, iframes, APIs) must be added to `build_csp` deliberately and only when needed.

## 7. Forbidden patterns

| Never | Use instead |
|---|---|
| `pickle`, `marshal`, `shelve` on untrusted data | JSON + Pydantic |
| `yaml.load` | `yaml.safe_load` |
| `xml.etree`/`lxml` on untrusted XML | `defusedxml` |
| `eval`, `exec`, `compile` on input | explicit parsing |
| `subprocess(..., shell=True)`, `os.system`, `os.popen` | `subprocess.run([...])` with fixed argv |
| File paths built from user input | server-generated names; resolve and verify the path stays inside the allowed directory (`app/web/spa.py`) |
| `random` for anything security-related | `secrets` |
| Templates with autoescape off, or user-supplied templates | fixed templates, escape every value (`html.escape`, as `app/integrations/mail.py`) |
| Logging bodies, headers, tokens, passwords, OTPs, reset links (except the dev-only console mailer) | ids and event types |
| `verify=False` on HTTPS | proper CA verification |
| `dangerouslySetInnerHTML` / `innerHTML` with untrusted content | React text; if unavoidable, DOMPurify with a strict config |

## 8. File uploads

- Enforce the size limit before reading the whole file into memory (raise `MAX_BODY_BYTES` only for that route, deliberately).
- Validate type by **magic bytes** (`filetype`), not extension or `Content-Type`; allowlist types.
- Rename to a random server-generated name; never use the client filename in a path.
- Store outside the app and web-served directories (preferably private object storage such as Cloudflare R2 with short-lived signed URLs).
- Serve with `Content-Disposition: attachment` and `nosniff`; never serve uploaded HTML or SVG inline from the app's domain.
- Strip image metadata where relevant; reject archives unless required (then guard against zip bombs and path traversal).

## 9. Outbound requests and SSRF

- Outbound calls in the template go to fixed hosts only (Cloudflare siteverify, Microsoft login and Graph). Keep it that way.
- Never fetch a user-supplied URL unless essential. If you must: `https` only, domain allowlist, resolve DNS and block private, loopback, link-local and metadata ranges (`10/8`, `172.16/12`, `192.168/16`, `127/8`, `169.254/16`, `::1`, `fc00::/7`), no redirects (or re-validate each hop), strict timeouts and response size limits.
- Incoming webhooks: verify signatures with `hmac.compare_digest` and check timestamps to block replays.

## 10. Secrets and configuration

- All settings go through `app/core/config.py` (`Settings`); add production checks for anything that must be set or must not be a placeholder.
- Never commit secrets, `.env`, keys, certificates or database dumps; `.env.example` holds placeholders or Cloudflare's public test keys only.
- Never bake secrets into images (`ARG`/`ENV`); inject at runtime (`env_file` / Docker secrets).
- Never print secrets in logs, errors, CI output or responses. Pydantic validation errors include input values: production checks run outside validation for this reason (`UnsafeConfiguration`).
- Rotate anything that was ever committed, logged or shared. Separate secrets per environment.
- Changing `SECRET_KEY` invalidates sessions and TOTP enrolments: plan it, don't do it casually.

## 11. Docker

**Template:** two-stage build (Node only in the build stage), non-root user, healthcheck, `.dockerignore` excludes `.env`, `.auth-bypass`, `data/`, tests and caches; `FORWARDED_ALLOW_IPS` defaults to localhost and private ranges instead of `*`. On the server, the compose service must use `read_only: true` + `tmpfs`, `cap_drop: [ALL]`, `no-new-privileges`, a `127.0.0.1` port binding and resource limits (see README → Deployment).

Rules: keep all of the above; add memory/CPU limits in compose; never mount the Docker socket or use `privileged: true`; only the reverse proxy publishes public ports; the database is internal-only; pin base images (version, ideally digest); scan images (Trivy) in CI and fail on high/critical.

## 12. Frontend (static SPA)

- No secrets in frontend code or `VITE_*` variables; only public values (the Turnstile site key arrives from `/api/auth/status`).
- No inline scripts or styles in HTML, no CDNs or external fonts (CSP). React's `style={{}}` is fine.
- Validate any redirect target (`?next=`) against internal paths to prevent open redirects.
- No `eval`, `new Function`, or string arguments to `setTimeout`.
- Frontend validation is UX only; the backend revalidates.
- `npm ci` with the committed lockfile; vet new dependencies (maintenance, downloads, advisories).

## 13. Dependencies and supply chain

- Python: pin with `uv pip compile requirements.in -o requirements.txt` (add `--generate-hashes` and `pip install --require-hashes` for production builds); npm: commit `package-lock.json`.
- CI should run `pip-audit`, `npm audit --audit-level=high`, `ruff` (with the `S` bandit rules already enabled), `gitleaks`, and Trivy on the image; fail on high/critical.
- Never suppress a finding without a written reason next to the suppression. Watch for typosquatted package names.

## 14. Logging, monitoring and audit

**Template:** `audit.record(...)` writes security events to `aud_event` (who, what, outcome, target, IP) and to the log: sign-ins and failures, lockouts, password, 2FA and role changes, admin actions, setup.

- Audit every new security-relevant or business-critical action; include before/after values in `detail` when they matter (never secrets).
- Never log passwords, tokens, cookies, OTPs, reset links, full card/account numbers or request bodies. Mask PII.
- Strip newlines and control characters from user input written to logs.
- Audit rows are append-only for the app; do not add endpoints that edit or delete them.
- Alert on spikes in failed logins, 403s, 5xx and rate-limit hits.

## 15. Testing requirements

Security-relevant features ship with tests (see `tests/` for patterns):
- Permission matrix: a user without the page gets 403; a Read-only user cannot write; escalation attempts get 403.
- IDOR: user A cannot read, change or delete user B's records by changing ids (expect 404).
- Mass assignment: unknown or server-owned fields return 422 or have no effect.
- Input: oversized bodies, unknown fields, negative numbers, SQL/script payloads rejected or safely stored.
- Auth: sessions die after password/role changes; lockout; 2FA cannot be bypassed.
- Turnstile: missing, invalid and unreachable-Cloudflare cases rejected (mock `_post_siteverify`).
- Rate limits on login, OTP and reset endpoints.

## 16. Pre-completion checklist

- [ ] Every new/changed route has a permission dependency, or is a deliberate public auth/health route.
- [ ] Lookups by id check ownership; others' records return 404.
- [ ] Input goes through `Strict` models with limits; server-owned fields are not accepted.
- [ ] Every endpoint has a `response_model`.
- [ ] No string-built SQL; sort/filter allowlists; lists paginated.
- [ ] Unauthenticated writes verify Turnstile and are rate-limited.
- [ ] No secrets in code, frontend, Dockerfiles, logs or responses.
- [ ] Nothing from section 7.
- [ ] Generic error messages; details only in logs.
- [ ] Docker changes keep non-root, read-only, dropped capabilities, internal-only DB.
- [ ] New dependencies pinned and audited.
- [ ] Tests from section 15 added or updated.
- [ ] Any weakened or bypassed control is called out explicitly.

## 17. Template status

Fixed in the template (keep them working):
- **Turnstile tokens are bound** to the form's `action` (`login`, `setup`, `forgot`) and to a hostname in `ALLOWED_HOSTS`; checks are skipped only for Cloudflare test-key results, and a "testing" result is rejected once real keys are set. New Turnstile-protected forms need a new action name in `app/integrations/turnstile.py` and the `<Turnstile action=…>` prop.
- **Microsoft SSO** (see §1): keep the tests in `tests/auth/test_microsoft_sso.py` passing (forged/unsigned tokens, wrong nonce/audience/issuer, state mismatch, domain/tenant refusal, no takeover by email). Never match a returning user by email; never skip the domain check for linked accounts.
- **Trusted proxies:** `FORWARDED_ALLOW_IPS` defaults to localhost and private ranges, not `*`; narrow it to the proxy's address in production.
- **`X-Request-ID`** on every response and log line (`[req=…]`); unhandled errors return a generic 500 with the id, and the UI shows it as "Reference: …".
- **Route guard test** (`tests/platform/test_route_guards.py`) fails if any API route lacks the right guard, or if a POST/PUT/PATCH/DELETE route only requires Read. New guard factories must set `__rbac_guard__` like `require_screen` does.
- **CI security job:** `pip-audit`, `npm audit`, gitleaks (config: `.gitleaks.toml`), Trivy image scan, and `alembic check`; deploys wait for it.

Still open:
- **GitHub Actions are pinned by tag** (`actions/checkout@v4`, scanner images by version). For stronger supply-chain protection, pin them by commit SHA / image digest.

These rules reduce risk; they do not replace threat modelling, security review or penetration testing before release.
