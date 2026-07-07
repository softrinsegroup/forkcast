from uuid import UUID
from fastapi import HTTPException, Request


async def get_current_user(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_store = request.app.state.user_store
    user = await user_store.get(UUID(user_id))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user
