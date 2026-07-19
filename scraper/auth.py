import os
import secrets

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials

_security = HTTPBasic()


async def require_dashboard_auth(
    credentials: HTTPBasicCredentials = Depends(_security),
) -> None:
    """
    HTTP Basic auth for everything except /healthcheck. Any username; the
    password must match DASHBOARD_PASSWORD. 503 when unset — fail loud,
    never open (same convention as the backend's ingest key).
    """
    password = os.getenv("DASHBOARD_PASSWORD")
    if not password:
        raise HTTPException(status_code=503, detail="Dashboard auth not configured")
    if not secrets.compare_digest(credentials.password, password):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
