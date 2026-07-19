import os
import secrets
from uuid import UUID
from fastapi import HTTPException, Request
import structlog

from storage import UserStore


async def get_current_user(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_store: UserStore = request.app.state.user_store
    user = await user_store.get(UUID(user_id))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Bind user_id to the logging context so every log line in this request
    # carries it. Propagates because RequestLoggingMiddleware is raw ASGI.
    structlog.contextvars.bind_contextvars(user_id=user_id)

    return user


async def require_ingest_key(request: Request) -> None:
    """
    Auth for machine clients (the scraper service) via static bearer token.
    Session cookies don't work outside a browser, so /recipes/ingest and
    /recipes/parse use `Authorization: Bearer <INGEST_API_KEY>` instead.
    """
    api_key = os.getenv("INGEST_API_KEY")
    if not api_key:
        # Fail loud: the endpoint is disabled until the key is configured.
        raise HTTPException(status_code=503, detail="Ingest not configured")

    auth = request.headers.get("Authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(token, api_key):
        raise HTTPException(status_code=401, detail="Invalid ingest key")
