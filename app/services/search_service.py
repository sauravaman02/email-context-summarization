"""Natural language search across client email threads (Bonus feature).

Uses Gemini to interpret a free-text query and match it against all
emails within the authenticated user's firm. Returns matching clients,
relevant email IDs, and highlighted excerpts.
"""

import asyncio
import json
import logging
from uuid import UUID

from google import genai
from google.genai import types
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repositories.client_repo import ClientRepository
from app.repositories.email_repo import EmailRepository

logger = logging.getLogger(__name__)

SEARCH_PROMPT = """You are a search engine for a CPA firm's email database.
Given a natural language query and a list of client email threads, find ALL clients and emails that match the query.

Query: "{query}"

Clients and their emails:
---
{client_emails}
---

Return a JSON object with this structure:
{{
  "results": [
    {{
      "client_id": "<uuid>",
      "client_name": "<name>",
      "relevance": "<one-sentence explanation of why this client matches>",
      "matching_email_ids": ["<uuid>", ...],
      "highlight": "<short quote or summary from the matching emails>"
    }}
  ],
  "interpretation": "<how you interpreted the query>"
}}

Rules:
- Only include clients whose emails genuinely match the query intent.
- If no clients match, return an empty "results" array.
- Be precise — don't stretch matches.

Respond ONLY with valid JSON. No markdown fences, no explanation."""


def _build_search_context(clients_with_emails: list[tuple]) -> str:
    """Format client/email data into a text block for the search prompt."""
    blocks: list[str] = []
    for client, emails in clients_with_emails:
        email_texts = []
        for e in emails:
            email_texts.append(
                f"  EmailID: {e.id}\n"
                f"  From: {e.sender_name} <{e.sender_email}>\n"
                f"  Subject: {e.subject}\n"
                f"  Date: {e.sent_at.isoformat() if e.sent_at else ''}\n"
                f"  Body: {e.body[:500]}\n"
            )
        blocks.append(
            f"ClientID: {client.id}\n"
            f"ClientName: {client.name}\n"
            f"Emails:\n" + "\n  ---\n".join(email_texts)
        )
    return "\n\n===\n\n".join(blocks)


async def search_emails(
    db: AsyncSession,
    firm_id: UUID,
    query: str,
) -> dict:
    """Search across all client emails in a firm using natural language.

    Returns a dict with 'results' (matching clients), 'interpretation'
    (how the AI understood the query), and 'tokens' (usage stats).
    """
    client_repo = ClientRepository(db)
    email_repo = EmailRepository(db)

    clients, _ = await client_repo.list_by_firm(firm_id, skip=0, limit=200)

    clients_with_emails = []
    for client in clients:
        emails = await email_repo.get_for_client(client.id, limit=50)
        if emails:
            clients_with_emails.append((client, emails))

    if not clients_with_emails:
        return {"results": [], "interpretation": "No emails found in your firm"}

    formatted = _build_search_context(clients_with_emails)
    prompt = SEARCH_PROMPT.format(query=query, client_emails=formatted)

    client_ai = genai.Client(api_key=settings.gemini_api_key)

    try:
        response = await asyncio.to_thread(
            client_ai.models.generate_content,
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )

        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3].strip()

        result = json.loads(text)

        input_tokens = 0
        output_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

        result["tokens"] = {"input": input_tokens, "output": output_tokens}
        return result

    except json.JSONDecodeError as exc:
        logger.error("Failed to parse Gemini search response as JSON: %s", exc)
        raise RuntimeError("Search returned invalid response format") from exc
    except Exception as exc:
        logger.error("Search failed: %s", exc)
        raise RuntimeError(f"Search service unavailable: {exc}") from exc
