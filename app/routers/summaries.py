"""Email summarisation endpoints.

Two endpoints:
  - POST /summary       → uses cache + partial-refresh (cost-efficient)
  - POST /summary/refresh → bypasses both (force fresh analysis)
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.dependencies import CurrentUser, DbSession
from app.repositories.client_repo import ClientRepository
from app.schemas import SummaryRequest, SummaryResponse
from app.services.summarization_service import SummarizationService

router = APIRouter(prefix="/api/clients", tags=["Summaries"])


@router.post("/{client_id}/summary", response_model=SummaryResponse)
async def get_summary(
    client_id: UUID,
    db: DbSession,
    user: CurrentUser,
    body: SummaryRequest | None = None,
):
    """Generate or retrieve a cached summary for a client's email thread.

    Accepts optional start_date/end_date for filtering. If fewer than 5 new
    emails have arrived since the last analysis, returns the existing summary
    with skipped=true and a reason explaining why.
    """
    client_repo = ClientRepository(db)
    client = await client_repo.get_by_id(client_id, user.firm_id)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found or does not belong to your firm",
        )

    start_date = body.start_date if body else None
    end_date = body.end_date if body else None

    try:
        service = SummarizationService(db)
        return await service.get_or_create_summary(
            client_id=client_id,
            firm_id=user.firm_id,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Summarization service unavailable: {exc}",
        )


@router.post("/{client_id}/summary/refresh", response_model=SummaryResponse)
async def refresh_summary(
    client_id: UUID,
    db: DbSession,
    user: CurrentUser,
    body: SummaryRequest | None = None,
):
    """Force a fresh summarisation, bypassing cache and partial-refresh skip logic.

    Use this when you need the absolute latest analysis regardless of
    how many new emails have arrived.
    """
    client_repo = ClientRepository(db)
    client = await client_repo.get_by_id(client_id, user.firm_id)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found or does not belong to your firm",
        )

    start_date = body.start_date if body else None
    end_date = body.end_date if body else None

    try:
        service = SummarizationService(db)
        return await service.get_or_create_summary(
            client_id=client_id,
            firm_id=user.firm_id,
            start_date=start_date,
            end_date=end_date,
            force_refresh=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Summarization service unavailable: {exc}",
        )
