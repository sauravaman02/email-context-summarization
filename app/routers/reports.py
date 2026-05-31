"""Admin and superuser reporting endpoints.

Firm admins see summary coverage within their firm.
Superusers see a global cross-firm overview.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.dependencies import DbSession, require_role
from app.models import Firm
from app.repositories.client_repo import ClientRepository
from app.repositories.summary_repo import SummaryRepository
from app.schemas import (
    AccountantInfo,
    FirmReportResponse,
    GlobalFirmSummary,
    GlobalReportResponse,
    SummaryTrackingInfo,
)

router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get("/firm", response_model=FirmReportResponse)
async def firm_report(
    db: DbSession,
    user: Annotated[AccountantInfo, Depends(require_role("firm_admin", "superuser"))],
):
    """Firm admin report: total clients and how many have generated summaries.

    Includes per-client tracking data (emails analysed, last refresh, token usage).
    """
    client_repo = ClientRepository(db)
    summary_repo = SummaryRepository(db)

    total_clients = await client_repo.count_by_firm(user.firm_id)
    clients_with_summaries = await client_repo.count_with_summaries(user.firm_id)
    tracking = await summary_repo.get_tracking_for_firm(user.firm_id)

    result = await db.execute(select(Firm.name).where(Firm.id == user.firm_id))
    firm_name = result.scalar_one_or_none() or "Unknown"

    return FirmReportResponse(
        firm_id=user.firm_id,
        firm_name=firm_name,
        total_clients=total_clients,
        clients_with_summaries=clients_with_summaries,
        summaries=[SummaryTrackingInfo(**t) for t in tracking],
    )


@router.get("/global", response_model=GlobalReportResponse)
async def global_report(
    db: DbSession,
    user: Annotated[AccountantInfo, Depends(require_role("superuser"))],
):
    """Superuser report: summary coverage across all firms, grouped by firm."""
    summary_repo = SummaryRepository(db)
    rows = await summary_repo.get_global_report()

    firms = [GlobalFirmSummary(**r) for r in rows]
    return GlobalReportResponse(total_firms=len(firms), firms=firms)
