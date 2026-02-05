import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .admin.initialize import create_admin_interface
from .api import router
import logging
logger = logging.getLogger(__name__)

from .core.config import settings
from .core.setup import create_application, lifespan_factory

logger.info(f"--- STARTUP CONFIG: AZURE_OPENAI_ENDPOINT={settings.AZURE_OPENAI_ENDPOINT} ---")
logger.info(f"--- STARTUP CONFIG: BACKLOG_USE_MOCKS={settings.BACKLOG_USE_MOCKS} ---")

admin = create_admin_interface()


@asynccontextmanager
async def lifespan_with_admin(app: FastAPI) -> AsyncGenerator[None, None]:
    """Custom lifespan that includes admin initialization and OpenTelemetry."""
    # Get the default lifespan
    default_lifespan = lifespan_factory(settings)
    
    # Configure all integrations (Semantic Cache, Jira, etc.)
    try:
        from .core.integration_config import configure_integrations
        configure_integrations()
    except Exception as e:
        logger.warning(f"Integration configuration failed: {e}")

    # Initialize OpenTelemetry if enabled
    if settings.OTEL_ENABLED:
        try:
            from .agents.observability import setup_telemetry

            setup_telemetry(app=app)
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(f"OpenTelemetry setup failed: {e}")

    # Run the default lifespan initialization and our admin initialization
    async with default_lifespan(app):
        # Initialize admin interface if it exists
        if admin:
            # Initialize admin database and setup
            await admin.initialize()

        yield


app = create_application(router=router, settings=settings, lifespan=lifespan_with_admin)

# Mount admin interface if enabled
if admin:
    app.mount(settings.CRUD_ADMIN_MOUNT_PATH, admin.app)
