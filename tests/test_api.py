"""Integration tests for API endpoints: auth, clients, reports, and access control."""

import uuid

import pytest
import pytest_asyncio

from tests.conftest import make_token


@pytest.mark.asyncio
class TestHealthEndpoint:
    async def test_health_check(self, async_client):
        resp = await async_client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
class TestAuthEndpoints:
    async def test_login_success(self, async_client, seeded_db):
        resp = await async_client.post(
            "/api/auth/login",
            json={"email": "user@test.com", "password": "password123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, async_client, seeded_db):
        resp = await async_client.post(
            "/api/auth/login",
            json={"email": "user@test.com", "password": "wrong"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, async_client, seeded_db):
        resp = await async_client.post(
            "/api/auth/login",
            json={"email": "nobody@test.com", "password": "password123"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestClientEndpoints:
    async def test_list_clients_unauthenticated(self, async_client):
        resp = await async_client.get("/api/clients")
        assert resp.status_code in (401, 403)

    async def test_list_clients(self, async_client, seeded_db):
        token = make_token(seeded_db["accountant"].id, seeded_db["firm"].id)
        resp = await async_client.get(
            "/api/clients",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["clients"][0]["name"] == "Test Client"

    async def test_get_client_detail(self, async_client, seeded_db):
        token = make_token(seeded_db["accountant"].id, seeded_db["firm"].id)
        client_id = str(seeded_db["client"].id)
        resp = await async_client.get(
            f"/api/clients/{client_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email_count"] == 10

    async def test_get_client_wrong_firm(self, async_client, seeded_db):
        other_firm_id = uuid.uuid4()
        token = make_token(seeded_db["accountant"].id, other_firm_id)
        client_id = str(seeded_db["client"].id)
        resp = await async_client.get(
            f"/api/clients/{client_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_list_emails(self, async_client, seeded_db):
        token = make_token(seeded_db["accountant"].id, seeded_db["firm"].id)
        client_id = str(seeded_db["client"].id)
        resp = await async_client.get(
            f"/api/clients/{client_id}/emails",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10


@pytest.mark.asyncio
class TestReportEndpoints:
    async def test_firm_report_as_admin(self, async_client, seeded_db):
        token = make_token(seeded_db["admin"].id, seeded_db["firm"].id, "firm_admin")
        resp = await async_client.get(
            "/api/reports/firm",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_clients"] == 1
        assert data["clients_with_summaries"] == 0

    async def test_firm_report_as_accountant_forbidden(self, async_client, seeded_db):
        token = make_token(seeded_db["accountant"].id, seeded_db["firm"].id, "accountant")
        resp = await async_client.get(
            "/api/reports/firm",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_global_report_as_superuser(self, async_client, seeded_db):
        token = make_token(seeded_db["superuser"].id, seeded_db["firm"].id, "superuser")
        resp = await async_client.get(
            "/api/reports/global",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    async def test_global_report_as_admin_forbidden(self, async_client, seeded_db):
        token = make_token(seeded_db["admin"].id, seeded_db["firm"].id, "firm_admin")
        resp = await async_client.get(
            "/api/reports/global",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
