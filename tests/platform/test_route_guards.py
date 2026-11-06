"""Fails if any API route can be reached without the right guard (fastapi-security §2).

Rules
  * /api/auth/* and /api/health/* are the only public routes.
  * /api/me and /api/me/* need a signed-in session (outside RBAC).
  * Everything else needs require_screen(...) or require_lookup(...).
  * A route that changes data (POST/PUT/PATCH/DELETE) guarded by a screen must
    require WRITE, not just read.
"""

from __future__ import annotations

from fastapi.routing import APIRoute

try:  # FastAPI >= 0.16x keeps included routers nested; this public helper flattens them.
    from fastapi.routing import iter_route_contexts
except ImportError:  # older FastAPI flattens app.routes itself
    iter_route_contexts = None

PUBLIC_PREFIXES = ("/api/auth/", "/api/health/")
SESSION_PREFIXES = ("/api/me",)
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


def guards(route: APIRoute) -> list[dict]:
    """All guard markers in the route's dependency tree."""
    found: list[dict] = []
    stack = list(route.dependant.dependencies)
    while stack:
        dep = stack.pop()
        marker = getattr(dep.call, "__rbac_guard__", None)
        if marker:
            found.append(marker)
        stack.extend(dep.dependencies)
    return found


def api_routes(app) -> list[tuple[str, set[str], APIRoute]]:
    """(effective path, methods, route) for every API route."""
    if iter_route_contexts is not None:
        items = [(c.path, set(c.methods or ()), c.route) for c in iter_route_contexts(app.routes)]
    else:
        items = [(r.path, set(r.methods), r) for r in app.routes]
    return [(path, methods, r) for path, methods, r in items if isinstance(r, APIRoute) and path.startswith("/api/")]


def test_there_are_routes_to_check(app):
    # Guards against the walker silently finding nothing (which would make the checks below pass vacuously).
    assert len(api_routes(app)) > 30


def test_every_route_has_the_right_guard(app):
    problems: list[str] = []
    for path, methods, route in api_routes(app):
        name = f"{','.join(sorted(methods))} {path}"
        found = guards(route)
        kinds = {g["kind"] for g in found}
        if path.startswith(PUBLIC_PREFIXES):
            continue
        if path == "/api/me" or path.startswith(tuple(p + "/" for p in SESSION_PREFIXES)):
            if not kinds & {"session", "user", "screen"}:
                problems.append(f"{name}: needs a signed-in session")
            continue
        if not kinds & {"screen", "lookup"}:
            problems.append(f"{name}: needs require_screen(...) or require_lookup(...)")
            continue
        if methods & UNSAFE:
            screen_guards = [g for g in found if g["kind"] == "screen"]
            if not any(g["write"] for g in screen_guards):
                problems.append(f"{name}: changes data but only requires READ")
    assert not problems, "Unguarded or under-guarded routes:\n" + "\n".join(problems)


def test_lookups_are_read_only(app):
    for path, methods, _ in api_routes(app):
        if path.startswith("/api/lookups/"):
            assert methods <= {"GET", "HEAD"}, path
