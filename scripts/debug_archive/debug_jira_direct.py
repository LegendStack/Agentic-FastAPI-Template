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
        # Test 1: Simple Search on v2
        print("\n--- Test 1: Search v2 (Simple) ---")
        try:
            resp = await client.get(
                f"{settings.JIRA_URL}/rest/api/2/search",
                params={"jql": "order by created DESC", "maxResults": 1},
                auth=auth,
            )
            print(f"Status: {resp.status_code}")
            if resp.status_code != 200:
                print(f"Response: {resp.text}")
        except Exception as e:
            print(f"Error: {e}")

        # Test 2: Project Search on v2 (The failing query)
        print("\n--- Test 2: Search v2 (Project PDLC) ---")
        try:
            resp = await client.get(
                f"{settings.JIRA_URL}/rest/api/2/search",
                params={"jql": "project = 'PDLC' AND issuetype = Epic", "maxResults": 1},
                auth=auth,
            )
            print(f"Status: {resp.status_code}")
            if resp.status_code != 200:
                print(f"Response: {resp.text}")
        except Exception as e:
            print(f"Error: {e}")

        # Test 3: Search v3 (Fallback)
        print("\n--- Test 3: Search v3 ---")
        try:
            resp = await client.get(
                f"{settings.JIRA_URL}/rest/api/3/search",
                params={"jql": "project = 'PDLC' AND issuetype = Epic", "maxResults": 1},
                auth=auth,
            )
            print(f"Status: {resp.status_code}")
            if resp.status_code != 200:
                print(f"Response: {resp.text}")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
