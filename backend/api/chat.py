import json
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from api.deps import get_current_user
from models import User


router = APIRouter(prefix="/chat", tags=["chat"])


def _chunk_text(content) -> str:
    """Extract streamed text from an AIMessageChunk's content.

    With tools bound, ChatAnthropic returns content as a list of block dicts
    (text and tool_use) rather than a plain string; concatenate the text ones.
    """
    if isinstance(content, str):
        return content
    return "".join(
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )


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
                    text = _chunk_text(event["data"]["chunk"].content)
                    if text:
                        yield f"data: {json.dumps({'type': 'token', 'content': text})}\n\n"

            new_snapshot = await graph.aget_state(config)
            for task in new_snapshot.tasks:
                for interrupt_obj in task.interrupts:
                    yield f"event: interrupt\ndata: {json.dumps({'value': interrupt_obj.value})}\n\n"

            yield "event: done\ndata: {}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
