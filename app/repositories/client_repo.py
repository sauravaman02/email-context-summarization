"""Data access layer for Client entities.

All queries are firm-scoped to enforce multi-tenancy — an accountant
at Firm A can never access Firm B's clients through this repository.
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Client, Email, EmailSummary


class ClientRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, client_id: UUID, firm_id: UUID) -> Client | None:
        """Fetch a single client, scoped to the given firm."""
        result = await self._db.execute(
            select(Client).where(Client.id == client_id, Client.firm_id == firm_id)
        )
        return result.scalar_one_or_none()

    async def list_by_firm(
        self, firm_id: UUID, skip: int = 0, limit: int = 50
    ) -> tuple[list[Client], int]:
        """Return a paginated list of clients for a firm, ordered by name."""
        count_result = await self._db.execute(
            select(func.count()).select_from(Client).where(Client.firm_id == firm_id)
        )
        total = count_result.scalar_one()

        result = await self._db.execute(
            select(Client)
            .where(Client.firm_id == firm_id)
            .order_by(Client.name)
            .offset(skip)
            .limit(limit)
        )
        clients = list(result.scalars().all())
        return clients, total

    async def get_email_count(self, client_id: UUID) -> int:
        """Count total emails for a client (used for dashboard cards)."""
        result = await self._db.execute(
            select(func.count()).select_from(Email).where(Email.client_id == client_id)
        )
        return result.scalar_one()

    async def count_by_firm(self, firm_id: UUID) -> int:
        """Total number of clients in a firm (for admin reports)."""
        result = await self._db.execute(
            select(func.count()).select_from(Client).where(Client.firm_id == firm_id)
        )
        return result.scalar_one()

    async def count_with_summaries(self, firm_id: UUID) -> int:
        """Count clients that have at least one generated summary."""
        result = await self._db.execute(
            select(func.count())
            .select_from(EmailSummary)
            .join(Client, Client.id == EmailSummary.client_id)
            .where(Client.firm_id == firm_id)
        )
        return result.scalar_one()
