import os
from dotenv import load_dotenv, dotenv_values
import sys

# Path to .env
env_path = os.path.join(os.path.dirname(__file__), "src", ".env")

print(f"--- DEBUGGING ENVIRONMENT VARIABLES ---")
print(f"Script location: {os.path.abspath(__file__)}")
print(f".env path: {env_path}")
print(f".env exists: {os.path.exists(env_path)}")

# 1. Check raw os.environ
print(f"\n[RAW os.environ]")
print(f"JIRA_URL: {os.environ.get('JIRA_URL')}")
print(f"JIRA_USERNAME: {os.environ.get('JIRA_USERNAME')}")

# 2. Check values inside .env file directly
print(f"\n[.env FILE CONTENT]")
config = dotenv_values(env_path)
print(f"JIRA_URL: {config.get('JIRA_URL')}")
print(f"JIRA_USERNAME: {config.get('JIRA_USERNAME')}")

# 3. Simulate Pydantic loading
print(f"\n[Simulating Pydantic Precedence]")
if os.environ.get('JIRA_URL'):
    print("WARNING: os.environ has JIRA_URL, this will OVERRIDE .env!")
else:
    print("OK: os.environ does not have JIRA_URL, .env will be used.")
