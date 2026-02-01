import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# 1. Mock the config module and settings BEFORE importing anything else
mock_config = MagicMock()
mock_settings = MagicMock()
mock_settings.SECRET_KEY.get_secret_value.return_value = "test-secret-key"
mock_settings.ALGORITHM = "HS256"
mock_settings.AUTH_PROVIDER = "local"
mock_settings.AZURE_TENANT_ID = "test-tenant"
mock_settings.AZURE_CLIENT_ID = "test-client"
mock_settings.ENTRA_JWKS_URL = "https://example.com/{tenant_id}/keys"
mock_settings.ENTRA_ISSUER = "https://example.com/{tenant_id}/v2.0"
mock_settings.ENTRA_ROLE_MAPPING = {"admin_group": "group-123"}
mock_config.settings = mock_settings
sys.modules["src.app.core.config"] = mock_config

# Mock other modules that might be triggered
sys.modules["src.app.core.logger"] = MagicMock()
sys.modules["src.app.crud.crud_users"] = MagicMock()
sys.modules["src.app.crud.crud_tier"] = MagicMock()

import src.app.core.auth_providers as auth_providers
import src.app.core.user_service as user_service
from src.app.core.identity import UserIdentity


class TestAuth(unittest.IsolatedAsyncioTestCase):
    async def test_local_jwt_provider(self):
        from jose import jwt

        provider = auth_providers.LocalJWTProvider()
        token_data = {"sub": "testuser"}
        token = jwt.encode(token_data, "test-secret-key", algorithm="HS256")

        identity = await provider.verify_token(token)
        self.assertEqual(identity.subject, "testuser")
        self.assertEqual(identity.provider, "local")

    @patch("httpx.AsyncClient.get")
    async def test_entra_id_jwks_caching(self, mock_get):
        provider = auth_providers.EntraIDProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {"keys": [{"kid": "1", "kty": "RSA"}]}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # First call should fetch
        jwks1 = await provider._get_jwks()
        self.assertEqual(jwks1["keys"][0]["kid"], "1")
        self.assertEqual(mock_get.call_count, 1)

        # Second call should use cache
        jwks2 = await provider._get_jwks()
        self.assertEqual(jwks2, jwks1)
        self.assertEqual(mock_get.call_count, 1)

    async def test_identity_service_sync(self):
        mock_db = AsyncMock()
        identity = UserIdentity(
            subject="oid-1",
            email="test@example.com",
            full_name="Test User",
            username="testuser",
            provider="entra",
            raw_claims={"roles": ["Admin"]},
        )

        with patch("src.app.core.user_service.crud_users") as mock_crud:
            mock_crud.get.return_value = None
            mock_crud.create.return_value = {"id": 1, "email": "test@example.com"}

            user = await user_service.IdentityService.get_or_create_user(mock_db, identity)
            self.assertEqual(user["email"], "test@example.com")
            self.assertTrue(mock_crud.create.called)


if __name__ == "__main__":
    unittest.main()
