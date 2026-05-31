"""Pydantic schemas for API request validation and response serialisation.

These schemas serve as the contract between the API and any frontend consumer.
All response models use from_attributes=True for direct ORM-to-schema mapping.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Auth ─────────────────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    email: str = Field(..., description="Accountant's email address")
    password: str = Field(..., description="Account password")


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT bearer token")
    token_type: str = "bearer"


class AccountantInfo(BaseModel):
    """Decoded JWT payload representing the authenticated user."""

    id: UUID
    firm_id: UUID
    email: str
    full_name: str
    role: str


# ── Firm ─────────────────────────────────────────────────────────────────────


class FirmOut(BaseModel):
    id: UUID
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Client ───────────────────────────────────────────────────────────────────


class ClientOut(BaseModel):
    id: UUID
    firm_id: UUID
    name: str
    email: str
    created_at: datetime
    email_count: int | None = Field(None, description="Total emails for this client")

    model_config = {"from_attributes": True}


class ClientListResponse(BaseModel):
    clients: list[ClientOut]
    total: int = Field(..., description="Total number of clients (before pagination)")


# ── Email ────────────────────────────────────────────────────────────────────


class Recipient(BaseModel):
    email: str
    name: str


class EmailOut(BaseModel):
    id: UUID
    client_id: UUID
    sender_email: str
    sender_name: str
    recipients: list[Recipient]
    subject: str | None
    body: str
    sent_at: datetime

    model_config = {"from_attributes": True}


class EmailListResponse(BaseModel):
    emails: list[EmailOut]
    total: int


# ── Summary ──────────────────────────────────────────────────────────────────


class SummaryRequest(BaseModel):
    """Optional date range filter for summarisation. Omit both for all emails."""

    start_date: datetime | None = Field(
        None, description="Inclusive start of date range"
    )
    end_date: datetime | None = Field(None, description="Inclusive end of date range")


class Actor(BaseModel):
    name: str
    role: str = Field(..., description="e.g. Accountant, Client, IRS Agent")
    involvement: str


class ConcludedDiscussion(BaseModel):
    topic: str
    resolution: str
    resolved_date: str = Field(..., description="YYYY-MM-DD or 'unknown'")


class OpenActionItem(BaseModel):
    item: str
    assigned_to: str
    priority: str = Field(..., description="high, medium, or low")
    context: str


class SummaryContent(BaseModel):
    """Structured intelligence extracted by Gemini from an email thread."""

    actors: list[Actor] = []
    concluded_discussions: list[ConcludedDiscussion] = []
    open_action_items: list[OpenActionItem] = []


class SummaryResponse(BaseModel):
    client_id: UUID
    summary: SummaryContent
    emails_analysed_count: int
    last_refreshed_at: datetime | None
    input_tokens: int = Field(..., description="Gemini prompt tokens consumed")
    output_tokens: int = Field(..., description="Gemini completion tokens consumed")
    date_range_start: datetime | None
    date_range_end: datetime | None
    skipped: bool = Field(False, description="True if re-summarisation was skipped")
    skip_reason: str | None = Field(None, description="Why summarisation was skipped")


class SummaryTrackingInfo(BaseModel):
    """Per-client tracking data for admin reports."""

    client_id: UUID
    client_name: str
    emails_analysed_count: int
    last_refreshed_at: datetime | None
    input_tokens: int
    output_tokens: int


# ── Reports ──────────────────────────────────────────────────────────────────


class FirmReportResponse(BaseModel):
    """Firm admin report: summary coverage within a single firm."""

    firm_id: UUID
    firm_name: str
    total_clients: int
    clients_with_summaries: int
    summaries: list[SummaryTrackingInfo]


class GlobalFirmSummary(BaseModel):
    firm_id: UUID
    firm_name: str
    total_clients: int
    clients_with_summaries: int


class GlobalReportResponse(BaseModel):
    """Superuser report: summary coverage across all firms."""

    total_firms: int
    firms: list[GlobalFirmSummary]


# ── Health ───────────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
