"""FastAPI dependency injection for authentication and database access.

Provides reusable type aliases (DbSession, CurrentUser) and a role-based
access control factory (require_role) used across all route handlers.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import AccountantInfo
from app.services.auth_service import decode_access_token

security = HTTPBearer()

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> AccountantInfo:
    """Extract and validate the current user from the JWT Bearer token.

    Raises HTTP 401 if the token is missing, malformed, or expired.
    """
    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return AccountantInfo(
            id=UUID(payload["sub"]),
            firm_id=UUID(payload["firm_id"]),
            email=payload.get("email", ""),
            full_name=payload.get("full_name", ""),
            role=payload["role"],
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Malformed token payload: {exc}",
        )


CurrentUser = Annotated[AccountantInfo, Depends(get_current_user)]


def require_role(*allowed_roles: str):
    """Dependency factory that restricts endpoint access to specific roles.

    Usage in a route:
        user: Annotated[AccountantInfo, Depends(require_role("firm_admin", "superuser"))]
    """

    async def _check(user: CurrentUser) -> AccountantInfo:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' is not authorized. Required: {', '.join(allowed_roles)}",
            )
        return user

    return _check
