from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from jose import jwt

from src.app.core.auth_providers import EntraIDProvider, LocalJWTProvider
from src.app.core.config import settings
from src.app.core.identity import UserIdentity
from src.app.core.user_service import IdentityService


@pytest.fixture
def mock_settings_entra():
    with patch("src.app.core.auth_providers.settings") as mock:
        mock.AUTH_PROVIDER = "entra"
        mock.AZURE_TENANT_ID = "test-tenant"
        mock.AZURE_CLIENT_ID = "test-client"
        mock.ENTRA_JWKS_URL = "https://example.com/{tenant_id}/keys"
        mock.ENTRA_ISSUER = "https://example.com/{tenant_id}/v2.0"
        mock.ENTRA_ROLE_MAPPING = {"admin_group": "group-123"}
        yield mock


@pytest.mark.asyncio
async def test_local_jwt_provider_success():
    provider = LocalJWTProvider()
    token_data = {"sub": "testuser", "other": "data"}
    token = jwt.encode(token_data, settings.SECRET_KEY.get_secret_value(), algorithm=settings.ALGORITHM)

    identity = await provider.verify_token(token)

    assert identity.subject == "testuser"
    assert identity.provider == "local"
    assert identity.raw_claims["sub"] == "testuser"


@pytest.mark.asyncio
async def test_local_jwt_provider_invalid_token():
    provider = LocalJWTProvider()
    with pytest.raises(HTTPException) as exc:
        await provider.verify_token("invalid-token")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_entra_id_provider_jwks_caching(mock_settings_entra):
    provider = EntraIDProvider()

    mock_response = MagicMock()
    mock_response.json.return_value = {"keys": [{"kid": "1", "kty": "RSA"}]}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        # First call should fetch
        jwks1 = await provider._get_jwks()
        assert jwks1 == {"keys": [{"kid": "1", "kty": "RSA"}]}
        assert mock_get.call_count == 1

        # Second call should use cache
        jwks2 = await provider._get_jwks()
        assert jwks2 == jwks1
        assert mock_get.call_count == 1


@pytest.mark.asyncio
async def test_identity_service_jit_provisioning():
    mock_db = AsyncMock()
    identity = UserIdentity(
        subject="oid-123",
        email="test@example.com",
        full_name="Test User",
        username="testuser",
        provider="entra",
        raw_claims={"roles": ["User"]},
    )

    with patch("src.app.core.user_service.crud_users") as mock_crud:
        # Mock user not existing
        mock_crud.get = AsyncMock(return_value=None)
        # Mock user creation
        mock_crud.create = AsyncMock(return_value={"id": 1, "email": "test@example.com"})

        user = await IdentityService.get_or_create_user(mock_db, identity)

        assert user["email"] == "test@example.com"
        assert mock_crud.create.called
        # Check if it tried to find the user first
        assert mock_crud.get.called


@pytest.mark.asyncio
async def test_identity_service_role_mapping_admin():
    mock_db = AsyncMock()
    identity = UserIdentity(
        subject="oid-123",
        email="admin@example.com",
        full_name="Admin User",
        username="admin",
        provider="entra",
        raw_claims={"roles": ["Admin"]},  # Should trigger superuser
    )

    with patch("src.app.core.user_service.crud_users") as mock_crud:
        mock_crud.get = AsyncMock(return_value=None)
        mock_crud.create = AsyncMock(return_value={"id": 99})
        mock_crud.update = AsyncMock()

        await IdentityService.get_or_create_user(mock_db, identity)

        # Verify that update was called with is_superuser=True
        mock_crud.update.assert_called_once()
        args, kwargs = mock_crud.update.call_args
        assert kwargs["object"]["is_superuser"] is True
