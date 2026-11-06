---
name: code-review
description: Code review checklist for this FastAPI + React template. Load when reviewing a diff, pull request or your own work before saying it is done; it points to the detailed rules in the other skills (security, API, database, structure, errors/logging, frontend, docs).
---

# Code Review

Review in this order. Anything in **Blockers** stops a merge; the rest is fixed in the same PR unless agreed otherwise. Check the diff against the skills named in each section: this list is the summary, not the full rules.

## 0. Before reading the code

- [ ] The PR says **what** changed and **why**, how it was tested, and any risk (migration, config change, breaking API).
- [ ] It's one logical change. Large refactors are separate from behaviour changes.
- [ ] CI is green: `pytest`, `ruff check`/`ruff format --check`, `npm run build`, `alembic check`, and the security job.

## 1. Blockers (security and data integrity) — `fastapi-security`

- [ ] Every new or changed route has the right guard: `require_screen(key)` for reads, `write=True` for changes, `require_lookup` for lookups (`tests/platform/test_route_guards.py` enforces this).
- [ ] Lookups by id check ownership/tenant and return **404** for records the user can't see (no IDOR).
- [ ] No privilege escalation: assigning roles, editing roles or managing users goes through the `covers` checks.
- [ ] Request models inherit `Strict` with length/range limits; server-owned fields can't be set by clients; every route has a `response_model`.
- [ ] No string-built SQL; sort/filter fields come from allowlists; lists are paginated with a server max.
- [ ] Unauthenticated or abusable endpoints use Turnstile (with an `action`) and rate limits.
- [ ] No secrets, tokens, passwords, OTPs or PII in code, logs, responses, fixtures or the frontend.
- [ ] Money, stock and one-time actions are atomic (locks or conditional updates) and idempotent where needed.
- [ ] Security controls (CSP, CSRF, host check, headers, lockout, startup checks) are not weakened, or the PR explicitly calls out the change and justifies it.
- [ ] Migrations don't lose data (no drop + add for renames; NOT NULL columns are backfilled; there's a downgrade) — `db-migrations`.

## 2. Correctness

- [ ] It does what the PR says, including edge cases: empty, maximum size, duplicates, concurrent edits, deleted or inactive related records, users with several roles.
- [ ] Error paths are handled: failed writes roll back; external calls have timeouts; failures are surfaced (`error-handling-logging`).
- [ ] Times are UTC-aware (`utcnow`, `UTCDateTime`); there's no float money.
- [ ] Transactions commit once per request, after audit events are staged.

## 3. Tests

- [ ] New behaviour has tests, and bug fixes have a test that failed before the fix.
- [ ] Security-relevant changes include the `fastapi-security` §15 tests (permission matrix, IDOR, mass assignment, rate limits).
- [ ] Tests assert outcomes (status codes and bodies), not implementation details. They're deterministic, with no real network or sleeping (mock `_post`/`_post_siteverify`).
- [ ] Each test proves something: a check over an empty set passes vacuously, so sanity-check that it looks at real data.

## 4. Design and structure — `project-structure`, `api-conventions`, `db-naming-conventions`

- [ ] Files are in the right feature, and the dependency rules hold (no router-to-router imports, no FastAPI in services or integrations, no `core` → `features` imports).
- [ ] Endpoints follow the URL, method, status, naming and pagination conventions; there are no breaking API changes without a callout.
- [ ] Table, column and constraint names follow the prefix convention; a model change comes with its migration.
- [ ] Each piece of logic lives in one place: no copy-paste between features, and shared helpers sit in the owning feature or in `core`.
- [ ] No speculative abstractions, dead code, commented-out code or leftover debug output.

## 5. Readability

- [ ] Names say what things are (`expires_at`, not `exp`; `user_count`, not `n`).
- [ ] Functions do one thing; deep nesting is flattened with early returns.
- [ ] Comments explain *why*, not *what*. Docstrings on modules and non-obvious functions (`documentation`).
- [ ] Type hints are present on Python functions; the TypeScript has no `any`.

## 6. Errors and logging — `error-handling-logging`

- [ ] User-facing messages are short and safe; machine codes are stable.
- [ ] There's no bare `except` or silent swallowing; `log.exception` is used inside handlers that keep going.
- [ ] Logs use the right levels and `extra=` fields, with nothing from the never-log list.
- [ ] Security-relevant changes record an audit event.

## 7. Frontend — `frontend-conventions`

- [ ] Built only from `@/components/ui` (no raw `<select>`); loading, error and empty states are handled; list pages use `DataTablePage`/`DataTable`; dialogs use `open` so they animate out.
- [ ] Permissions are mirrored with `RequireScreen` / `can()`.
- [ ] Works in light and dark mode and at 390px wide; keyboard-accessible; labels and `aria-label`s are present.
- [ ] Types match the backend schemas; there's no `dangerouslySetInnerHTML` and no secrets.

## 8. Operations — `observability`

- [ ] New config has a default, is documented in `.env.example`, and gets a production safety check if it can be unsafe.
- [ ] New required dependencies are in the readiness check; new failure modes are logged and alertable.
- [ ] New dependencies (pip or npm) are justified, pinned, and pass audit.
- [ ] The deploy impact is stated (migration order, env changes, downtime).

## 9. Docs — `documentation`

- [ ] `README.md` / `AGENTS.md` / skills are updated when setup, conventions or architecture change.
- [ ] There's an ADR for significant decisions (new dependency, new pattern, deviating from a convention).
- [ ] `.env.example` is updated.

## How to write review comments

- Prefix the severity: **blocker:**, **should:** or **nit:**. Explain the risk, not just the rule ("this lets a member read other users' orders"), and suggest a fix.
- Be specific (file:line), and point to the skill rule when relevant.
- Approve once the blockers and shoulds are fixed; nits are optional.
- When reviewing your own work as an agent, run the checks, fix what you find, and report anything you couldn't verify.
