"""Application errors that are independent of FastAPI.

Services and integrations raise these (they must not import FastAPI); the
handler registered in app.main turns them into `{"detail": "..."}` responses.
Routers may raise them too, or `fastapi.HTTPException`, with the same result.

    raise NotFound("Order not found.")
    raise Conflict("This quotation has already been approved.")
    raise ServiceUnavailable("Payment provider unavailable. Please try again.")

`detail` is shown to end users: write a short, actionable sentence and never
include internals (ids, SQL, exception text, library names).
"""

from __future__ import annotations


class AppError(Exception):
    status_code = 400

    def __init__(self, detail: str, *, headers: dict[str, str] | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.headers = headers


class BadRequest(AppError):
    status_code = 400


class Unauthorized(AppError):
    status_code = 401


class Forbidden(AppError):
    status_code = 403


class NotFound(AppError):
    status_code = 404


class Conflict(AppError):
    status_code = 409


class Unprocessable(AppError):
    status_code = 422


class TooManyRequests(AppError):
    status_code = 429


class ServiceUnavailable(AppError):
    status_code = 503
