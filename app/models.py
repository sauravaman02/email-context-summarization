"""SQLAlchemy ORM models for the Email Context system.

Schema design supports: 50 firms x 10,000 clients x 100 emails per client.
Key indexes target the most common query patterns:
  - (client_id, sent_at) on emails for date-range filtering
  - (firm_id) on clients/accountants for firm-scoped queries
  - (email) on accountants for login lookups
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Firm(Base):
    """A CPA firm — the top-level organisational entity."""

    __tablename__ = "firms"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    accountants: Mapped[list["Accountant"]] = relationship(back_populates="firm")
    clients: Mapped[list["Client"]] = relationship(back_populates="firm")


class Accountant(Base):
    """A user within a firm. Roles: accountant, firm_admin, superuser."""

    __tablename__ = "accountants"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    firm_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("firms.id"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="accountant")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    firm: Mapped["Firm"] = relationship(back_populates="accountants")


class Client(Base):
    """An external client being serviced by a firm."""

    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    firm_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("firms.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    firm: Mapped["Firm"] = relationship(back_populates="clients")
    emails: Mapped[list["Email"]] = relationship(back_populates="client")
    summary: Mapped["EmailSummary | None"] = relationship(back_populates="client", uselist=False)


class Email(Base):
    """An individual email between an accountant and a client.

    Recipients stored as JSON array of {name, email} objects to avoid
    a join table for this read-heavy, write-once data.
    """

    __tablename__ = "emails"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("clients.id"), nullable=False, index=True
    )
    sender_email: Mapped[str] = mapped_column(String(255), nullable=False)
    sender_name: Mapped[str] = mapped_column(String(255), nullable=False)
    recipients: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    client: Mapped["Client"] = relationship(back_populates="emails")


class EmailSummary(Base):
    """AI-generated summary of a client's email thread.

    The summary payload (actors, concluded discussions, open action items)
    is Fernet-encrypted before storage to protect sensitive data at rest.
    One summary per client (UNIQUE constraint on client_id).
    """

    __tablename__ = "email_summaries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("clients.id"), nullable=False, unique=True, index=True
    )
    encrypted_summary: Mapped[str] = mapped_column(Text, nullable=False)
    emails_analysed_count: Mapped[int] = mapped_column(Integer, default=0)
    last_refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    date_range_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    date_range_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    client: Mapped["Client"] = relationship(back_populates="summary")
