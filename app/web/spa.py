"""Serves the compiled React app (frontend/dist) from FastAPI, so the
deployed service needs no Node.js runtime."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope

log = logging.getLogger(__name__)

_NOT_BUILT = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Frontend not built</title></head><body>
<h1>Frontend has not been built</h1>
<p>Run <code>python main.py</code> (builds automatically) or
<code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code>.</p></body></html>"""


class ImmutableStaticFiles(StaticFiles):
    """Vite emits content-hashed file names under /assets, so they can be
    cached forever."""

    async def get_response(self, path: str, scope: Scope):  # type: ignore[no-untyped-def]
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def mount_frontend(app: FastAPI, dist: Path) -> None:
    dist = dist.resolve()
    index = dist / "index.html"

    if (dist / "assets").is_dir():
        app.mount("/assets", ImmutableStaticFiles(directory=dist / "assets"), name="assets")

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def spa(full_path: str):  # type: ignore[no-untyped-def]
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        if not index.is_file():
            return HTMLResponse(_NOT_BUILT, status_code=503)
        if full_path:
            candidate = (dist / full_path).resolve()
            # Only serve real files inside dist (blocks ../ traversal).
            if candidate.is_file() and candidate.is_relative_to(dist) and candidate != index:
                return FileResponse(candidate, headers={"Cache-Control": "public, max-age=3600"})
        # Client-side routes all resolve to index.html.
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
