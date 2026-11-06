---
name: api-conventions
description: REST API naming and design conventions for this FastAPI + React template. Load before creating, renaming or reviewing any endpoint, router, Pydantic request/response schema, query parameter, error response, status code, or frontend API call (src/lib/api.ts, src/lib/types.ts).
---

# API Naming and Design Conventions

Apply these rules whenever you create or change an endpoint, router, schema or frontend API call. The goal: anyone (human or agent) can guess an endpoint's URL, method, payload and response shape without reading its code.

## 0. Precedence

1. The `fastapi-security` skill wins over anything here.
2. This template's existing conventions (described below) win over generic REST advice. If you find code that breaks them, follow the convention for new code and flag the mismatch. Never mix styles inside one API.
3. If an endpoint does not fit any pattern below, stop and propose a design before writing code.

## 1. URL structure

```
/api/<resource>[/<id>][/<sub-resource>[/<id>]][/<action>]
```

- All endpoints live under `/api/` (prefix set once in `app/api/router.py`). Everything else is the SPA.
- **Versioning:** the template is unversioned because the API serves only its own UI. When a project exposes the API to outside consumers, switch the single prefix to `/api/v1` for every router at once (and `frontend/src/lib/api.ts`). Never version some routers and not others.
- Resource names are **plural nouns** in **kebab-case**: `/users`, `/purchase-orders`, `/payment-terms`.
- Lowercase only, no trailing slash, no file extensions, no verbs in resource paths (`/orders`, never `/getOrders` or `/order-list`).
- Path parameters are named `<singular>_id`: `/orders/{order_id}`.
- **IDs in URLs:** business records use UUID strings (as `md_user` does). Small admin configuration tables (`md_role`, `md_screen`) use integer ids; that is acceptable only because they are permission-guarded and not user data. New user-facing data uses UUIDs.
- Nest at most **one level**, and only when the child cannot exist without the parent: `/orders/{order_id}/items` is fine; deeper chains get their own top-level resource (`/order-items/{item_id}`).
- One canonical URL per resource.

### Standard CRUD

| Operation | Method | Path | Success |
|---|---|---|---|
| List | GET | `/api/orders` | 200, paginated |
| Get one | GET | `/api/orders/{order_id}` | 200 |
| Create | POST | `/api/orders` | 201 (`Location` header optional) |
| Partial update (default) | PATCH | `/api/orders/{order_id}` | 200 |
| Full replace | PUT | `/api/orders/{order_id}` | 200 (only when the client sends the whole object, e.g. `PUT /api/roles/{role_id}`) |
| Delete | DELETE | `/api/orders/{order_id}` | 204, no body |

### Actions (state transitions)

A business action that is more than a field edit is a POST to a verb sub-path in kebab-case:

```
POST /api/users/{user_id}/unlock
POST /api/users/{user_id}/password            (admin password reset)
POST /api/users/{user_id}/sessions/revoke
POST /api/users/{user_id}/mfa/reset
POST /api/quotations/{quotation_id}/approve
```

- Never change status through a generic PATCH (`{"status": "approved"}`) when the transition has rules, side effects or its own permission.
- Actions return the updated resource with 200, 204 when there is nothing to return, or 202 if processed asynchronously.

### Route groups that already exist

| Group | Paths | Notes |
|---|---|---|
| Auth | `/api/auth/status`, `/setup`, `/login`, `/login/verify`, `/login/resend`, `/logout`, `/password/forgot`, `/password/reset` | Public; rate-limited; Turnstile where a bot could abuse it |
| Current user | `/api/me`, `/api/me/password`, `/api/me/sessions`, `/api/me/mfa/*` | Outside RBAC: every signed-in user |
| Lookups | `/api/lookups/<resource>` | Minimal `LookupItem` (`id`, `label`) lists for dropdowns; see "Lookups" in `AGENTS.md` |
| RBAC admin | `/api/roles`, `/api/screens` | Guarded by the `roles` screen |
| Health | `/api/health/live`, `/api/health/ready` | Public, no internals |

Add when a project needs them, following the same shapes: bulk (`POST /api/<resource>/bulk-create|bulk-update|bulk-delete`, with a max batch size), exports (`POST /api/<resource>/exports` → 202, `GET /api/exports/{export_id}`), async jobs (`GET /api/jobs/{job_id}`), incoming webhooks (`/api/webhooks/<provider>`, signature verified), global search (`GET /api/search?q=`).

## 2. Methods and status codes

GET never changes state. Use these codes; anything else needs a reason in the code review.

| Code | When |
|---|---|
| 200 | Read, update or action succeeded |
| 201 | Created |
| 202 | Accepted for async processing, or a deliberately uniform reply (`/password/forgot`) |
| 204 | Deleted / action with no body |
| 400 | Malformed or rejected request that is not a validation error (failed Turnstile, expired challenge or reset link, wrong current password) |
| 401 | Not signed in, or credentials/code wrong at sign-in |
| 403 | Signed in but lacks permission (`require_screen`), CSRF failure, escalation attempt |
| 404 | Not found, **or exists but belongs to someone else** (never confirm existence) |
| 409 | Conflict: duplicate, invalid state, last-admin / self-protection rules |
| 413 | Body too large (middleware) |
| 422 | Validation error (Pydantic or password policy) |
| 429 | Rate limited, always with `Retry-After` |
| 500 | Unexpected; generic message only |
| 503 | A dependency is down (database, Turnstile, email) |

Never return 200 with an error inside the body.

## 3. JSON field names

- **snake_case** everywhere in requests and responses; the frontend uses the keys as received (no camelCase aliases).
- Booleans start with `is_`, `has_`, `can_`, `must_` or `should_`: `is_active`, `must_change_password`, `can_write`.
- Timestamps end with `_at`; dates without time end with `_date`.
- References end with `_id`; counts end with `_count` (`user_count`).
- Avoid abbreviations except well-known ones (`id`, `url`, `ip`, `otp`, `mfa`, `gst`, `uom`).
- Never leak storage details: no table prefixes (`md_`, `txn_`) or internal column names (`password_hash`, `token_hash`) in API fields.

## 4. Data formats

| Type | Format | Example |
|---|---|---|
| Timestamp | ISO 8601 UTC (`UTCDateTime` columns serialize with `Z`) | `"2026-11-05T18:30:00Z"` |
| Date | ISO 8601 date | `"2026-11-05"` |
| Money | Integer minor units + ISO 4217 code, never floats | `{"amount_minor": 1250050, "currency": "INR"}` |
| Percentage | Decimal number | `18.0` |
| Enum | Lowercase snake_case string | `"pending_approval"`, `"totp"` |
| Phone | E.164 | `"+919876543210"` |
| Country / currency | ISO 3166-1 alpha-2 / ISO 4217 | `"IN"`, `"INR"` |

Optional values are returned as `null` (stable shapes); empty lists are `[]`, never `null`. Exception: `POST /api/auth/login` returns either the signed-in shape or the 2FA-challenge shape, with unused fields omitted.

## 5. Request and response shapes

**Single resource:** the object itself, no envelope.

**Lists:** always paginated, in this template's shape:

```json
{ "items": [ ... ], "total": 134, "page": 1, "page_size": 25 }
```

For huge or fast-growing tables use cursor pagination: `{ "items": [...], "next_cursor": "…", "has_more": true }`.

**Errors:** the template uses FastAPI's shape, produced by the global handlers in `app/main.py`:

```json
{ "detail": "This role is still assigned to users. Reassign them first." }
{ "detail": [ { "loc": ["email"], "msg": "value is not a valid email address" } ] }
```

- `detail` strings must be safe to show to end users: no stack traces, SQL, ids or library names.
- Where the frontend must branch on an error, use a stable machine code as the whole `detail` (existing: `csrf_failed`, `password_change_required`) and map it to a message in `src/lib/api.ts`. Never change an existing code.
- Validation errors never echo the submitted value.

## 6. Query parameters

All snake_case.

- **Pagination:** `page` (default 1) and `page_size` (default 20–50, **max 100**, enforced with `Query(ge=1, le=100)`). Cursor endpoints: `cursor` and `limit` (max 100).
- **Text search:** `q` (max 100 chars). Escape `%`, `_` and `\` before `LIKE`.
- **Filters:** exact match by field name (`?state=active&role_id=3`); several values comma-separated; ranges with inclusive `_from` / `_to` suffixes (`?created_from=2026-10-01`); booleans `true` / `false`.
- **Sorting:** `sort=-created_at,name`, only fields from an explicit per-endpoint allowlist; anything else is 422.
- Constrain every parameter with `Literal[...]` or `Query(...)` limits.

## 7. Headers

| Header | Direction | Status in template |
|---|---|---|
| `X-CSRF-Token` | Request | Required on every POST/PUT/PATCH/DELETE (handled by `lib/api.ts`) |
| `Retry-After` | Response | Sent with every 429 |
| `Location` | Response | Optional on 201 |
| `X-Request-ID` | Both | Not yet implemented: add middleware that accepts/generates it, echoes it and logs it, then show it in error toasts for support |
| `Idempotency-Key` | Request | Add for payments, order creation and other non-repeatable POSTs |
| `ETag` / `If-Match` | Both | Add for PATCH/PUT where concurrent edits matter; 409/412 on mismatch |
| `Deprecation` / `Sunset` | Response | On deprecated endpoints (also `deprecated=True` in FastAPI) |

Do not invent other custom headers without approval.

## 8. Breaking changes

Breaking: removing/renaming a field or endpoint, changing a type or meaning, adding a required request field, changing an error code. Not breaking: new optional request fields, new response fields, new endpoints, new enum values (the frontend must tolerate unknown values). The SPA ships with the API, so update both in the same change; if a project has external consumers, introduce `/api/v1` first (section 1).

## 9. FastAPI code conventions in this template

```
app/features/<feature>/router.py   HTTP layer for one resource/feature (registered in app/api/router.py)
app/features/<feature>/schemas.py  its Pydantic models (shared pieces live in app/api/schemas.py)
app/features/<feature>/service.py  business logic, no FastAPI imports (raise app.core.errors)
app/features/rbac/registry.py      pages + features that permissions apply to
```
Full layout and import rules: `project-structure`.

```python
router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])
CanRead = Depends(require_screen("purchase_orders"))
CanWrite = Depends(require_screen("purchase_orders", write=True))
```

Routers validate, check permissions, call services or run simple SQLAlchemy queries, audit, commit, and return. Move multi-step logic into the feature's `service.py`.

**Handler names** (also the OpenAPI operation names): `list_orders`, `get_order`, `create_order`, `update_order`, `delete_order`, `cancel_order` (action), `list_order_items` (sub-resource).

**Schema names** (match the existing ones):

| Purpose | Name |
|---|---|
| Create request | `OrderCreate` (inherits `Strict`) |
| Partial update | `OrderUpdate` (all optional; apply only fields that were sent) |
| Full replace | `OrderWrite` (e.g. `RoleWrite`) |
| Response | `OrderOut` |
| List page | `OrdersPage` (`items`, `total`, `page`, `page_size`) |
| Action request | `<Action><Resource>Request`, e.g. `CancelOrderRequest` |
| Lookup item | `LookupItem` (`id`, `label`) |

**Permissions:** this template's RBAC is per screen, not per verb. The key is the screen key from `app/features/rbac/registry.py` (snake_case of the resource, e.g. `purchase_orders`; features as `purchase_orders.approve`):

| Endpoint | Dependency |
|---|---|
| `GET /api/purchase-orders`, `GET …/{id}` | `require_screen("purchase_orders")` |
| `POST`, `PATCH`, `PUT`, `DELETE` | `require_screen("purchase_orders", write=True)` |
| Action with its own permission | a feature: `require_screen("purchase_orders.approve", write=True)` |
| Lookup for dropdowns elsewhere | `require_lookup("purchase_orders")` with consumers registered in `LOOKUPS` |

Multi-word resource: URL `/purchase-orders`, screen key `purchase_orders`, feature package `app/features/purchase_orders/`, schemas `PurchaseOrderOut`, table `txn_purchase_order` (see `db-naming-conventions`).

**Every route declares:** `response_model` (or `status_code=204`), `status_code` when not 200, and a permission dependency (or is one of the public auth/health routes).

```python
@router.post("/{quotation_id}/approve", response_model=QuotationOut, summary="Approve a quotation")
def approve_quotation(
    quotation_id: str,
    request: Request,
    db: DbSession,
    principal: Principal = Depends(require_screen("quotations.approve", write=True)),
) -> QuotationOut:
    quotation = _get_quotation(db, principal, quotation_id)  # 404 if not visible to this user
    ...
    audit.record(db, request, "quotation.approve", actor=principal, target_type="quotation", target_id=quotation.id)
    db.commit()
    return QuotationOut.model_validate(quotation)
```

Route functions are plain `def` (FastAPI runs them in a thread pool), because Argon2 and SQLAlchemy here are synchronous.

## 10. Frontend usage

- Every call goes through `api.get/post/patch/put/delete` in `src/lib/api.ts` (CSRF, errors, 401 handling). Components never call `fetch` with hand-written URLs.
- Response types live in `src/features/<feature>/types.ts` (shared ones in `src/lib/types.ts`) and mirror the feature's `schemas.py`; update both in the same change.
- Data loading uses `useResource`; dropdowns of another page's data use `useLookup`.

## 11. Quick reference

```
GET    /api/orders?state=open&sort=-created_at&page=1&page_size=25
GET    /api/orders/{order_id}
POST   /api/orders                         201
PATCH  /api/orders/{order_id}
DELETE /api/orders/{order_id}              204
POST   /api/orders/{order_id}/cancel
GET    /api/orders/{order_id}/items
GET    /api/lookups/customers?q=sha&limit=20
GET    /api/me
POST   /api/auth/login
```

## 12. Pre-completion checklist

- [ ] Under `/api/`, plural kebab-case resource, verbs only as action sub-paths, at most one nesting level.
- [ ] Right method and status code (section 2); DELETE returns 204; 404 (not 403) for records the user may not see.
- [ ] snake_case parameters and JSON keys; UUIDs for user-facing records.
- [ ] UTC ISO timestamps; money in minor units + currency.
- [ ] Lists paginated with a server-enforced maximum; sort/filter fields allowlisted.
- [ ] Errors use `{"detail": …}` with user-safe text or an existing stable code.
- [ ] File, handler, schema and screen-key names follow section 9.
- [ ] `response_model`, `status_code` and a permission dependency are declared.
- [ ] `src/lib/types.ts` updated; frontend calls go through `src/lib/api.ts`.
- [ ] No breaking change to an existing contract, or it is called out explicitly.
