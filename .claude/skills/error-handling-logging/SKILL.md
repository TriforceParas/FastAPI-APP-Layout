---
name: error-handling-logging
description: How to raise, handle and report errors, and how to log, in this FastAPI + React template (AppError hierarchy, {"detail"} responses, request ids, text/JSON logs, audit events, what never to log). Load before writing try/except, raising errors, adding log statements or audit records, handling API errors in the frontend, or debugging a production issue.
---

# Error Handling and Logging

Goals: users see short, safe, actionable messages; operators can find the full story in the logs from a single request id; nothing secret ever reaches a response or a log line.

## 1. How errors flow

```
service / integration ── raise AppError subclass ─┐
router / dependency ──── raise HTTPException ─────┤──► handler in app/main.py ──► {"detail": "..."} + status
Pydantic validation ─────────────────────────────┤──► 422 {"detail": [{loc, msg}]} (input never echoed)
anything unexpected ──────────────────────────────┘──► RequestIdMiddleware: logs traceback, returns
                                                       500 {"detail": "Internal server error", "request_id": "…"}
```

Every response carries `X-Request-ID`; the UI shows it on 5xx errors as "Reference: …".

## 2. Raising errors

| Situation | Raise | Status |
|---|---|---|
| Record missing, or not visible to this user | `NotFound("Order not found.")` | 404 |
| Duplicate, invalid state, business rule conflict | `Conflict("This quotation is already approved.")` | 409 |
| Missing permission (beyond `require_screen`) | `Forbidden("You cannot approve your own quotation.")` | 403 |
| Bad but well-formed request (expired link, failed Turnstile) | `BadRequest(...)` | 400 |
| Business validation Pydantic can't express | `Unprocessable(...)` | 422 |
| Throttled | `TooManyRequests(..., headers={"Retry-After": "30"})` | 429 |
| Dependency down (payment provider, email, Cloudflare) | `ServiceUnavailable(...)` | 503 |

From `app.core.errors`. Rules:

- **Services and integrations raise `AppError` subclasses, never `HTTPException`** (they must not import FastAPI). Routers and dependencies may use either.
- **`detail` is for end users**: one short sentence saying what happened and what to do. No ids, SQL, exception text, stack traces, file paths, library names or internal state.
- When the frontend must branch on an error, make `detail` a **stable snake_case code** (existing: `csrf_failed`, `password_change_required`) and map it to a message in `frontend/src/lib/api.ts`. Never change an existing code.
- Same message for "doesn't exist" and "not yours" (404). Same reply for "unknown email" and "known email" on auth flows.

## 3. Catching errors

- **Don't catch what you can't handle.** Let unexpected exceptions propagate: the middleware logs them with the request id and returns a safe 500.
- **Catch narrowly**: the specific exception (`httpx.HTTPError`, `IntegrityError`), never bare `except:`; `except Exception` only at a boundary that must not fail (background email: `send_safely`), and then always `log.exception(...)`.
- **Translate at the boundary**: convert library errors into `AppError` where they happen (`IntegrityError` → `Conflict`, `httpx.ConnectError` → `ServiceUnavailable`), using `raise … from None` so internals don't leak into chained tracebacks shown elsewhere.
- **Roll back** the session after a failed flush/commit before continuing (`db.rollback()`).
- **Fail closed** in security checks: on error, deny.
- **No silent failures**: if you swallow an exception, log it with context and say why in a comment.
- Background tasks have no user to answer: they must catch, log and never raise.

```python
try:
    db.flush()
except IntegrityError:
    db.rollback()
    raise Conflict("A customer with this GST number already exists.") from None
```

## 4. Frontend error handling

- All calls go through `api.*` in `src/lib/api.ts`; it throws `ApiError` (`status`, `detail`, `message`, `requestId`).
- Show `err.message` (already user-friendly): in an `<Alert tone="danger">` for forms, `toast.error(title, message)` for actions, `<ErrorState onRetry>` for failed page loads.
- 401 is handled globally (back to sign-in); don't special-case it in pages.
- Never show raw `detail` arrays, stack traces or JSON to users. Never `console.log` API responses that may contain personal data.

## 5. Logging

```python
import logging

log = logging.getLogger(__name__)

log.info("Order submitted", extra={"order_id": order.id, "item_count": len(items)})
log.warning("Payment provider slow", extra={"provider": "razorpay", "duration_ms": 4200})
log.exception("Invoice PDF generation failed", extra={"invoice_id": invoice.id})  # inside except: includes traceback
```

- **Format**: `LOG_FORMAT=text` (dev) or `json` (default in production: one object per line with `ts`, `level`, `logger`, `request_id`, `message` and every `extra` field). Pass data as `extra={...}`, not inside the message string, so it becomes searchable fields.
- **Levels**: `DEBUG` noisy diagnostics (off in production) · `INFO` normal business events and one access line per request · `WARNING` something unexpected but handled (retry, degraded dependency, rejected token) · `ERROR`/`exception` a request or job failed · `CRITICAL` the app cannot work (startup failure).
- **Every line carries the request id** automatically (`[req=…]` / `"request_id"`). Background work started from a request inherits it.
- One `app.access` line per request is written by `AccessLogMiddleware` (method, path without query string, status, duration, client IP). Don't add your own per-request logs.
- Use module loggers (`__name__`); never `print`.

### Never log

Passwords, password hashes, session/CSRF/reset/challenge tokens, OTP and recovery codes, TOTP secrets, API keys, `Authorization` or `Cookie` headers, full request or response bodies, query strings (reset links carry tokens there), card or bank numbers, national ids. Mask PII where you must log it (`mask_email`). Don't log values users typed into free-text fields unless needed, and strip newlines/control characters if you do (log injection). The dev-only console mailer is the single exception and is refused in production.

## 6. Audit events vs logs

| | `audit.record(...)` → `aud_event` | `log.*` |
|---|---|---|
| Purpose | Who did what to which record (security and business accountability) | Operations and debugging |
| Retention | Long, append-only | Days to weeks |
| Examples | sign-in, password/2FA/role changes, user created/deleted, approvals, exports | slow dependency, retries, handled errors, tracebacks |

Record an audit event for every security-relevant or business-critical change, with `outcome` (`success`/`failure`/`denied`), `target_type`/`target_id` and a small `detail` dict (before/after values when useful, never secrets). `audit.record` also writes a log line.

## 7. Checklist

- [ ] Services/integrations raise `AppError` subclasses; no FastAPI imports there.
- [ ] Every `detail` is user-safe; machine codes are stable.
- [ ] No bare `except`; caught exceptions are handled, translated or logged with `log.exception`.
- [ ] Failed DB writes roll back; security checks fail closed.
- [ ] Logs use `extra=` fields, the right level, and nothing from the "never log" list.
- [ ] Security-relevant changes write an audit event.
- [ ] Frontend shows `ApiError.message` via Alert / toast / ErrorState; 5xx shows the reference.
