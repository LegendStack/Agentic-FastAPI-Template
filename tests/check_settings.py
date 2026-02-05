from src.app.core.config import settings
import os

print(f"Current Working Directory: {os.getcwd()}")
print(f"BACKLOG_USE_MOCKS from settings: {settings.BACKLOG_USE_MOCKS}")
print(f"RAG_BACKEND from settings: {settings.RAG_BACKEND}")
print(f"JIRA_URL: {settings.JIRA_URL}")
expected_url = "https://manoprotechie-1765337128600.atlassian.net"
if str(settings.JIRA_URL).rstrip('/') == expected_url:
    print("✅ JIRA_URL matches .env")
else:
    print(f"❌ JIRA_URL MISMATCH! Expected {expected_url}, got {settings.JIRA_URL}")
print(f"AZURE_OPENAI_ENDPOINT: {settings.AZURE_OPENAI_ENDPOINT}")

# Check if .env file exists where pydantic thinks it is
env_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "src", ".env")
print(f"Checking for .env at: {env_path}")
print(f"Exists: {os.path.exists(env_path)}")
