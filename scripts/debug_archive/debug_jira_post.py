import asyncio
import os
import sys

import httpx

# Add src to path to import settings
sys.path.append(os.path.join(os.getcwd(), "src"))

from app.core.config import settings


async def main():
    print(f"JIRA URL: {settings.JIRA_URL}")
    auth = (settings.JIRA_USERNAME, settings.JIRA_API_TOKEN.get_secret_value())

    async with httpx.AsyncClient() as client:
        # Test 2: Search v3 with POST
        print("\n--- Test 2: Search v3 (POST) ---")
        try:
            payload = {
                "jql": "project = 'PDLC' AND issuetype = Epic",
                "maxResults": 1,
                "fields": ["summary", "description", "status"],
            }
            resp = await client.post(f"{settings.JIRA_URL}/rest/api/3/search", json=payload, auth=auth)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                print("Success! Found issues:")
                print(resp.json().get("issues", []))
            else:
                print(f"Response: {resp.text}")
        except Exception as e:
            print(f"Error: {e}")

        # Test 3: Search v3 JQL Endpoint (Literal)
        print("\n--- Test 3: Search v3 JQL (/rest/api/3/search/jql) ---")
        try:
            # Maybe it expects just the JQL string? Or JSON?
            # Usually POST search takes JSON.
            payload = {
                "jql": "project = 'PDLC' AND issuetype = Epic",
                "maxResults": 1,
                "fields": ["summary", "description", "status"],
            }
            resp = await client.post(f"{settings.JIRA_URL}/rest/api/3/search/jql", json=payload, auth=auth)
            print(f"Status: {resp.status_code}")
            if resp.status_code != 200:
                print(f"Response: {resp.text}")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
