import os
import sys
# Add src to sys.path
sys.path.append(os.getcwd())

from src.app.core.config import settings

print(f"BACKLOG_USE_MOCKS: {settings.BACKLOG_USE_MOCKS}")
print(f"JIRA_URL: {settings.JIRA_URL}")
print(f"AZURE_OPENAI_ENDPOINT: {settings.AZURE_OPENAI_ENDPOINT}")

# Check where it thinks .env is
config_dir = os.path.dirname(os.path.realpath(settings.__module__.split('.')[0])) # This is wrong but let's try
# Just check the path used in SettingsConfigDict
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
env_path = os.path.join(project_root, "src", ".env")
print(f"Checking for .env at: {env_path}")
print(f"Exists: {os.path.exists(env_path)}")
