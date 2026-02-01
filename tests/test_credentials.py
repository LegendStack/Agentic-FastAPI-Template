"""
Tests for Credential Providers and Integration Clients.
========================================================
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.app.core.credentials import (
    ApiKeyProvider,
    AuthMode,
    BasicAuthProvider,
    Credentials,
    OAuth2ClientCredentialsProvider,
    PatProvider,
    TokenInfo,
)

# ============================================================================
# TokenInfo Tests
# ============================================================================


class TestTokenInfo:
    """Tests for TokenInfo dataclass."""

    def test_token_not_expired(self):
        """Test token is not expired."""
        token = TokenInfo(access_token="test", expires_at=datetime.utcnow() + timedelta(hours=1))
        assert token.is_expired is False

    def test_token_expired(self):
        """Test token is expired."""
        token = TokenInfo(access_token="test", expires_at=datetime.utcnow() - timedelta(minutes=5))
        assert token.is_expired is True

    def test_token_expiring_soon(self):
        """Test token expiring within buffer is considered expired."""
        token = TokenInfo(
            access_token="test",
            expires_at=datetime.utcnow() + timedelta(seconds=30),  # Within 60s buffer
        )
        assert token.is_expired is True

    def test_token_no_expiry(self):
        """Test token with no expiry is not expired."""
        token = TokenInfo(access_token="test")
        assert token.is_expired is False


# ============================================================================
# Credentials Tests
# ============================================================================


class TestCredentials:
    """Tests for Credentials class."""

    def test_api_key_header(self):
        """Test API key auth header."""
        creds = Credentials(auth_mode=AuthMode.API_KEY, api_key="my-key")
        header = creds.get_auth_header()
        assert header == {"api-key": "my-key"}

    def test_oauth2_header(self):
        """Test OAuth2 auth header."""
        token = TokenInfo(access_token="token123", token_type="Bearer")
        creds = Credentials(auth_mode=AuthMode.OAUTH2, token=token)
        header = creds.get_auth_header()
        assert header == {"Authorization": "Bearer token123"}

    def test_pat_header(self):
        """Test PAT auth header."""
        creds = Credentials(auth_mode=AuthMode.PAT, api_key="pat123")
        header = creds.get_auth_header()
        assert header == {"Authorization": "Bearer pat123"}

    def test_basic_header(self):
        """Test Basic auth header."""
        creds = Credentials(auth_mode=AuthMode.BASIC, username="user", password="pass")
        header = creds.get_auth_header()
        import base64

        expected = base64.b64encode(b"user:pass").decode()
        assert header == {"Authorization": f"Basic {expected}"}


# ============================================================================
# ApiKeyProvider Tests
# ============================================================================


class TestApiKeyProvider:
    """Tests for ApiKeyProvider."""

    @pytest.mark.asyncio
    async def test_get_credentials(self):
        """Test getting API key credentials."""
        provider = ApiKeyProvider("my-api-key")
        creds = await provider.get_credentials()

        assert creds.auth_mode == AuthMode.API_KEY
        assert creds.api_key == "my-api-key"

    def test_auth_mode(self):
        """Test auth mode is API_KEY."""
        provider = ApiKeyProvider("key")
        assert provider.get_auth_mode() == AuthMode.API_KEY


# ============================================================================
# PatProvider Tests
# ============================================================================


class TestPatProvider:
    """Tests for PatProvider."""

    @pytest.mark.asyncio
    async def test_get_credentials(self):
        """Test getting PAT credentials."""
        provider = PatProvider("my-pat-token")
        creds = await provider.get_credentials()

        assert creds.auth_mode == AuthMode.PAT
        assert creds.api_key == "my-pat-token"


# ============================================================================
# BasicAuthProvider Tests
# ============================================================================


class TestBasicAuthProvider:
    """Tests for BasicAuthProvider."""

    @pytest.mark.asyncio
    async def test_get_credentials(self):
        """Test getting basic auth credentials."""
        provider = BasicAuthProvider("user", "pass")
        creds = await provider.get_credentials()

        assert creds.auth_mode == AuthMode.BASIC
        assert creds.username == "user"
        assert creds.password == "pass"


# ============================================================================
# OAuth2ClientCredentialsProvider Tests
# ============================================================================


class TestOAuth2ClientCredentialsProvider:
    """Tests for OAuth2ClientCredentialsProvider."""

    @pytest.fixture
    def provider(self):
        return OAuth2ClientCredentialsProvider(
            client_id="client123",
            client_secret="secret456",
            token_url="https://login.example.com/oauth2/token",
            scope="https://api.example.com/.default",
        )

    @pytest.mark.asyncio
    async def test_get_credentials_fetches_token(self, provider):
        """Test fetching new token on first call."""
        with patch("httpx.AsyncClient") as MockClient:
            mock_response = MagicMock()
            mock_response.json.return_value = {"access_token": "new-token", "token_type": "Bearer", "expires_in": 3600}
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            MockClient.return_value = mock_client

            creds = await provider.get_credentials()

            assert creds.auth_mode == AuthMode.OAUTH2
            assert creds.token.access_token == "new-token"
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_credentials_uses_cache(self, provider):
        """Test using cached token on subsequent calls."""
        # Set up cached token
        provider._token_cache = TokenInfo(
            access_token="cached-token", expires_at=datetime.utcnow() + timedelta(hours=1)
        )

        creds = await provider.get_credentials()

        assert creds.token.access_token == "cached-token"

    @pytest.mark.asyncio
    async def test_get_credentials_refreshes_expired(self, provider):
        """Test refreshing expired token."""
        # Set up expired cached token
        provider._token_cache = TokenInfo(
            access_token="expired-token", expires_at=datetime.utcnow() - timedelta(hours=1)
        )

        with patch("httpx.AsyncClient") as MockClient:
            mock_response = MagicMock()
            mock_response.json.return_value = {"access_token": "refreshed-token", "expires_in": 3600}
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            MockClient.return_value = mock_client

            creds = await provider.get_credentials()

            assert creds.token.access_token == "refreshed-token"

    def test_auth_mode(self, provider):
        """Test auth mode is OAUTH2."""
        assert provider.get_auth_mode() == AuthMode.OAUTH2


# ============================================================================
# Integration Client Factory Tests
# ============================================================================


class TestIntegrationClientFactory:
    """Tests for IntegrationClientFactory."""

    @pytest.fixture
    def factory(self):
        from src.app.core.clients import IntegrationClientFactory

        return IntegrationClientFactory()

    def test_configure_api_key(self, factory):
        """Test configuring with API key."""
        from src.app.core.clients import Integration, IntegrationConfig

        config = IntegrationConfig(name=Integration.AZURE_OPENAI, auth_mode=AuthMode.API_KEY, api_key="test-key")
        factory.configure(config)

        assert factory.is_configured(Integration.AZURE_OPENAI)

    def test_configure_pat(self, factory):
        """Test configuring with PAT."""
        from src.app.core.clients import Integration, IntegrationConfig

        config = IntegrationConfig(name=Integration.JIRA, auth_mode=AuthMode.PAT, token="jira-pat")
        factory.configure(config)

        assert factory.is_configured(Integration.JIRA)

    def test_configure_oauth2(self, factory):
        """Test configuring with OAuth2."""
        from src.app.core.clients import Integration, IntegrationConfig

        config = IntegrationConfig(
            name=Integration.MICROSOFT_GRAPH,
            auth_mode=AuthMode.OAUTH2,
            client_id="client123",
            client_secret="secret456",
            tenant_id="tenant789",
            scope="https://graph.microsoft.com/.default",
        )
        factory.configure(config)

        assert factory.is_configured(Integration.MICROSOFT_GRAPH)

    @pytest.mark.asyncio
    async def test_get_credentials(self, factory):
        """Test getting credentials from configured integration."""
        from src.app.core.clients import Integration, IntegrationConfig

        config = IntegrationConfig(name=Integration.COHERE, auth_mode=AuthMode.API_KEY, api_key="cohere-key")
        factory.configure(config)

        creds = await factory.get_credentials(Integration.COHERE)

        assert creds.api_key == "cohere-key"

    @pytest.mark.asyncio
    async def test_get_credentials_not_configured(self, factory):
        """Test getting credentials for unconfigured integration raises error."""
        from src.app.core.clients import Integration

        with pytest.raises(ValueError, match="not configured"):
            await factory.get_credentials(Integration.AZURE_BLOB)

    def test_get_config(self, factory):
        """Test getting stored configuration."""
        from src.app.core.clients import Integration, IntegrationConfig

        config = IntegrationConfig(
            name=Integration.AZURE_SEARCH,
            auth_mode=AuthMode.API_KEY,
            api_key="search-key",
            base_url="https://search.example.com",
        )
        factory.configure(config)

        retrieved = factory.get_config(Integration.AZURE_SEARCH)

        assert retrieved.base_url == "https://search.example.com"


# ============================================================================
# Client Implementation Tests
# ============================================================================


class TestAzureOpenAIClient:
    """Tests for AzureOpenAIClient."""

    @pytest.fixture
    def client(self):
        from src.app.core.clients import (
            AzureOpenAIClient,
            Integration,
            IntegrationClientFactory,
            IntegrationConfig,
        )

        factory = IntegrationClientFactory()
        factory.configure(
            IntegrationConfig(name=Integration.AZURE_OPENAI, auth_mode=AuthMode.API_KEY, api_key="test-openai-key")
        )

        return AzureOpenAIClient(factory, "https://example.openai.azure.com")

    @pytest.mark.asyncio
    async def test_get_headers(self, client):
        """Test getting auth headers."""
        headers = await client._get_headers()

        assert headers["api-key"] == "test-openai-key"
        assert headers["Content-Type"] == "application/json"


class TestJiraClient:
    """Tests for JiraClient."""

    @pytest.fixture
    def client(self):
        from src.app.core.clients import (
            Integration,
            IntegrationClientFactory,
            IntegrationConfig,
            JiraClient,
        )

        factory = IntegrationClientFactory()
        factory.configure(
            IntegrationConfig(
                name=Integration.JIRA, auth_mode=AuthMode.PAT, token="jira-pat-token", cloud_id="test-cloud-id"
            )
        )

        return JiraClient(factory, "test-cloud-id")

    def test_base_url(self, client):
        """Test Jira base URL is constructed correctly."""
        assert "api.atlassian.com/ex/jira/test-cloud-id" in client.base_url


class TestCohereClient:
    """Tests for CohereClient."""

    @pytest.fixture
    def client(self):
        from src.app.core.clients import (
            CohereClient,
            Integration,
            IntegrationClientFactory,
            IntegrationConfig,
        )

        factory = IntegrationClientFactory()
        factory.configure(
            IntegrationConfig(name=Integration.COHERE, auth_mode=AuthMode.API_KEY, api_key="cohere-api-key")
        )

        return CohereClient(factory)

    @pytest.mark.asyncio
    async def test_get_headers(self, client):
        """Test getting Cohere auth headers."""
        headers = await client._get_headers()

        assert headers["Authorization"] == "Bearer cohere-api-key"
        assert headers["Content-Type"] == "application/json"
