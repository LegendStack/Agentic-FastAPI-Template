"""
Credential Providers.
=====================
Abstract base and concrete implementations for various authentication methods.

Supports:
- API Key authentication
- OAuth2 Client Credentials (Azure AD, Atlassian, etc.)
- Azure Managed Identity
- Personal Access Tokens (PAT)
"""

import asyncio
import logging
import typing
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class AuthMode(str, Enum):
    """Supported authentication modes."""

    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    MANAGED_IDENTITY = "managed_identity"
    PAT = "pat"
    BASIC = "basic"


@dataclass
class TokenInfo:
    """Represents an OAuth2 token with metadata."""

    access_token: str
    token_type: str = "Bearer"
    expires_at: datetime | None = None
    refresh_token: str | None = None
    scope: str | None = None

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        # Add 60-second buffer
        return datetime.utcnow() >= (self.expires_at - timedelta(seconds=60))


@dataclass
class Credentials:
    """Universal credentials container."""

    auth_mode: AuthMode
    token: TokenInfo | None = None
    api_key: str | None = None
    username: str | None = None
    password: str | None = None

    def get_auth_header(self) -> dict[str, str]:
        """Get the appropriate authorization header."""
        if self.auth_mode == AuthMode.API_KEY:
            return {"api-key": self.api_key}
        elif self.auth_mode in (AuthMode.OAUTH2, AuthMode.MANAGED_IDENTITY):
            return {"Authorization": f"{self.token.token_type} {self.token.access_token}"}
        elif self.auth_mode == AuthMode.PAT:
            return {"Authorization": f"Bearer {self.api_key}"}
        elif self.auth_mode == AuthMode.BASIC:
            import base64

            encoded = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            return {"Authorization": f"Basic {encoded}"}
        return {}


class BaseCredentialProvider(ABC):
    """Abstract base for credential providers."""

    @abstractmethod
    async def get_credentials(self) -> Credentials:
        """Get current valid credentials, refreshing if needed."""
        pass

    @abstractmethod
    def get_auth_mode(self) -> AuthMode:
        """Return the authentication mode."""
        pass


class ApiKeyProvider(BaseCredentialProvider):
    """Provider for API key authentication."""

    def __init__(self, api_key: str, header_name: str = "api-key"):
        self._api_key = api_key
        self._header_name = header_name

    async def get_credentials(self) -> Credentials:
        return Credentials(auth_mode=AuthMode.API_KEY, api_key=self._api_key)

    def get_auth_mode(self) -> AuthMode:
        return AuthMode.API_KEY


class PatProvider(BaseCredentialProvider):
    """Provider for Personal Access Token authentication."""

    def __init__(self, token: str):
        self._token = token

    async def get_credentials(self) -> Credentials:
        return Credentials(auth_mode=AuthMode.PAT, api_key=self._token)

    def get_auth_mode(self) -> AuthMode:
        return AuthMode.PAT


class BasicAuthProvider(BaseCredentialProvider):
    """Provider for Basic authentication."""

    def __init__(self, username: str, password: str):
        self._username = username
        self._password = password

    async def get_credentials(self) -> Credentials:
        return Credentials(auth_mode=AuthMode.BASIC, username=self._username, password=self._password)

    def get_auth_mode(self) -> AuthMode:
        return AuthMode.BASIC


class OAuth2ClientCredentialsProvider(BaseCredentialProvider):
    """
    OAuth2 Client Credentials flow provider.

    Used for Azure AD, Microsoft Graph, and other OAuth2-compatible services.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_url: str,
        scope: str | None = None,
        resource: str | None = None,  # For Azure AD v1 endpoints
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._scope = scope
        self._resource = resource
        self._token_cache: TokenInfo | None = None
        self._lock = asyncio.Lock()

    async def get_credentials(self) -> Credentials:
        async with self._lock:
            if self._token_cache and not self._token_cache.is_expired:
                return Credentials(auth_mode=AuthMode.OAUTH2, token=self._token_cache)

            token = await self._fetch_token()
            self._token_cache = token

            return Credentials(auth_mode=AuthMode.OAUTH2, token=token)

    async def _fetch_token(self) -> TokenInfo:
        """Fetch a new token from the OAuth2 token endpoint."""
        try:
            import httpx
        except ImportError:
            raise ImportError("httpx required. Install with: pip install httpx")

        data = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }

        if self._scope:
            data["scope"] = self._scope
        if self._resource:
            data["resource"] = self._resource

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self._token_url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                response.raise_for_status()
                token_data = response.json()
            except Exception as e:
                logger.error(f"Failed to fetch OAuth2 token: {e}")
                raise

        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        logger.info(f"Fetched new OAuth2 token, expires at {expires_at}")

        return TokenInfo(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            expires_at=expires_at,
            scope=token_data.get("scope"),
        )

    def get_auth_mode(self) -> AuthMode:
        return AuthMode.OAUTH2


class AzureManagedIdentityProvider(BaseCredentialProvider):
    """
    Azure Managed Identity provider.

    Uses Azure.Identity for token acquisition. Works in:
    - Azure CLI (local dev)
    - Environment Variables (Service Principal)
    - Azure VMs / App Service / AKS (Managed Identity)
    """

    def __init__(self, resource: str, client_id: str | None = None):
        """
        Args:
            resource: The resource URL (e.g., 'https://cognitiveservices.azure.com/')
            client_id: Optional client ID for user-assigned managed identity
        """
        self._resource = resource
        self._client_id = client_id
        self._credential = None
        self._token_cache: TokenInfo | None = None
        self._lock = asyncio.Lock()

    def _get_credential(self):
        if self._credential is None:
            try:
                from azure.identity import DefaultAzureCredential

                # DefaultAzureCredential handles Managed Identity, CLI, and Env vars
                self._credential = DefaultAzureCredential(managed_identity_client_id=self._client_id)
            except ImportError:
                raise ImportError("azure-identity required. Install with: pip install azure-identity")
        return self._credential

    async def get_credentials(self) -> Credentials:
        async with self._lock:
            if self._token_cache and not self._token_cache.is_expired:
                return Credentials(auth_mode=AuthMode.MANAGED_IDENTITY, token=self._token_cache)

            credential = self._get_credential()

            # Acquisition is usually blocking, but newer azure-identity supports async
            # We'll use the sync version in an executor for safety across versions
            loop = asyncio.get_event_loop()
            token = await loop.run_in_executor(None, credential.get_token, self._resource)

            self._token_cache = TokenInfo(
                access_token=token.token, expires_at=datetime.fromtimestamp(token.expires_on, tz=None)
            )

            logger.info(f"Fetched Azure AD token for {self._resource}")

            return Credentials(auth_mode=AuthMode.MANAGED_IDENTITY, token=self._token_cache)

    def get_auth_mode(self) -> AuthMode:
        return AuthMode.MANAGED_IDENTITY


class AtlassianOAuth2Provider(BaseCredentialProvider):
    """
    OAuth2 provider for Atlassian Cloud (Jira, Confluence).

    Uses 3-legged OAuth2 flow for user authorization.
    Requires initial authorization via browser redirect.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,  # Must be obtained via initial auth flow
        cloud_id: str,  # Atlassian Cloud ID
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._cloud_id = cloud_id
        self._token_url = "https://auth.atlassian.com/oauth/token"
        self._token_cache: TokenInfo | None = None
        self._lock = asyncio.Lock()

    @property
    def cloud_id(self) -> str:
        return self._cloud_id

    async def get_credentials(self) -> Credentials:
        async with self._lock:
            if self._token_cache and not self._token_cache.is_expired:
                return Credentials(auth_mode=AuthMode.OAUTH2, token=self._token_cache)

            token = await self._refresh_access_token()
            self._token_cache = token

            return Credentials(auth_mode=AuthMode.OAUTH2, token=token)

    async def _refresh_access_token(self) -> TokenInfo:
        """Refresh the access token using the refresh token."""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self._token_url,
                data={
                    "grant_type": "refresh_token",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "refresh_token": self._refresh_token,
                },
            )
            response.raise_for_status()
            token_data = response.json()

        # Update refresh token if a new one is provided
        if "refresh_token" in token_data:
            self._refresh_token = token_data["refresh_token"]

        expires_in = token_data.get("expires_in", 3600)

        return TokenInfo(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            expires_at=datetime.utcnow() + timedelta(seconds=expires_in),
            refresh_token=self._refresh_token,
        )

    def get_auth_mode(self) -> AuthMode:
        return AuthMode.OAUTH2


class AzureOpenAICredentialFactory:
    """Factory for creating Azure OpenAI credential providers."""

    @staticmethod
    def get_provider(settings: typing.Any) -> BaseCredentialProvider:
        """Get the appropriate provider based on settings."""
        mode = settings.AZURE_OPENAI_AUTH_MODE.lower()
        resource = "https://cognitiveservices.azure.com/.default"

        if mode == "api_key":
            if not settings.AZURE_OPENAI_API_KEY:
                raise ValueError("AZURE_OPENAI_API_KEY is required for api_key auth mode.")
            return ApiKeyProvider(settings.AZURE_OPENAI_API_KEY.get_secret_value())

        elif mode == "oauth2":
            if not settings.AZURE_OPENAI_CLIENT_ID or not settings.AZURE_OPENAI_CLIENT_SECRET:
                raise ValueError("Client ID and Secret are required for oauth2 auth mode.")

            # Construct token URL from tenant ID if available
            tenant_id = getattr(settings, "AZURE_TENANT_ID", "common")
            token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

            return OAuth2ClientCredentialsProvider(
                client_id=settings.AZURE_OPENAI_CLIENT_ID,
                client_secret=settings.AZURE_OPENAI_CLIENT_SECRET.get_secret_value(),
                token_url=token_url,
                scope=resource,
            )

        elif mode == "managed_identity":
            return AzureManagedIdentityProvider(resource=resource, client_id=settings.AZURE_OPENAI_CLIENT_ID)

        else:
            raise ValueError(f"Unsupported Azure OpenAI auth mode: {mode}")
