"""JWT authentication and password hashing service.

Uses bcrypt for password hashing (resistant to rainbow table attacks)
and HS256 JWT tokens with configurable expiry for stateless auth.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
from jose import JWTError, jwt

from app.config import settings


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt and a random salt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(
    accountant_id: UUID,
    firm_id: UUID,
    role: str,
) -> str:
    """Create a signed JWT containing the user's identity and role.

    The token embeds firm_id so downstream endpoints can enforce
    firm-scoped data access without an extra DB lookup.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expiry_minutes)
    payload = {
        "sub": str(accountant_id),
        "firm_id": str(firm_id),
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT. Raises JWTError on invalid/expired tokens."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        if payload.get("sub") is None:
            raise JWTError("Missing subject claim")
        return payload
    except JWTError:
        raise
