"""Data access layer for EmailSummary entities.

Handles upsert (create-or-update) for the one-summary-per-client model,
and aggregation queries for firm-level and global admin reports.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Client, EmailSummary, Firm


class SummaryRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_client_id(self, client_id: UUID) -> EmailSummary | None:
        """Fetch the latest summary for a client, if one exists."""
        result = await self._db.execute(
            select(EmailSummary).where(EmailSummary.client_id == client_id)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        client_id: UUID,
        encrypted_summary: str,
        emails_analysed_count: int,
        last_refreshed_at: datetime,
        input_tokens: int,
        output_tokens: int,
        date_range_start: datetime | None,
        date_range_end: datetime | None,
    ) -> EmailSummary:
        """Create or update the summary for a client.

        Uses SELECT-then-UPDATE rather than database-specific UPSERT
        for portability across SQLite and PostgreSQL.
        """
        existing = await self.get_by_client_id(client_id)
        if existing:
            existing.encrypted_summary = encrypted_summary
            existing.emails_analysed_count = emails_analysed_count
            existing.last_refreshed_at = last_refreshed_at
            existing.input_tokens = input_tokens
            existing.output_tokens = output_tokens
            existing.date_range_start = date_range_start
            existing.date_range_end = date_range_end
            self._db.add(existing)
            await self._db.flush()
            return existing

        summary = EmailSummary(
            client_id=client_id,
            encrypted_summary=encrypted_summary,
            emails_analysed_count=emails_analysed_count,
            last_refreshed_at=last_refreshed_at,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
        )
        self._db.add(summary)
        await self._db.flush()
        return summary

    async def get_tracking_for_firm(self, firm_id: UUID) -> list[dict]:
        """Per-client summary tracking data for the firm admin report."""
        result = await self._db.execute(
            select(
                EmailSummary.client_id,
                Client.name.label("client_name"),
                EmailSummary.emails_analysed_count,
                EmailSummary.last_refreshed_at,
                EmailSummary.input_tokens,
                EmailSummary.output_tokens,
            )
            .join(Client, Client.id == EmailSummary.client_id)
            .where(Client.firm_id == firm_id)
            .order_by(Client.name)
        )
        return [row._asdict() for row in result.all()]

    async def get_global_report(self) -> list[dict]:
        """Cross-firm summary counts for the superuser global report."""
        result = await self._db.execute(
            select(
                Firm.id.label("firm_id"),
                Firm.name.label("firm_name"),
                func.count(func.distinct(Client.id)).label("total_clients"),
                func.count(func.distinct(EmailSummary.id)).label("clients_with_summaries"),
            )
            .select_from(Firm)
            .outerjoin(Client, Client.firm_id == Firm.id)
            .outerjoin(EmailSummary, EmailSummary.client_id == Client.id)
            .group_by(Firm.id, Firm.name)
            .order_by(Firm.name)
        )
        return [row._asdict() for row in result.all()]
