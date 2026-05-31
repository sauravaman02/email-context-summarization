"""Authentication endpoints.

Provides JWT token issuance via email/password login.
All other endpoints require the returned Bearer token.
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.dependencies import DbSession
from app.models import Accountant
from app.schemas import LoginRequest, TokenResponse
from app.services.auth_service import create_access_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: DbSession):
    """Authenticate with email and password, returns a JWT bearer token."""
    result = await db.execute(
        select(Accountant).where(Accountant.email == body.email)
    )
    accountant = result.scalar_one_or_none()

    if accountant is None or not verify_password(body.password, accountant.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not accountant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated — contact your firm administrator",
        )

    token = create_access_token(
        accountant_id=accountant.id,
        firm_id=accountant.firm_id,
        role=accountant.role,
    )
    return TokenResponse(access_token=token)
