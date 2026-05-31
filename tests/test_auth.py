"""Tests for the authentication service: password hashing and JWT lifecycle."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.config import settings
from app.services.auth_service import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "securePassword123!"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("correct")
        assert not verify_password("wrong", hashed)

    def test_different_hashes_for_same_password(self):
        p = "test"
        assert hash_password(p) != hash_password(p)


class TestJWT:
    def test_create_and_decode_token(self):
        aid = uuid.uuid4()
        fid = uuid.uuid4()
        token = create_access_token(aid, fid, "accountant")

        payload = decode_access_token(token)
        assert payload["sub"] == str(aid)
        assert payload["firm_id"] == str(fid)
        assert payload["role"] == "accountant"

    def test_token_contains_expiry(self):
        token = create_access_token(uuid.uuid4(), uuid.uuid4(), "accountant")
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        assert "exp" in payload

    def test_expired_token_raises(self):
        payload = {
            "sub": str(uuid.uuid4()),
            "firm_id": str(uuid.uuid4()),
            "role": "accountant",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        with pytest.raises(Exception):
            decode_access_token(token)

    def test_invalid_token_raises(self):
        with pytest.raises(Exception):
            decode_access_token("not.a.valid.token")

    def test_roles_preserved(self):
        for role in ["accountant", "firm_admin", "superuser"]:
            token = create_access_token(uuid.uuid4(), uuid.uuid4(), role)
            payload = decode_access_token(token)
            assert payload["role"] == role
