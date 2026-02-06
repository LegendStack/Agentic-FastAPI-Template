import os
from enum import Enum
from typing import Any

from pydantic import SecretStr, computed_field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


# HACK: Force purge of poisoned environment variables that persist in the session
# This ensures we load from .env instead of the stale environment
for key in ["JIRA_URL", "JIRA_USERNAME", "JIRA_API_TOKEN", "JIRA_PROJECTS"]:
    if key in os.environ:
        # Check if it matches the stale "mtall" value to be safe, or just nuke it
        # Nuke it to be sure we prefer .env for these specific keys
        del os.environ[key]

class AppSettings(BaseSettings):
    APP_NAME: str = "Agentic FastAPI Template"
    APP_DESCRIPTION: str | None = "Enterprise-ready Agentic AI template built on top of FastAPI and LangGraph."
    APP_VERSION: str | None = "2.1.0"
    LICENSE_NAME: str | None = "MIT"
    CONTACT_NAME: str | None = "LegendStack"
    CONTACT_EMAIL: str | None = "manohar@tallapaneni.com"


class CryptSettings(BaseSettings):
    SECRET_KEY: SecretStr = SecretStr("secret-key")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7


class FileLoggerSettings(BaseSettings):
    FILE_LOG_MAX_BYTES: int = 10 * 1024 * 1024
    FILE_LOG_BACKUP_COUNT: int = 5
    FILE_LOG_FORMAT_JSON: bool = True
    FILE_LOG_LEVEL: str = "INFO"

    # Include request ID, path, method, client host, and status code in the file log
    FILE_LOG_INCLUDE_REQUEST_ID: bool = True
    FILE_LOG_INCLUDE_PATH: bool = True
    FILE_LOG_INCLUDE_METHOD: bool = True
    FILE_LOG_INCLUDE_CLIENT_HOST: bool = True
    FILE_LOG_INCLUDE_STATUS_CODE: bool = True


class ConsoleLoggerSettings(BaseSettings):
    CONSOLE_LOG_LEVEL: str = "INFO"
    CONSOLE_LOG_FORMAT_JSON: bool = False

    # Include request ID, path, method, client host, and status code in the console log
    CONSOLE_LOG_INCLUDE_REQUEST_ID: bool = False
    CONSOLE_LOG_INCLUDE_PATH: bool = False
    CONSOLE_LOG_INCLUDE_METHOD: bool = False
    CONSOLE_LOG_INCLUDE_CLIENT_HOST: bool = False
    CONSOLE_LOG_INCLUDE_STATUS_CODE: bool = False


class DatabaseSettings(BaseSettings):
    pass


class SQLiteSettings(DatabaseSettings):
    SQLITE_URI: str = "./sql_app.db"
    SQLITE_SYNC_PREFIX: str = "sqlite:///"
    SQLITE_ASYNC_PREFIX: str = "sqlite+aiosqlite:///"


class MySQLSettings(DatabaseSettings):
    MYSQL_USER: str = "username"
    MYSQL_PASSWORD: str = "password"
    MYSQL_SERVER: str = "localhost"
    MYSQL_PORT: int = 5432
    MYSQL_DB: str = "dbname"
    MYSQL_SYNC_PREFIX: str = "mysql://"
    MYSQL_ASYNC_PREFIX: str = "mysql+aiomysql://"
    MYSQL_URL: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def MYSQL_URI(self) -> str:
        credentials = f"{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
        location = f"{self.MYSQL_SERVER}:{self.MYSQL_PORT}/{self.MYSQL_DB}"
        return f"{credentials}@{location}"


class PostgresSettings(DatabaseSettings):
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "postgres"
    POSTGRES_SYNC_PREFIX: str = "postgresql://"
    POSTGRES_ASYNC_PREFIX: str = "postgresql+asyncpg://"
    POSTGRES_URL: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def POSTGRES_URI(self) -> str:
        credentials = f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
        location = f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        return f"{credentials}@{location}"


class FirstUserSettings(BaseSettings):
    ADMIN_NAME: str = "admin"
    ADMIN_EMAIL: str = "admin@admin.com"
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "!Ch4ng3Th1sP4ssW0rd!"


class TestSettings(BaseSettings): ...


class RedisCacheSettings(BaseSettings):
    REDIS_CACHE_HOST: str = "localhost"
    REDIS_CACHE_PORT: int = 6379

    @computed_field  # type: ignore[prop-decorator]
    @property
    def REDIS_CACHE_URL(self) -> str:
        return f"redis://{self.REDIS_CACHE_HOST}:{self.REDIS_CACHE_PORT}"


class ClientSideCacheSettings(BaseSettings):
    CLIENT_CACHE_MAX_AGE: int = 60


class RedisQueueSettings(BaseSettings):
    REDIS_QUEUE_HOST: str = "localhost"
    REDIS_QUEUE_PORT: int = 6379


class RedisRateLimiterSettings(BaseSettings):
    REDIS_RATE_LIMIT_HOST: str = "localhost"
    REDIS_RATE_LIMIT_PORT: int = 6379

    @computed_field  # type: ignore[prop-decorator]
    @property
    def REDIS_RATE_LIMIT_URL(self) -> str:
        return f"redis://{self.REDIS_RATE_LIMIT_HOST}:{self.REDIS_RATE_LIMIT_PORT}"


class GraphSettings(BaseSettings):
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: SecretStr = SecretStr("password")


class FrameworkExpansionSettings(BaseSettings):
    # Semantic Cache
    ENABLE_SEMANTIC_CACHE: bool = False
    SEMANTIC_CACHE_THRESHOLD: float = 0.95  # Standard threshold (safe with targeted embedding)
    SEMANTIC_CACHE_TTL: int = 3600 * 24  # 24 hours

    # Reflector
    ENABLE_REFLECTOR: bool = True
    REFLECTOR_THRESHOLD: float = 0.8

    # Parsing (Unstructured)
    PREFER_UNSTRUCTURED: bool = True


class DefaultRateLimitSettings(BaseSettings):
    DEFAULT_RATE_LIMIT_LIMIT: int = 10
    DEFAULT_RATE_LIMIT_PERIOD: int = 3600


class CRUDAdminSettings(BaseSettings):
    CRUD_ADMIN_ENABLED: bool = True
    CRUD_ADMIN_MOUNT_PATH: str = "/admin"

    CRUD_ADMIN_ALLOWED_IPS_LIST: list[str] | None = None
    CRUD_ADMIN_ALLOWED_NETWORKS_LIST: list[str] | None = None
    CRUD_ADMIN_MAX_SESSIONS: int = 10
    CRUD_ADMIN_SESSION_TIMEOUT: int = 1440
    SESSION_SECURE_COOKIES: bool = True

    CRUD_ADMIN_TRACK_EVENTS: bool = True
    CRUD_ADMIN_TRACK_SESSIONS: bool = True

    CRUD_ADMIN_REDIS_ENABLED: bool = False
    CRUD_ADMIN_REDIS_HOST: str = "localhost"
    CRUD_ADMIN_REDIS_PORT: int = 6379
    CRUD_ADMIN_REDIS_DB: int = 0
    CRUD_ADMIN_REDIS_PASSWORD: str | None = "None"
    CRUD_ADMIN_REDIS_SSL: bool = False


class EnvironmentOption(str, Enum):
    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"


class EnvironmentSettings(BaseSettings):
    ENVIRONMENT: EnvironmentOption = EnvironmentOption.LOCAL


class CORSSettings(BaseSettings):
    CORS_ORIGINS: list[str] = ["*"]
    CORS_METHODS: list[str] = ["*"]
    CORS_HEADERS: list[str] = ["*"]


class AuthProvider(str, Enum):
    LOCAL = "local"
    ENTRA = "entra"


class RAGBackend(str, Enum):
    PGVECTOR = "pgvector"
    AZURE_SEARCH = "azure_search"
    REDIS = "redis"


class AuthSettings(BaseSettings):
    AUTH_PROVIDER: AuthProvider = AuthProvider.LOCAL
    AZURE_TENANT_ID: str | None = None
    AZURE_CLIENT_ID: str | None = None
    ENTRA_JWKS_URL: str = "https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
    ENTRA_ISSUER: str = "https://login.microsoftonline.com/{tenant_id}/v2.0"
    ENTRA_ROLE_MAPPING: dict[str, Any] = {}


class AISettings(BaseSettings):
    # Azure OpenAI
    AZURE_OPENAI_API_KEY: SecretStr | None = None
    AZURE_OPENAI_ENDPOINT: str | None = None
    AZURE_OPENAI_AD_TOKEN: SecretStr | None = None
    AZURE_OPENAI_API_VERSION: str = "2023-05-15"
    AZURE_OPENAI_CHAT_DEPLOYMENT_NAME: str = "gpt-4"
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME: str = "text-embedding-ada-002"
    AZURE_OPENAI_AUTH_MODE: str = "api_key"  # api_key | oauth2 | managed_identity
    AZURE_OPENAI_CLIENT_ID: str | None = None
    AZURE_OPENAI_CLIENT_SECRET: SecretStr | None = None

    RAG_BACKEND: RAGBackend = RAGBackend.PGVECTOR

    # Azure AI Search (Optional)
    AZURE_SEARCH_ENDPOINT: str | None = None
    AZURE_SEARCH_KEY: SecretStr | None = None
    AZURE_SEARCH_INDEX_NAME: str = "agent-index"
    AZURE_SEARCH_AUTH_MODE: str = "api_key"  # api_key | oauth2 | managed_identity
    AZURE_SEARCH_CLIENT_ID: str | None = None
    AZURE_SEARCH_CLIENT_SECRET: SecretStr | None = None

    # Redis Vector Store (Optional)
    REDIS_VECTOR_URL: str | None = None
    REDIS_VECTOR_INDEX_NAME: str = "agent-index"

    # Jira
    JIRA_URL: str | None = None
    JIRA_USERNAME: str | None = None
    JIRA_API_TOKEN: SecretStr | None = None
    JIRA_PROJECTS: list[str] = []
    JIRA_AUTH_MODE: str = "pat"  # pat | basic | oauth2
    JIRA_CLIENT_ID: str | None = None
    JIRA_CLIENT_SECRET: SecretStr | None = None
    JIRA_REFRESH_TOKEN: str | None = None
    JIRA_CLOUD_ID: str | None = None
    # Backlog Agent Settings (Enterprise Decomposition)
    BACKLOG_USE_MOCKS: bool = False

    # Jira Field Mapping
    JIRA_FIELD_MAP_ACCEPTANCE_CRITERIA: str | None = None
    JIRA_FIELD_MAP_TECH_NOTES: str | None = None
    JIRA_FIELD_MAP_COMPLEXITY: str | None = None
    JIRA_FIELD_MAP_DEPENDENCIES: str | None = None
    JIRA_FIELD_MAP_PRIORITY: str | None = None

    # Jira Epic Configuration
    JIRA_EPIC_ISSUE_TYPE: str = "Epic"
    JIRA_EPIC_NAME_FIELD: str | None = "customfield_10011"

    # Confluence (Optional)
    CONFLUENCE_URL: str | None = None
    CONFLUENCE_USERNAME: str | None = None
    CONFLUENCE_API_TOKEN: SecretStr | None = None
    CONFLUENCE_SPACES: list[str] = []
    CONFLUENCE_AUTH_MODE: str = "pat"  # pat | basic | oauth2
    CONFLUENCE_CLIENT_ID: str | None = None
    CONFLUENCE_CLIENT_SECRET: SecretStr | None = None
    CONFLUENCE_REFRESH_TOKEN: str | None = None
    CONFLUENCE_CLOUD_ID: str | None = None

    # SharePoint (Optional)
    SHAREPOINT_SITE_URL: str | None = None
    SHAREPOINT_CLIENT_ID: str | None = None
    SHAREPOINT_CLIENT_SECRET: SecretStr | None = None
    SHAREPOINT_AUTH_MODE: str = "oauth2"  # oauth2 | managed_identity

    # Microsoft Graph (Optional)
    GRAPH_CLIENT_ID: str | None = None
    GRAPH_CLIENT_SECRET: SecretStr | None = None
    GRAPH_AUTH_MODE: str = "oauth2"  # oauth2 | managed_identity

    # Azure Blob Storage (Optional)
    AZURE_BLOB_ACCOUNT_URL: str | None = None
    AZURE_BLOB_CONNECTION_STRING: SecretStr | None = None
    AZURE_BLOB_AUTH_MODE: str = "api_key"  # api_key | oauth2 | managed_identity

    # Cohere Reranking (Optional)
    COHERE_API_KEY: SecretStr | None = None
    COHERE_RERANK_MODEL: str = "rerank-english-v2.0"


class ObservabilitySettings(BaseSettings):
    # OpenTelemetry
    OTEL_ENABLED: bool = False
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"

    # Datadog
    DD_SERVICE: str = "fastapi-agent"
    DD_ENV: str = "local"
    DD_VERSION: str = "2.0.0"


class AgentRateLimitSettings(BaseSettings):
    # Default rate limit tier for new tenants
    DEFAULT_RATE_LIMIT_TIER: str = "standard"  # free, standard, premium, enterprise


class Settings(
    AppSettings,
    SQLiteSettings,
    PostgresSettings,
    CryptSettings,
    FirstUserSettings,
    TestSettings,
    RedisCacheSettings,
    ClientSideCacheSettings,
    RedisQueueSettings,
    RedisRateLimiterSettings,
    DefaultRateLimitSettings,
    CRUDAdminSettings,
    EnvironmentSettings,
    CORSSettings,
    FileLoggerSettings,
    ConsoleLoggerSettings,
    AuthSettings,
    AISettings,
    ObservabilitySettings,
    AgentRateLimitSettings,
    GraphSettings,
):
    # --- Framework Expansion (V4.0) ---
    ENABLE_SEMANTIC_CACHE: bool = True
    SEMANTIC_CACHE_THRESHOLD: float = 0.98
    SEMANTIC_CACHE_TTL: int = 3600 * 24

    ENABLE_REFLECTOR: bool = True
    REFLECTOR_THRESHOLD: float = 0.8

    PREFER_UNSTRUCTURED: bool = True

    # --- Intelligence & Memory (V4.1) ---
    ENABLE_ENTITY_MEMORY: bool = False  # Track entities across threads
    ENTITY_EXTRACTION_MODEL: str = "gpt-4o"
    ENTITY_SIMILARITY_THRESHOLD: float = 0.85
    
    @computed_field  # type: ignore[prop-decorator]
    @property
    def REDIS_URL(self) -> str:
        """Alias for semantic caching and other integrations."""
        return self.REDIS_CACHE_URL

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        from .vault import VaultSettingsSource
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            VaultSettingsSource(settings_cls), # Vault takes precedence over defaults, but env/init override it? 
            # Ideally: Init > Env > DotEnv > Vault > Defaults
            # Or: Init > Env > Vault > DotEnv > Defaults?
            # User usually wants Vault to provide secrets that are NOT in env.
            # But if a user EXPLICITLY sets an env var locally, it should probably win for debugging.
            # So: Init > Env > DotEnv > Vault
            file_secret_settings,
        )


settings = Settings()
