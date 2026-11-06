"""Entry point.

    python main.py            build the UI if it is stale, then serve app + UI
    python main.py --dev      same, plus auto-reload (Python) and rebuild-on-save (UI)
    uvicorn main:app          serve only (what the Docker image runs)

There is never a Node.js server: the React UI is compiled to static files in
frontend/dist and FastAPI serves them alongside /api.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from app.main import create_app

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
DIST_INDEX = FRONTEND / "dist" / "index.html"
UI_SOURCES = ("src", "public", "index.html", "package.json", "vite.config.ts", "tsconfig.json")

app = create_app()


def _newest_mtime(paths: list[Path]) -> float:
    newest = 0.0
    for path in paths:
        if path.is_file():
            newest = max(newest, path.stat().st_mtime)
        elif path.is_dir():
            for child in path.rglob("*"):
                if child.is_file():
                    newest = max(newest, child.stat().st_mtime)
    return newest


def _npm() -> str | None:
    return shutil.which("npm")


def _ensure_node_modules(npm: str) -> None:
    if (FRONTEND / "node_modules").is_dir():
        return
    lock = (FRONTEND / "package-lock.json").is_file()
    print("» Installing frontend dependencies…", flush=True)
    subprocess.run([npm, "ci" if lock else "install"], cwd=FRONTEND, check=True)


def build_frontend(force: bool = False) -> None:
    stale = (
        force
        or not DIST_INDEX.is_file()
        or (_newest_mtime([FRONTEND / p for p in UI_SOURCES]) > DIST_INDEX.stat().st_mtime)
    )
    if not stale:
        print("» Frontend build is up to date.", flush=True)
        return
    npm = _npm()
    if npm is None:
        if DIST_INDEX.is_file():
            print("» npm not found; serving the existing (possibly stale) frontend build.", flush=True)
            return
        sys.exit("npm is required to build the frontend the first time (frontend/dist is missing).")
    _ensure_node_modules(npm)
    print("» Building frontend…", flush=True)
    subprocess.run([npm, "run", "build"], cwd=FRONTEND, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dev", action="store_true", help="auto-reload backend and rebuild UI on save")
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    parser.add_argument("--skip-build", action="store_true", help="do not build the frontend")
    parser.add_argument("--rebuild", action="store_true", help="force a frontend rebuild")
    args = parser.parse_args()

    if not args.skip_build:
        build_frontend(force=args.rebuild)

    import uvicorn

    watcher: subprocess.Popen[bytes] | None = None
    if args.dev and (npm := _npm()):
        watcher = subprocess.Popen([npm, "run", "watch"], cwd=FRONTEND)
    try:
        uvicorn.run(
            "main:app",
            host=args.host,
            port=args.port,
            reload=args.dev,
            reload_dirs=[str(ROOT / "app")] if args.dev else None,
            server_header=False,
            access_log=False,  # app.middleware.access_log logs requests (with request ids)
            proxy_headers=True,
        )
    finally:
        if watcher:
            watcher.terminate()


if __name__ == "__main__":
    main()
