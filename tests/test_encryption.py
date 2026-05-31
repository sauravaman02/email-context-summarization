"""Tests for the Fernet encryption service: roundtrip, key rotation, edge cases."""

import pytest
from cryptography.fernet import Fernet

from app.services import encryption_service


@pytest.fixture(autouse=True)
def _reset_fernet(monkeypatch):
    """Ensure a valid Fernet key is configured for each test."""
    key = Fernet.generate_key().decode()
    monkeypatch.setattr("app.services.encryption_service.settings.encryption_key", key)
    encryption_service._fernet = None
    yield
    encryption_service._fernet = None


class TestEncryption:
    def test_roundtrip(self):
        data = {
            "actors": [
                {"name": "John", "role": "Client", "involvement": "Primary taxpayer"}
            ],
            "concluded_discussions": [],
            "open_action_items": [
                {
                    "item": "Send W-2",
                    "assigned_to": "John",
                    "priority": "high",
                    "context": "Needed for filing",
                }
            ],
        }
        encrypted = encryption_service.encrypt(data)
        assert encrypted != str(data)
        decrypted = encryption_service.decrypt(encrypted)
        assert decrypted == data

    def test_encrypted_output_is_string(self):
        encrypted = encryption_service.encrypt({"key": "value"})
        assert isinstance(encrypted, str)

    def test_different_encryptions_differ(self):
        data = {"test": "data"}
        e1 = encryption_service.encrypt(data)
        e2 = encryption_service.encrypt(data)
        assert e1 != e2  # Fernet uses random IV

    def test_wrong_key_fails(self, monkeypatch):
        data = {"secret": "info"}
        encrypted = encryption_service.encrypt(data)

        new_key = Fernet.generate_key().decode()
        monkeypatch.setattr(
            "app.services.encryption_service.settings.encryption_key", new_key
        )
        encryption_service._fernet = None

        with pytest.raises(Exception):
            encryption_service.decrypt(encrypted)

    def test_empty_dict(self):
        data = {}
        encrypted = encryption_service.encrypt(data)
        assert encryption_service.decrypt(encrypted) == data

    def test_large_payload(self):
        data = {
            "items": [{"id": i, "text": f"Item number {i}" * 50} for i in range(100)]
        }
        encrypted = encryption_service.encrypt(data)
        assert encryption_service.decrypt(encrypted) == data
