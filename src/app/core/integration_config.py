"""
Integration Auto-Configuration.
===============================
Automatically configures integration clients from environment settings.

Usage:
    from app.core.integration_config import configure_integrations, get_client

    # Configure all integrations from environment
    configure_integrations()

    # Get configured clients
    openai = get_client(Integration.AZURE_OPENAI)
"""

import logging

from .clients import (
    AzureOpenAIClient,
    AzureSearchClient,
    CohereClient,
    ConfluenceClient,
    Integration,
    IntegrationClientFactory,
    IntegrationConfig,
    JiraClient,
    MicrosoftGraphClient,
    client_factory,
)
from .credentials import AuthMode

logger = logging.getLogger(__name__)


def _parse_auth_mode(mode_str: str | None, default: AuthMode = AuthMode.API_KEY) -> AuthMode:
    """Parse auth mode string to enum."""
    if not mode_str:
        return default
    mode_map = {
        "api_key": AuthMode.API_KEY,
        "key": AuthMode.API_KEY,
        "oauth2": AuthMode.OAUTH2,
        "oauth": AuthMode.OAUTH2,
        "managed_identity": AuthMode.MANAGED_IDENTITY,
        "mi": AuthMode.MANAGED_IDENTITY,
        "pat": AuthMode.PAT,
        "basic": AuthMode.BASIC,
    }
    return mode_map.get(mode_str.lower(), default)


def configure_integrations(factory: IntegrationClientFactory | None = None) -> None:
    """
    Configure all integrations from environment settings.

    Reads settings from app.core.config.settings and configures the client factory.
    """
    from .config import settings

    factory = factory or client_factory

    # -------------------------------------------------------------------------
    # Azure OpenAI
    # -------------------------------------------------------------------------
    if settings.AZURE_OPENAI_ENDPOINT:
        auth_mode = _parse_auth_mode(
            getattr(settings, "AZURE_OPENAI_AUTH_MODE", None),
            AuthMode.API_KEY if settings.AZURE_OPENAI_API_KEY else AuthMode.MANAGED_IDENTITY,
        )

        config = IntegrationConfig(
            name=Integration.AZURE_OPENAI,
            auth_mode=auth_mode,
            base_url=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY.get_secret_value() if settings.AZURE_OPENAI_API_KEY else None,
            client_id=getattr(settings, "AZURE_OPENAI_CLIENT_ID", None),
            client_secret=getattr(settings, "AZURE_OPENAI_CLIENT_SECRET", None)
            and getattr(settings, "AZURE_OPENAI_CLIENT_SECRET").get_secret_value(),
            tenant_id=settings.AZURE_TENANT_ID,
            scope="https://cognitiveservices.azure.com/.default",
            resource="https://cognitiveservices.azure.com/",
        )
        factory.configure(config)
        logger.info(f"Azure OpenAI configured with {auth_mode.value} auth")

    # -------------------------------------------------------------------------
    # Azure AI Search
    # -------------------------------------------------------------------------
    if settings.AZURE_SEARCH_ENDPOINT:
        auth_mode = _parse_auth_mode(
            getattr(settings, "AZURE_SEARCH_AUTH_MODE", None),
            AuthMode.API_KEY if settings.AZURE_SEARCH_KEY else AuthMode.MANAGED_IDENTITY,
        )

        config = IntegrationConfig(
            name=Integration.AZURE_SEARCH,
            auth_mode=auth_mode,
            base_url=settings.AZURE_SEARCH_ENDPOINT,
            api_key=settings.AZURE_SEARCH_KEY.get_secret_value() if settings.AZURE_SEARCH_KEY else None,
            client_id=getattr(settings, "AZURE_SEARCH_CLIENT_ID", None),
            client_secret=getattr(settings, "AZURE_SEARCH_CLIENT_SECRET", None)
            and getattr(settings, "AZURE_SEARCH_CLIENT_SECRET").get_secret_value(),
            tenant_id=settings.AZURE_TENANT_ID,
            scope="https://search.azure.com/.default",
            resource="https://search.azure.com/",
        )
        factory.configure(config)
        logger.info(f"Azure AI Search configured with {auth_mode.value} auth")

    # -------------------------------------------------------------------------
    # Microsoft Graph
    # -------------------------------------------------------------------------
    graph_client_id = getattr(settings, "GRAPH_CLIENT_ID", None)
    graph_client_secret = getattr(settings, "GRAPH_CLIENT_SECRET", None)

    if graph_client_id:
        auth_mode = _parse_auth_mode(getattr(settings, "GRAPH_AUTH_MODE", None), AuthMode.OAUTH2)

        config = IntegrationConfig(
            name=Integration.MICROSOFT_GRAPH,
            auth_mode=auth_mode,
            client_id=graph_client_id,
            client_secret=graph_client_secret.get_secret_value() if graph_client_secret else None,
            tenant_id=settings.AZURE_TENANT_ID,
            scope="https://graph.microsoft.com/.default",
        )
        factory.configure(config)
        logger.info(f"Microsoft Graph configured with {auth_mode.value} auth")

    # -------------------------------------------------------------------------
    # Jira
    # -------------------------------------------------------------------------
    if settings.JIRA_URL:
        auth_mode = _parse_auth_mode(
            getattr(settings, "JIRA_AUTH_MODE", None), AuthMode.PAT if settings.JIRA_API_TOKEN else AuthMode.OAUTH2
        )

        if auth_mode == AuthMode.PAT:
            config = IntegrationConfig(
                name=Integration.JIRA,
                auth_mode=AuthMode.PAT,
                base_url=settings.JIRA_URL,
                token=settings.JIRA_API_TOKEN.get_secret_value() if settings.JIRA_API_TOKEN else None,
            )
        elif auth_mode == AuthMode.BASIC:
            config = IntegrationConfig(
                name=Integration.JIRA,
                auth_mode=AuthMode.BASIC,
                base_url=settings.JIRA_URL,
                username=settings.JIRA_USERNAME,
                password=settings.JIRA_API_TOKEN.get_secret_value() if settings.JIRA_API_TOKEN else None,
            )
        else:
            # OAuth2 for Jira Cloud
            config = IntegrationConfig(
                name=Integration.JIRA,
                auth_mode=AuthMode.OAUTH2,
                base_url=settings.JIRA_URL,
                client_id=getattr(settings, "JIRA_CLIENT_ID", None),
                client_secret=getattr(settings, "JIRA_CLIENT_SECRET", None)
                and getattr(settings, "JIRA_CLIENT_SECRET").get_secret_value(),
                refresh_token=getattr(settings, "JIRA_REFRESH_TOKEN", None),
                cloud_id=getattr(settings, "JIRA_CLOUD_ID", None),
            )

        factory.configure(config)
        logger.info(f"Jira configured with {auth_mode.value} auth")

    # -------------------------------------------------------------------------
    # Confluence
    # -------------------------------------------------------------------------
    if settings.CONFLUENCE_URL:
        auth_mode = _parse_auth_mode(
            getattr(settings, "CONFLUENCE_AUTH_MODE", None),
            AuthMode.PAT if settings.CONFLUENCE_API_TOKEN else AuthMode.OAUTH2,
        )

        if auth_mode == AuthMode.PAT:
            config = IntegrationConfig(
                name=Integration.CONFLUENCE,
                auth_mode=AuthMode.PAT,
                base_url=settings.CONFLUENCE_URL,
                token=settings.CONFLUENCE_API_TOKEN.get_secret_value() if settings.CONFLUENCE_API_TOKEN else None,
            )
        elif auth_mode == AuthMode.BASIC:
            config = IntegrationConfig(
                name=Integration.CONFLUENCE,
                auth_mode=AuthMode.BASIC,
                base_url=settings.CONFLUENCE_URL,
                username=settings.CONFLUENCE_USERNAME,
                password=settings.CONFLUENCE_API_TOKEN.get_secret_value() if settings.CONFLUENCE_API_TOKEN else None,
            )
        else:
            # OAuth2 for Confluence Cloud
            config = IntegrationConfig(
                name=Integration.CONFLUENCE,
                auth_mode=AuthMode.OAUTH2,
                base_url=settings.CONFLUENCE_URL,
                client_id=getattr(settings, "CONFLUENCE_CLIENT_ID", None),
                client_secret=getattr(settings, "CONFLUENCE_CLIENT_SECRET", None)
                and getattr(settings, "CONFLUENCE_CLIENT_SECRET").get_secret_value(),
                refresh_token=getattr(settings, "CONFLUENCE_REFRESH_TOKEN", None),
                cloud_id=getattr(settings, "CONFLUENCE_CLOUD_ID", None),
            )

        factory.configure(config)
        logger.info(f"Confluence configured with {auth_mode.value} auth")

    # -------------------------------------------------------------------------
    # SharePoint (uses Microsoft Graph)
    # -------------------------------------------------------------------------
    if settings.SHAREPOINT_SITE_URL:
        auth_mode = _parse_auth_mode(getattr(settings, "SHAREPOINT_AUTH_MODE", None), AuthMode.OAUTH2)

        config = IntegrationConfig(
            name=Integration.SHAREPOINT,
            auth_mode=auth_mode,
            base_url=settings.SHAREPOINT_SITE_URL,
            client_id=settings.SHAREPOINT_CLIENT_ID,
            client_secret=settings.SHAREPOINT_CLIENT_SECRET.get_secret_value()
            if settings.SHAREPOINT_CLIENT_SECRET
            else None,
            tenant_id=settings.AZURE_TENANT_ID,
            scope="https://graph.microsoft.com/.default",
        )
        factory.configure(config)
        logger.info(f"SharePoint configured with {auth_mode.value} auth")

    # -------------------------------------------------------------------------
    # Cohere (for reranking)
    # -------------------------------------------------------------------------
    if settings.COHERE_API_KEY:
        config = IntegrationConfig(
            name=Integration.COHERE,
            auth_mode=AuthMode.API_KEY,
            api_key=settings.COHERE_API_KEY.get_secret_value(),
        )
        factory.configure(config)
        logger.info("Cohere configured with API key auth")

    # -------------------------------------------------------------------------
    # Azure Blob Storage
    # -------------------------------------------------------------------------
    blob_connection_string = getattr(settings, "AZURE_BLOB_CONNECTION_STRING", None)
    blob_account_url = getattr(settings, "AZURE_BLOB_ACCOUNT_URL", None)

    if blob_connection_string or blob_account_url:
        auth_mode = _parse_auth_mode(
            getattr(settings, "AZURE_BLOB_AUTH_MODE", None),
            AuthMode.API_KEY if blob_connection_string else AuthMode.MANAGED_IDENTITY,
        )

        config = IntegrationConfig(
            name=Integration.AZURE_BLOB,
            auth_mode=auth_mode,
            base_url=blob_account_url,
            api_key=blob_connection_string.get_secret_value()
            if blob_connection_string and hasattr(blob_connection_string, "get_secret_value")
            else blob_connection_string,
            tenant_id=settings.AZURE_TENANT_ID,
            resource="https://storage.azure.com/",
        )
        factory.configure(config)
        logger.info(f"Azure Blob Storage configured with {auth_mode.value} auth")


# =============================================================================
# Convenience Functions
# =============================================================================


def get_azure_openai_client() -> AzureOpenAIClient | None:
    """Get configured Azure OpenAI client."""
    from .config import settings

    if not client_factory.is_configured(Integration.AZURE_OPENAI):
        return None
    return AzureOpenAIClient(client_factory, settings.AZURE_OPENAI_ENDPOINT)


def get_azure_search_client() -> AzureSearchClient | None:
    """Get configured Azure AI Search client."""
    from .config import settings

    if not client_factory.is_configured(Integration.AZURE_SEARCH):
        return None
    return AzureSearchClient(client_factory, settings.AZURE_SEARCH_ENDPOINT, settings.AZURE_SEARCH_INDEX_NAME)


def get_microsoft_graph_client() -> MicrosoftGraphClient | None:
    """Get configured Microsoft Graph client."""
    if not client_factory.is_configured(Integration.MICROSOFT_GRAPH):
        return None
    return MicrosoftGraphClient(client_factory)


def get_jira_client() -> JiraClient | None:
    """Get configured Jira client."""
    if not client_factory.is_configured(Integration.JIRA):
        return None
    config = client_factory.get_config(Integration.JIRA)
    return JiraClient(client_factory, config.cloud_id or "")


def get_confluence_client() -> ConfluenceClient | None:
    """Get configured Confluence client."""
    if not client_factory.is_configured(Integration.CONFLUENCE):
        return None
    config = client_factory.get_config(Integration.CONFLUENCE)
    return ConfluenceClient(client_factory, config.cloud_id or "")


def get_cohere_client() -> CohereClient | None:
    """Get configured Cohere client."""
    if not client_factory.is_configured(Integration.COHERE):
        return None
    return CohereClient(client_factory)


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "configure_integrations",
    "client_factory",
    "get_azure_openai_client",
    "get_azure_search_client",
    "get_microsoft_graph_client",
    "get_jira_client",
    "get_confluence_client",
    "get_cohere_client",
    "Integration",
]
