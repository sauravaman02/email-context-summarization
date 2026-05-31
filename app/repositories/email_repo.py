"""Data access layer for Email entities.

Provides date-range filtering for summarisation and paginated listing
for the API. The (client_id, sent_at) index is leveraged by all queries.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Email


class EmailRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_for_client(
        self,
        client_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        skip: int = 0,
        limit: int | None = None,
    ) -> list[Email]:
        """Fetch emails for a client, optionally filtered by date range.

        Used by the summarisation engine to build the prompt payload.
        Results are ordered chronologically (oldest first) for coherent thread reading.
        """
        stmt = select(Email).where(Email.client_id == client_id)
        if start_date:
            stmt = stmt.where(Email.sent_at >= start_date)
        if end_date:
            stmt = stmt.where(Email.sent_at <= end_date)
        stmt = stmt.order_by(Email.sent_at.asc()).offset(skip)
        if limit:
            stmt = stmt.limit(limit)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def count_for_client(
        self,
        client_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> int:
        """Count emails matching the date filter (drives partial-refresh logic)."""
        stmt = (
            select(func.count()).select_from(Email).where(Email.client_id == client_id)
        )
        if start_date:
            stmt = stmt.where(Email.sent_at >= start_date)
        if end_date:
            stmt = stmt.where(Email.sent_at <= end_date)
        result = await self._db.execute(stmt)
        return result.scalar_one()

    async def list_paginated(
        self,
        client_id: UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Email], int]:
        """Paginated email list for the client detail view (newest first)."""
        count_result = await self._db.execute(
            select(func.count()).select_from(Email).where(Email.client_id == client_id)
        )
        total = count_result.scalar_one()

        result = await self._db.execute(
            select(Email)
            .where(Email.client_id == client_id)
            .order_by(Email.sent_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total
