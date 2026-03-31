"""Connection pool, auth dependencies."""

from collections.abc import Generator
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from psycopg2.pool import ThreadedConnectionPool

from config.settings import settings

pool: ThreadedConnectionPool | None = None


def init_pool() -> None:
    global pool
    pool = ThreadedConnectionPool(
        settings.db_pool_min,
        settings.db_pool_max,
        settings.dsn,
    )


def close_pool() -> None:
    global pool
    if pool:
        pool.closeall()
        pool = None


def get_conn() -> Generator:
    assert pool is not None, "Connection pool not initialised"
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)


@dataclass
class CurrentUser:
    email: str
    display_name: str
    role: str  # admin | readonly


def get_current_user(request: Request, conn=Depends(get_conn)) -> CurrentUser:
    if not settings.auth_enabled:
        email = settings.dev_user_email
    else:
        email = request.headers.get("Remote-Email")
        if not email:
            raise HTTPException(401, "Not authenticated")

    cur = conn.cursor()
    cur.execute(
        "SELECT email, display_name, role FROM app_user WHERE email = %s",
        (email,),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(403, f"User {email} is not authorised")

    display_name_header = request.headers.get("Remote-Name")
    return CurrentUser(
        email=row[0],
        display_name=display_name_header or row[1],
        role=row[2],
    )


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(403, "Admin access required")
    return user
