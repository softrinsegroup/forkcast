import os
import secrets
from urllib.parse import urlencode
from fastapi import APIRouter, HTTPException, Request
from fastapi.routing import RedirectResponse
import httpx
import structlog

from models import UserCreate
from storage import UserStore

log = structlog.get_logger()

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")


@router.get("/google")
async def google_login(request: Request):
    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(url)


@router.get("/google/callback")
async def google_callback(request: Request, code: str, state: str):
    # Check for CSRF attacks on state
    if state != request.session.pop("oauth_state", None):
        raise HTTPException(status_code=400, detail="Invalid state")

    async with httpx.AsyncClient() as client:
        # Exchange code for tokens
        token_res = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        # Raise error if Google OAuth returned 4xx/5xx
        token_res.raise_for_status()
        tokens = token_res.json()

        # Fetch profile
        user_res = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        user = user_res.json()

        # Create/update user
        google_sub = user["sub"]
        user_store: UserStore = request.app.state.user_store
        existing_user = await user_store.get_by_google_sub(google_sub)
        if not existing_user:
            user_id = await user_store.create(
                UserCreate(
                    name=user["name"], email=user["email"], google_sub=google_sub
                )
            )
        else:
            existing_user.name = user["name"]
            existing_user.email = user["email"]
            await user_store.update(existing_user)
            user_id = existing_user.id

        # Store user_id in session
        request.session["user_id"] = str(user_id)
        log.info("user_logged_in", user_id=str(user_id))

        return RedirectResponse("/")


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")
