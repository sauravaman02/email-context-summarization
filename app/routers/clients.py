"""Client and email listing endpoints, plus email simulation utility.

All endpoints are firm-scoped — the authenticated user's firm_id (from JWT)
is used to filter results, preventing cross-firm data access.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import CurrentUser, DbSession
from app.models import Email
from app.repositories.client_repo import ClientRepository
from app.repositories.email_repo import EmailRepository
from app.schemas import ClientListResponse, ClientOut, EmailListResponse, EmailOut
from app.services.cache_service import cache

router = APIRouter(prefix="/api/clients", tags=["Clients"])


@router.get("", response_model=ClientListResponse)
async def list_clients(
    db: DbSession,
    user: CurrentUser,
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Page size"),
):
    """List all clients for the authenticated user's firm."""
    repo = ClientRepository(db)
    clients, total = await repo.list_by_firm(user.firm_id, skip, limit)

    client_outs = []
    for c in clients:
        count = await repo.get_email_count(c.id)
        client_outs.append(
            ClientOut(
                id=c.id,
                firm_id=c.firm_id,
                name=c.name,
                email=c.email,
                created_at=c.created_at,
                email_count=count,
            )
        )
    return ClientListResponse(clients=client_outs, total=total)


@router.get("/{client_id}", response_model=ClientOut)
async def get_client(client_id: UUID, db: DbSession, user: CurrentUser):
    """Get details for a single client, including their email count."""
    repo = ClientRepository(db)
    client = await repo.get_by_id(client_id, user.firm_id)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found or does not belong to your firm",
        )
    count = await repo.get_email_count(client.id)
    return ClientOut(
        id=client.id,
        firm_id=client.firm_id,
        name=client.name,
        email=client.email,
        created_at=client.created_at,
        email_count=count,
    )


@router.get("/{client_id}/emails", response_model=EmailListResponse)
async def list_emails(
    client_id: UUID,
    db: DbSession,
    user: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List emails for a client, paginated with newest first."""
    client_repo = ClientRepository(db)
    client = await client_repo.get_by_id(client_id, user.firm_id)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found or does not belong to your firm",
        )

    email_repo = EmailRepository(db)
    emails, total = await email_repo.list_paginated(client_id, skip, limit)

    return EmailListResponse(
        emails=[
            EmailOut(
                id=e.id,
                client_id=e.client_id,
                sender_email=e.sender_email,
                sender_name=e.sender_name,
                recipients=e.recipients,
                subject=e.subject,
                body=e.body,
                sent_at=e.sent_at,
            )
            for e in emails
        ],
        total=total,
    )


@router.post("/{client_id}/emails/simulate", tags=["Simulation"])
async def simulate_incoming_email(
    client_id: UUID,
    db: DbSession,
    user: CurrentUser,
    count: int = Query(1, ge=1, le=20, description="Number of emails to simulate"),
):
    """Simulate new incoming emails for a client.

    Mimics what a Microsoft Graph API poller would do in production.
    Use this to test the partial-refresh logic: generate a summary first,
    then simulate emails and call summary again to observe the skip behavior
    when fewer than SUMMARIZATION_MIN_NEW_EMAILS have arrived.
    """
    client_repo = ClientRepository(db)
    client = await client_repo.get_by_id(client_id, user.firm_id)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found or does not belong to your firm",
        )

    subjects = [
        "Follow-up on outstanding documents",
        "Updated tax worksheet attached",
        "Question about deduction eligibility",
        "Quarterly estimated payment reminder",
        "Missing receipt for business expense",
        "Schedule K-1 received from partnership",
        "Amended return discussion",
        "Year-end tax planning meeting",
        "IRS correspondence received",
        "Payroll tax question",
    ]

    now = datetime.now(timezone.utc)
    for i in range(count):
        email = Email(
            client_id=client_id,
            sender_email=client.email,
            sender_name=client.name,
            recipients=[
                {
                    "name": user.email.split("@")[0].replace(".", " ").title(),
                    "email": user.email,
                }
            ],
            subject=subjects[i % len(subjects)],
            body=f"Hi, this is a follow-up regarding my tax filing. Could you please provide an update on the status? (Simulated email #{i + 1})",
            sent_at=now,
        )
        db.add(email)

    await db.flush()

    # Invalidate cached summaries so partial-refresh logic evaluates fresh counts
    cache.delete(cache.make_summary_key(str(client_id)))
    cache.delete(cache.make_summary_key(str(client_id), "none", "none"))

    total = await client_repo.get_email_count(client_id)
    return {
        "message": f"Simulated {count} new email(s) for {client.name}",
        "new_emails_created": count,
        "total_emails_now": total,
    }
