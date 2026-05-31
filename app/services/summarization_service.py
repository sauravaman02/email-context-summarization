"""Core summarisation orchestrator.

Coordinates the full summary lifecycle:
  1. Check cache for a recent result
  2. Apply partial-refresh logic (skip if < N new emails)
  3. Fetch emails, call Gemini, encrypt the result
  4. Persist to DB and update cache

Resilience guarantee: an existing summary is NEVER overwritten unless
a new Gemini response is successfully received and parsed.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repositories.email_repo import EmailRepository
from app.repositories.summary_repo import SummaryRepository
from app.schemas import SummaryContent, SummaryResponse
from app.services import encryption_service, gemini_service
from app.services.cache_service import cache

logger = logging.getLogger(__name__)


class SummarizationService:
    def __init__(self, db: AsyncSession) -> None:
        self._email_repo = EmailRepository(db)
        self._summary_repo = SummaryRepository(db)
        self._db = db

    async def get_or_create_summary(
        self,
        client_id: UUID,
        firm_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        force_refresh: bool = False,
    ) -> SummaryResponse:
        """Generate or retrieve a summary for a client's email thread.

        Args:
            client_id: Target client.
            firm_id: Used for access-control validation upstream.
            start_date: Optional inclusive start of date filter.
            end_date: Optional inclusive end of date filter.
            force_refresh: If True, bypasses cache and partial-refresh skip logic.

        Returns:
            SummaryResponse with the AI-generated summary or a skip indicator.

        Raises:
            ValueError: If start_date > end_date.
            RuntimeError: If Gemini fails and no existing summary is available.
        """
        self._validate_date_range(start_date, end_date)

        cache_key = cache.make_summary_key(
            str(client_id),
            start_date.isoformat() if start_date else None,
            end_date.isoformat() if end_date else None,
        )

        if not force_refresh:
            cached = cache.get(cache_key)
            if cached is not None:
                logger.info("Returning cached summary for client %s", client_id)
                return cached

        total_emails = await self._email_repo.count_for_client(
            client_id, start_date, end_date
        )
        if total_emails == 0:
            return SummaryResponse(
                client_id=client_id,
                summary=SummaryContent(),
                emails_analysed_count=0,
                last_refreshed_at=None,
                input_tokens=0,
                output_tokens=0,
                date_range_start=start_date,
                date_range_end=end_date,
                skipped=True,
                skip_reason="No emails found for the given date range",
            )

        existing_summary = await self._summary_repo.get_by_client_id(client_id)

        # Partial-refresh: skip if not enough new emails to justify a re-analysis
        if not force_refresh and existing_summary is not None:
            new_emails = total_emails - existing_summary.emails_analysed_count
            if new_emails < settings.summarization_min_new_emails:
                decrypted = encryption_service.decrypt(
                    existing_summary.encrypted_summary
                )
                response = SummaryResponse(
                    client_id=client_id,
                    summary=SummaryContent(**decrypted),
                    emails_analysed_count=existing_summary.emails_analysed_count,
                    last_refreshed_at=existing_summary.last_refreshed_at,
                    input_tokens=existing_summary.input_tokens,
                    output_tokens=existing_summary.output_tokens,
                    date_range_start=existing_summary.date_range_start,
                    date_range_end=existing_summary.date_range_end,
                    skipped=True,
                    skip_reason=(
                        f"Only {new_emails} new email(s) since last analysis "
                        f"(threshold: {settings.summarization_min_new_emails})"
                    ),
                )
                cache.set(cache_key, response)
                return response

        emails_data = await self._email_repo.get_for_client(
            client_id, start_date, end_date
        )
        email_dicts = [
            {
                "sender_email": e.sender_email,
                "sender_name": e.sender_name,
                "recipients": e.recipients,
                "subject": e.subject,
                "body": e.body,
                "sent_at": e.sent_at.isoformat() if e.sent_at else "",
            }
            for e in emails_data
        ]

        try:
            (
                summary_dict,
                input_tokens,
                output_tokens,
            ) = await gemini_service.summarize_emails(email_dicts)
        except RuntimeError:
            # Resilience: return the existing summary rather than failing entirely
            if existing_summary is not None:
                logger.warning(
                    "Gemini failed — returning existing summary for client %s",
                    client_id,
                )
                decrypted = encryption_service.decrypt(
                    existing_summary.encrypted_summary
                )
                return SummaryResponse(
                    client_id=client_id,
                    summary=SummaryContent(**decrypted),
                    emails_analysed_count=existing_summary.emails_analysed_count,
                    last_refreshed_at=existing_summary.last_refreshed_at,
                    input_tokens=existing_summary.input_tokens,
                    output_tokens=existing_summary.output_tokens,
                    date_range_start=existing_summary.date_range_start,
                    date_range_end=existing_summary.date_range_end,
                    skipped=False,
                    skip_reason="Gemini API failed; returning last successful summary",
                )
            raise

        # Only persist after a successful Gemini response
        encrypted = encryption_service.encrypt(summary_dict)
        now = datetime.now(timezone.utc)

        await self._summary_repo.upsert(
            client_id=client_id,
            encrypted_summary=encrypted,
            emails_analysed_count=total_emails,
            last_refreshed_at=now,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            date_range_start=start_date,
            date_range_end=end_date,
        )

        response = SummaryResponse(
            client_id=client_id,
            summary=SummaryContent(**summary_dict),
            emails_analysed_count=total_emails,
            last_refreshed_at=now,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            date_range_start=start_date,
            date_range_end=end_date,
        )

        cache.set(cache_key, response)
        # Invalidate the "no date range" key so a generic request sees fresh data
        cache.delete(cache.make_summary_key(str(client_id)))

        return response

    @staticmethod
    def _validate_date_range(
        start_date: datetime | None, end_date: datetime | None
    ) -> None:
        """Reject logically invalid date ranges."""
        if start_date and end_date and start_date > end_date:
            raise ValueError(
                f"start_date ({start_date.isoformat()}) must be before "
                f"end_date ({end_date.isoformat()})"
            )
