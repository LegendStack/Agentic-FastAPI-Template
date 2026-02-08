import os
import sys

# Add src to path
sys.path.append(os.path.abspath("."))

from src.app.core.config import settings

print(f"DATABASE_URL: {settings.POSTGRES_URI}")
print(f"FULL_URL: {settings.POSTGRES_ASYNC_PREFIX}{settings.POSTGRES_URI}")
