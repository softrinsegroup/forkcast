import json
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from api.deps import get_current_user
from models import User


router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/stream")
async def chat_stream(
    request: Request, message: str, user: User = Depends(get_current_user)
):
    graph = request.app.state.graph
    config = {"configurable": {"thread_id": str(user.id)}}
    snapshot = await graph.aget_state(config)

    # Handles new message or resuming an interrupt
    invocation = (
        Command(resume=message)
        if snapshot.next
        else {
            "user_id": str(user.id),
            "messages": [HumanMessage(message)],
            "user_message": message,
        }
    )

    # Generate the token stream
    async def generate():
        try:
            async for event in graph.astream_events(
                invocation, config=config, version="v2"
            ):
                if event["event"] == "on_chat_model_stream":
                    chunk = event["data"]["chunk"].content
                    if chunk:
                        yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

            new_snapshot = await graph.aget_state(config)
            for task in new_snapshot.tasks:
                for interrupt_obj in task.interrupts:
                    yield f"event: interrupt\ndata: {json.dumps({'value': interrupt_obj.value})}\n\n"

            yield "event: done\ndata: {}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
