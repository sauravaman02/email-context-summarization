"""Natural language search endpoint (Bonus feature).

Allows accountants to search across all their firm's client emails
using free-text queries — powered by Gemini AI.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.dependencies import CurrentUser, DbSession
from app.services.search_service import search_emails

router = APIRouter(prefix="/api/search", tags=["Search"])


class SearchRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        description="Natural language search query",
        json_schema_extra={"examples": ["clients who had issues with their 1099-INT filing"]},
    )


@router.post("")
async def natural_language_search(
    body: SearchRequest,
    db: DbSession,
    user: CurrentUser,
):
    """Search across all client emails using natural language.

    Examples:
    - "show me all clients who had issues with their 1099-INT filing"
    - "which clients are waiting on documents?"
    - "find emails about cryptocurrency"
    """
    if not body.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query cannot be empty",
        )

    try:
        return await search_emails(db, user.firm_id, body.query)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        )
