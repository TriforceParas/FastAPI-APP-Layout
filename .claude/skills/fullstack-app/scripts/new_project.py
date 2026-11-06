#!/usr/bin/env python3
"""Scaffold a new project from this repository (the FastAPI + React template).

    new_project.py <dest_dir> --name "Acme Ops" [--tagline "Field operations"]
                   [--service acme] [--no-install] [--no-git]

- Copies this repo, minus local-only files (never overwrites a non-empty directory).
- Sets APP_NAME / APP_TAGLINE in .env, the HTML title, the npm package name
  and the docker-compose service / deploy-workflow paths.
- Creates a venv (outside the project if the target filesystem can't hold
  symlinks, e.g. NTFS), installs Python + npm deps, builds the UI, runs tests.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# .claude/skills/fullstack-app/scripts/new_project.py -> repo root
TEMPLATE = Path(__file__).resolve().parents[4]

# Local state, secrets and build output never go into a new project.
EXCLUDE = shutil.ignore_patterns(
    ".git",
    "node_modules",
    "dist",
    "data",
    ".env",
    ".auth-bypass",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "*.tsbuildinfo",
    "settings.local.json",
)


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "app"


def replace_in(path: Path, old: str, new: str, count: int = 0) -> None:
    text = path.read_text()
    if old not in text:
        return
    path.write_text(text.replace(old, new) if count == 0 else text.replace(old, new, count))


def supports_symlinks(directory: Path) -> bool:
    with tempfile.TemporaryDirectory(dir=directory) as tmp:
        try:
            os.symlink("target", Path(tmp) / "link")
            return True
        except OSError:
            return False


def run(cmd: list[str], cwd: Path) -> None:
    print(f"» {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dest")
    parser.add_argument("--name", required=True, help="product name shown in the UI")
    parser.add_argument("--tagline", default="Operations dashboard")
    parser.add_argument("--service", help="compose service / server folder name (default: slug of name)")
    parser.add_argument("--no-install", action="store_true", help="skip venv, npm install, build and tests")
    parser.add_argument("--no-git", action="store_true")
    args = parser.parse_args()

    dest = Path(args.dest).expanduser().resolve()
    if dest.exists() and any(dest.iterdir()):
        sys.exit(f"Refusing to overwrite non-empty directory: {dest}")
    if not (TEMPLATE / "main.py").is_file() or not (TEMPLATE / "frontend/src").is_dir():
        sys.exit(f"Template not found at {TEMPLATE}")
    if dest == TEMPLATE or TEMPLATE in dest.parents:
        sys.exit("Destination must be outside the template repository")

    slug = slugify(args.name)
    service = slugify(args.service or args.name)
    shutil.copytree(TEMPLATE, dest, dirs_exist_ok=True, ignore=EXCLUDE)

    # --- Personalise ----------------------------------------------------------
    env = (dest / ".env.example").read_text()
    env = re.sub(r"^APP_NAME=.*$", f"APP_NAME={args.name}", env, flags=re.M)
    env = re.sub(r"^APP_TAGLINE=.*$", f"APP_TAGLINE={args.tagline}", env, flags=re.M)
    (dest / ".env.example").write_text(env)
    (dest / ".env").write_text(env)

    replace_in(dest / "frontend/index.html", "<title>Workspace</title>", f"<title>{args.name}</title>")
    replace_in(dest / "frontend/package.json", '"name": "app-frontend"', f'"name": "{slug}-frontend"')
    replace_in(dest / "frontend/package-lock.json", '"name": "app-frontend"', f'"name": "{slug}-frontend"', count=2)
    replace_in(dest / "app/core/config.py", 'app_name: str = "Workspace"', f'app_name: str = "{args.name}"')
    replace_in(
        dest / "app/core/config.py", 'app_tagline: str = "Operations dashboard"', f'app_tagline: str = "{args.tagline}"'
    )
    for wf in ("test-deploy.yml", "prod-deploy.yml"):
        p = dest / ".github/workflows" / wf
        text = p.read_text()
        text = re.sub(r"/opt/app/(test|prod)/app\b", rf"/opt/app/\1/{service}", text)
        text = text.replace("--build app", f"--build {service}")
        text = text.replace('# Change "app" to this service\'s folder / compose service name.\n', "")
        p.write_text(text)
    compose = dest / "docker-compose.example.yml"  # optional: only if the template still ships one
    if compose.is_file():
        compose.write_text(
            compose.read_text()
            .replace("  app:\n", f"  {service}:\n")
            .replace("./app", f"./{service}")
            .replace("app-data", f"{service}-data")
        )
    replace_in(dest / "README.md", "# App template: FastAPI + React, no Node at runtime", f"# {args.name}")

    print(f"✓ Created {dest}  (service: {service})")

    if not args.no_git and shutil.which("git"):
        run(["git", "init", "-q", "-b", "main"], dest)

    if args.no_install:
        return

    # --- Install ----------------------------------------------------------------
    if supports_symlinks(dest):
        venv = dest / ".venv"
    else:
        venv = Path.home() / ".venvs" / slug
        print(f"! {dest} can't hold symlinks (NTFS/exFAT?) — using venv at {venv}")
    if shutil.which("uv"):
        run(["uv", "venv", "-q", str(venv)], dest)
        run(["uv", "pip", "install", "-q", "-r", "requirements-dev.txt", "--python", str(venv / "bin/python")], dest)
    else:
        run([sys.executable, "-m", "venv", str(venv)], dest)
        run([str(venv / "bin/pip"), "install", "-q", "-r", "requirements-dev.txt"], dest)

    npm = shutil.which("npm")
    if npm:
        run([npm, "ci", "--no-audit", "--no-fund"], dest / "frontend")
        run([npm, "run", "build"], dest / "frontend")
    else:
        print("! npm not found — install Node 20.19+ to build the UI")

    run([str(venv / "bin/python"), "-m", "pytest", "-q", "-p", "no:cacheprovider"], dest)
    shutil.rmtree(dest / "data", ignore_errors=True)  # tests/dev key; start clean

    print(
        f"\n✓ Ready.\n  cd {dest}\n  {venv}/bin/python main.py --dev    # http://127.0.0.1:8000\n"
        "  First visit shows the initial-registration screen."
    )


if __name__ == "__main__":
    main()
