from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/google")
async def google_login():
    pass


@router.get("/google/callback")
async def google_callback():
    pass
