"""
Integration Clients.
====================
High-level clients for external integrations with pluggable authentication.

Each client auto-configures authentication based on environment settings.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .credentials import (
    ApiKeyProvider,
    AtlassianOAuth2Provider,
    AuthMode,
    AzureManagedIdentityProvider,
    BaseCredentialProvider,
    BasicAuthProvider,
    Credentials,
    OAuth2ClientCredentialsProvider,
    PatProvider,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Integration Definitions
# =============================================================================


class Integration(str, Enum):
    """Supported integrations."""

    AZURE_OPENAI = "azure_openai"
    AZURE_SEARCH = "azure_search"
    AZURE_BLOB = "azure_blob"
    MICROSOFT_GRAPH = "microsoft_graph"
    JIRA = "jira"
    CONFLUENCE = "confluence"
    SHAREPOINT = "sharepoint"
    COHERE = "cohere"


@dataclass
class IntegrationConfig:
    """Configuration for an integration."""

    name: Integration
    auth_mode: AuthMode
    base_url: str | None = None

    # API Key auth
    api_key: str | None = None
    api_key_header: str = "api-key"

    # OAuth2 / Azure AD
    client_id: str | None = None
    client_secret: str | None = None
    tenant_id: str | None = None
    scope: str | None = None
    resource: str | None = None

    # PAT / Basic Auth
    username: str | None = None
    password: str | None = None
    token: str | None = None

    # Atlassian-specific
    cloud_id: str | None = None
    refresh_token: str | None = None


# =============================================================================
# Client Factory
# =============================================================================


class IntegrationClientFactory:
    """
    Factory for creating integration clients with appropriate authentication.

    Usage:
        factory = IntegrationClientFactory()

        # Get Azure OpenAI client
        openai_client = await factory.get_client(Integration.AZURE_OPENAI)

        # Or with custom config
        config = IntegrationConfig(
            name=Integration.JIRA,
            auth_mode=AuthMode.OAUTH2,
            client_id="...",
            ...
        )
        jira_client = await factory.get_client_with_config(config)
    """

    def __init__(self):
        self._providers: dict[Integration, BaseCredentialProvider] = {}
        self._configs: dict[Integration, IntegrationConfig] = {}

    def configure(self, config: IntegrationConfig) -> None:
        """Configure an integration."""
        self._configs[config.name] = config
        self._providers[config.name] = self._create_provider(config)
        logger.info(f"Configured {config.name.value} with {config.auth_mode.value} auth")

    def _create_provider(self, config: IntegrationConfig) -> BaseCredentialProvider:
        """Create the appropriate credential provider for the config."""

        if config.auth_mode == AuthMode.API_KEY:
            if not config.api_key:
                raise ValueError(f"API key required for {config.name}")
            return ApiKeyProvider(config.api_key, config.api_key_header)

        elif config.auth_mode == AuthMode.PAT:
            if not config.token:
                raise ValueError(f"Token required for {config.name}")
            return PatProvider(config.token)

        elif config.auth_mode == AuthMode.BASIC:
            if not config.username or not config.password:
                raise ValueError(f"Username and password required for {config.name}")
            return BasicAuthProvider(config.username, config.password)

        elif config.auth_mode == AuthMode.OAUTH2:
            # Determine OAuth2 type based on integration
            if config.name in (Integration.JIRA, Integration.CONFLUENCE):
                if not all([config.client_id, config.client_secret, config.refresh_token]):
                    raise ValueError(f"OAuth2 credentials required for {config.name}")
                return AtlassianOAuth2Provider(
                    client_id=config.client_id,
                    client_secret=config.client_secret,
                    refresh_token=config.refresh_token,
                    cloud_id=config.cloud_id or "",
                )
            else:
                # Azure AD / Standard OAuth2
                if not all([config.client_id, config.client_secret, config.tenant_id]):
                    raise ValueError(f"OAuth2 credentials required for {config.name}")

                token_url = f"https://login.microsoftonline.com/{config.tenant_id}/oauth2/v2.0/token"

                return OAuth2ClientCredentialsProvider(
                    client_id=config.client_id,
                    client_secret=config.client_secret,
                    token_url=token_url,
                    scope=config.scope,
                    resource=config.resource,
                )

        elif config.auth_mode == AuthMode.MANAGED_IDENTITY:
            if not config.resource:
                raise ValueError("Resource URL required for managed identity")
            return AzureManagedIdentityProvider(
                resource=config.resource,
                client_id=config.client_id,  # Optional for user-assigned MI
            )

        raise ValueError(f"Unsupported auth mode: {config.auth_mode}")

    async def get_credentials(self, integration: Integration) -> Credentials:
        """Get credentials for an integration."""
        if integration not in self._providers:
            raise ValueError(f"Integration {integration.value} not configured")
        return await self._providers[integration].get_credentials()

    def get_config(self, integration: Integration) -> IntegrationConfig | None:
        """Get configuration for an integration."""
        return self._configs.get(integration)

    def is_configured(self, integration: Integration) -> bool:
        """Check if an integration is configured."""
        return integration in self._providers


# =============================================================================
# Pre-configured Client Wrappers
# =============================================================================


class AzureOpenAIClient:
    """
    Azure OpenAI client with flexible authentication.

    Usage:
        client = AzureOpenAIClient(factory, endpoint="https://...")
        response = await client.chat(messages=[...])
    """

    def __init__(self, factory: IntegrationClientFactory, endpoint: str):
        self.factory = factory
        self.endpoint = endpoint.rstrip("/")

    async def _get_headers(self) -> dict[str, str]:
        creds = await self.factory.get_credentials(Integration.AZURE_OPENAI)
        headers = creds.get_auth_header()
        headers["Content-Type"] = "application/json"
        return headers

    async def chat(
        self, messages: list, deployment: str, api_version: str = "2024-02-15-preview", **kwargs
    ) -> dict[str, Any]:
        """Send a chat completion request."""
        import httpx

        url = f"{self.endpoint}/openai/deployments/{deployment}/chat/completions"
        headers = await self._get_headers()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url, params={"api-version": api_version}, headers=headers, json={"messages": messages, **kwargs}
            )
            response.raise_for_status()
            return response.json()

    async def embed(
        self, texts: list[str], deployment: str, api_version: str = "2024-02-15-preview"
    ) -> list[list[float]]:
        """Get embeddings for texts."""
        import httpx

        url = f"{self.endpoint}/openai/deployments/{deployment}/embeddings"
        headers = await self._get_headers()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url, params={"api-version": api_version}, headers=headers, json={"input": texts}
            )
            response.raise_for_status()
            data = response.json()
            return [item["embedding"] for item in data["data"]]


class AzureSearchClient:
    """
    Azure AI Search client with flexible authentication.
    """

    def __init__(self, factory: IntegrationClientFactory, endpoint: str, index_name: str):
        self.factory = factory
        self.endpoint = endpoint.rstrip("/")
        self.index_name = index_name

    async def _get_headers(self) -> dict[str, str]:
        creds = await self.factory.get_credentials(Integration.AZURE_SEARCH)
        headers = creds.get_auth_header()
        headers["Content-Type"] = "application/json"
        return headers

    async def search(
        self, search_text: str = "*", filter: str | None = None, top: int = 10, api_version: str = "2024-07-01"
    ) -> dict[str, Any]:
        """Execute a search query."""
        import httpx

        url = f"{self.endpoint}/indexes/{self.index_name}/docs/search"
        headers = await self._get_headers()

        body = {"search": search_text, "top": top}
        if filter:
            body["filter"] = filter

        async with httpx.AsyncClient() as client:
            response = await client.post(url, params={"api-version": api_version}, headers=headers, json=body)
            response.raise_for_status()
            return response.json()

    async def vector_search(
        self,
        vector: list[float],
        vector_field: str = "contentVector",
        k: int = 10,
        filter: str | None = None,
        api_version: str = "2024-07-01",
    ) -> dict[str, Any]:
        """Execute a vector search."""
        import httpx

        url = f"{self.endpoint}/indexes/{self.index_name}/docs/search"
        headers = await self._get_headers()

        body = {"vectorQueries": [{"kind": "vector", "vector": vector, "k": k, "fields": vector_field}]}
        if filter:
            body["filter"] = filter

        async with httpx.AsyncClient() as client:
            response = await client.post(url, params={"api-version": api_version}, headers=headers, json=body)
            response.raise_for_status()
            return response.json()


class MicrosoftGraphClient:
    """
    Microsoft Graph API client.

    Provides access to OneDrive, Teams, Outlook, etc.
    """

    def __init__(self, factory: IntegrationClientFactory):
        self.factory = factory
        self.base_url = "https://graph.microsoft.com/v1.0"

    async def _get_headers(self) -> dict[str, str]:
        creds = await self.factory.get_credentials(Integration.MICROSOFT_GRAPH)
        headers = creds.get_auth_header()
        headers["Content-Type"] = "application/json"
        return headers

    async def get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        """Make a GET request to Graph API."""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}{path}", headers=await self._get_headers(), params=params)
            response.raise_for_status()
            return response.json()

    async def post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        """Make a POST request to Graph API."""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}{path}", headers=await self._get_headers(), json=data)
            response.raise_for_status()
            return response.json()

    # Convenience methods
    async def get_user(self) -> dict[str, Any]:
        """Get current user info."""
        return await self.get("/me")

    async def list_drive_items(self, path: str = "/") -> dict[str, Any]:
        """List items in OneDrive."""
        return await self.get(f"/me/drive/root:{path}:/children")

    async def send_mail(self, to: str, subject: str, body: str) -> None:
        """Send an email."""
        await self.post(
            "/me/sendMail",
            {
                "message": {
                    "subject": subject,
                    "body": {"contentType": "Text", "content": body},
                    "toRecipients": [{"emailAddress": {"address": to}}],
                }
            },
        )


class AtlassianClient:
    """
    Base client for Atlassian Cloud APIs (Jira, Confluence).
    """

    def __init__(self, factory: IntegrationClientFactory, integration: Integration, cloud_id: str):
        self.factory = factory
        self.integration = integration
        self.cloud_id = cloud_id

    @property
    def base_url(self) -> str:
        if self.integration == Integration.JIRA:
            return f"https://api.atlassian.com/ex/jira/{self.cloud_id}/rest/api/3"
        elif self.integration == Integration.CONFLUENCE:
            return f"https://api.atlassian.com/ex/confluence/{self.cloud_id}/wiki/rest/api"
        raise ValueError(f"Unknown Atlassian integration: {self.integration}")

    async def _get_headers(self) -> dict[str, str]:
        creds = await self.factory.get_credentials(self.integration)
        headers = creds.get_auth_header()
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json"
        return headers

    async def get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}{path}", headers=await self._get_headers(), params=params)
            response.raise_for_status()
            return response.json()

    async def post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}{path}", headers=await self._get_headers(), json=data)
            response.raise_for_status()
            return response.json()


class JiraClient(AtlassianClient):
    """Jira Cloud API client."""

    def __init__(self, factory: IntegrationClientFactory, cloud_id: str):
        super().__init__(factory, Integration.JIRA, cloud_id)

    async def search_issues(self, jql: str, max_results: int = 50) -> dict[str, Any]:
        """Search issues using JQL."""
        return await self.get("/search", {"jql": jql, "maxResults": max_results})

    async def get_issue(self, issue_key: str) -> dict[str, Any]:
        """Get a specific issue."""
        return await self.get(f"/issue/{issue_key}")

    async def create_issue(self, project_key: str, summary: str, issue_type: str, **fields) -> dict[str, Any]:
        """Create a new issue."""
        return await self.post(
            "/issue",
            {
                "fields": {
                    "project": {"key": project_key},
                    "summary": summary,
                    "issuetype": {"name": issue_type},
                    **fields,
                }
            },
        )


class ConfluenceClient(AtlassianClient):
    """Confluence Cloud API client."""

    def __init__(self, factory: IntegrationClientFactory, cloud_id: str):
        super().__init__(factory, Integration.CONFLUENCE, cloud_id)

    async def get_page(self, page_id: str, expand: str = "body.storage") -> dict[str, Any]:
        """Get a Confluence page."""
        return await self.get(f"/content/{page_id}", {"expand": expand})

    async def search_content(self, cql: str, limit: int = 25) -> dict[str, Any]:
        """Search content using CQL."""
        return await self.get("/content/search", {"cql": cql, "limit": limit})


class CohereClient:
    """
    Cohere API client for reranking.
    """

    def __init__(self, factory: IntegrationClientFactory):
        self.factory = factory
        self.base_url = "https://api.cohere.ai/v1"

    async def _get_headers(self) -> dict[str, str]:
        creds = await self.factory.get_credentials(Integration.COHERE)
        return {"Authorization": f"Bearer {creds.api_key}", "Content-Type": "application/json"}

    async def rerank(
        self, query: str, documents: list[str], model: str = "rerank-english-v2.0", top_n: int = 10
    ) -> dict[str, Any]:
        """Rerank documents."""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/rerank",
                headers=await self._get_headers(),
                json={"query": query, "documents": documents, "model": model, "top_n": top_n},
            )
            response.raise_for_status()
            return response.json()


# =============================================================================
# Global Factory Instance
# =============================================================================

client_factory = IntegrationClientFactory()
