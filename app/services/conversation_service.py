"""Conversational AI interface for querying email data (Bonus feature).

Maintains per-session conversation history so accountants can ask
follow-up questions naturally — e.g. "give me all emails for Akshar
from last month" followed by "now summarise these".

Sessions are stored in-memory. For production, swap to Redis-backed
session storage for persistence across restarts and horizontal scaling.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from uuid import UUID

from google import genai
from google.genai import types
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repositories.client_repo import ClientRepository
from app.repositories.email_repo import EmailRepository

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """You are an AI assistant for a CPA (accounting) firm. You help accountants find and understand emails from their clients.

You have access to the firm's email database. When the user asks about emails, clients, or tax matters, answer based on the provided email data.

Available capabilities:
- Find emails for a specific client
- Filter emails by date range
- Summarize email threads
- Answer questions about the content of emails
- Compare discussions across clients

When referencing emails, mention the client name, subject, and date.
If asked to summarize, provide: actors involved, concluded discussions, and open action items.
Always be concise and professional."""

MAX_HISTORY_TURNS = 10


class ConversationSession:
    """Holds the message history for a single conversation."""

    def __init__(self, session_id: str, firm_id: UUID):
        self.session_id = session_id
        self.firm_id = firm_id
        self.history: list[dict] = []
        self.created_at = datetime.now(timezone.utc)


_sessions: dict[str, ConversationSession] = {}


def get_or_create_session(session_id: str | None, firm_id: UUID) -> ConversationSession:
    """Retrieve an existing session or create a new one."""
    if session_id and session_id in _sessions:
        return _sessions[session_id]
    new_id = session_id or str(uuid.uuid4())[:8]
    session = ConversationSession(new_id, firm_id)
    _sessions[new_id] = session
    return session


async def _build_context(db: AsyncSession, firm_id: UUID) -> str:
    """Build a context string with all client emails for the firm."""
    client_repo = ClientRepository(db)
    email_repo = EmailRepository(db)

    clients, _ = await client_repo.list_by_firm(firm_id, skip=0, limit=200)

    blocks: list[str] = []
    for client in clients:
        emails = await email_repo.get_for_client(client.id, limit=50)
        if not emails:
            continue

        email_lines = []
        for e in emails:
            email_lines.append(
                f"- From: {e.sender_name} | To: {', '.join(r.get('name', '') for r in e.recipients)} "
                f"| Date: {e.sent_at.strftime('%Y-%m-%d') if e.sent_at else '?'} "
                f"| Subject: {e.subject}\n  {e.body[:400]}"
            )

        blocks.append(
            f"CLIENT: {client.name} ({client.email})\n" + "\n".join(email_lines)
        )

    return "\n\n---\n\n".join(blocks) if blocks else "No emails found."


async def chat(
    db: AsyncSession,
    firm_id: UUID,
    message: str,
    session_id: str | None = None,
) -> dict:
    """Process a conversational message, maintaining session history.

    Returns a dict with session_id, response text, token usage, and turn number.
    The session_id should be sent back on subsequent requests to continue the conversation.
    """
    session = get_or_create_session(session_id, firm_id)
    email_context = await _build_context(db, firm_id)

    session.history.append({"role": "user", "content": message})

    # Include recent conversation history for multi-turn context
    history_text = ""
    if len(session.history) > 1:
        earlier = session.history[:-1]
        history_text = "\n\nPrevious conversation:\n" + "\n".join(
            f"{'User' if h['role'] == 'user' else 'Assistant'}: {h['content']}"
            for h in earlier[-MAX_HISTORY_TURNS:]
        )

    prompt = (
        f"{SYSTEM_INSTRUCTION}\n\n"
        f"Email Database:\n{email_context}\n"
        f"{history_text}\n\n"
        f"User: {message}\n\n"
        f"Respond helpfully and concisely. If asked to summarize, use structured format with "
        f"Actors, Concluded Discussions, and Open Action Items."
    )

    client_ai = genai.Client(api_key=settings.gemini_api_key)

    try:
        response = await asyncio.to_thread(
            client_ai.models.generate_content,
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.3),
        )

        answer = response.text.strip()

        input_tokens = 0
        output_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            input_tokens = (
                getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            )
            output_tokens = (
                getattr(response.usage_metadata, "candidates_token_count", 0) or 0
            )

        session.history.append({"role": "assistant", "content": answer})

        return {
            "session_id": session.session_id,
            "response": answer,
            "tokens": {"input": input_tokens, "output": output_tokens},
            "turn": len(session.history) // 2,
        }

    except Exception as exc:
        logger.error("Conversation failed: %s", exc)
        raise RuntimeError(f"Conversation service unavailable: {exc}") from exc
