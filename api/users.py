from fastapi import APIRouter, Depends

from api.deps import get_current_user
from models import User

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {"user": user}
