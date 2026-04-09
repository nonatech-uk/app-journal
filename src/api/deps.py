"""Connection pool, auth dependencies."""

from fastapi import Depends, HTTPException

from mees_shared.db import get_conn, init_pool as _init_pool, close_pool  # noqa: F401
from mees_shared.auth import CurrentUser, get_current_user as _make_get_user  # noqa: F401

from config.settings import settings

# App-specific auth dependency
get_current_user = _make_get_user(settings.auth_enabled, settings.dev_user_email)


def init_pool() -> None:
    _init_pool(settings.dsn, settings.db_pool_min, settings.db_pool_max)


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(403, "Admin access required")
    return user
