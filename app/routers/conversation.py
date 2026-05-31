"""Conversational AI endpoint (Bonus feature).

Supports multi-turn conversations where accountants can ask follow-up
questions — e.g. "give me all emails for Akshar from last month"
followed by "now summarise these". Session state is maintained via
a session_id returned in each response.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.dependencies import CurrentUser, DbSession
from app.services.conversation_service import chat

router = APIRouter(prefix="/api/chat", tags=["Conversational Interface"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Your question or instruction")
    session_id: str | None = Field(
        None,
        description="Include to continue a prior conversation. Omit to start a new one.",
    )


@router.post("")
async def chat_endpoint(
    body: ChatRequest,
    db: DbSession,
    user: CurrentUser,
):
    """Chat with your email data using natural language.

    Send a message and optionally include a session_id to continue
    a prior conversation. The AI remembers context within a session.

    Examples:
    - "give me all emails for Akshar from last month"
    - (follow-up with same session_id) "now summarise these"
    - "what are the open action items across all clients?"
    """
    if not body.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty",
        )

    try:
        return await chat(db, user.firm_id, body.message, body.session_id)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        )
