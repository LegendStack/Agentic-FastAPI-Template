import httpx
import asyncio
import os
import sys

sys.path.append(os.path.join(os.getcwd(), "src"))
from app.core.config import settings

async def main():
    auth = (settings.JIRA_USERNAME, settings.JIRA_API_TOKEN.get_secret_value())
    url = f"{settings.JIRA_URL}/rest/api/3/search/jql"
    print(f"Testing {url} ...")
    
    async with httpx.AsyncClient() as client:
        try:
            payload = {
                "jql": "project = 'PDLC' AND issuetype = Epic",
                "maxResults": 1,
                "fields": ["summary"]
            }
            resp = await client.post(url, json=payload, auth=auth)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                print("SUCCESS: Found endpoint")
                print(resp.json())
            else:
                print(f"FAILURE: {resp.status_code}")
                # print(resp.text)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
