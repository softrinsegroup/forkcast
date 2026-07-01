from fastapi import APIRouter

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/chat")
async def chat_stream():
    pass
