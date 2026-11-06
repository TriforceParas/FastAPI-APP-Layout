"""Mounts every API router under /api. Register new feature routers here."""

from __future__ import annotations

from fastapi import APIRouter

from app.features.account import router as me
from app.features.audit import router as audit
from app.features.auth import microsoft as microsoft_sso
from app.features.auth import router as auth
from app.features.dashboard import router as dashboard
from app.features.lookups import router as lookups
from app.features.mfa import router as mfa
from app.features.rbac import router as roles
from app.features.system import router as health
from app.features.users import router as users

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(microsoft_sso.router)
api_router.include_router(me.router)
api_router.include_router(mfa.router)
api_router.include_router(users.router)
api_router.include_router(roles.router)
api_router.include_router(lookups.router)
api_router.include_router(audit.router)
api_router.include_router(dashboard.router)
