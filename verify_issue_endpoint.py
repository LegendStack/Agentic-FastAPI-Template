import httpx
import asyncio
import os
import sys

sys.path.append(os.path.join(os.getcwd(), "src"))
from app.core.config import settings

async def main():
    print(f"JIRA URL: {settings.JIRA_URL}")
    auth = (settings.JIRA_USERNAME, settings.JIRA_API_TOKEN.get_secret_value())
    
    async with httpx.AsyncClient() as client:
        # 1. Find a valid issue key
        print("\n--- Finding an issue ---")
        try:
            # use new search endpoint
            # Try searching for ANY issue in a specific project or just created recently if project is unknown.
            # But the error 'search restriction' suggests we need a project or similar.
            # Let's try Project = PDLC first, or just "created >= -30d"
            # Actually, let's try to list projects first to get a key? No, just try a safe JQL.
            # "project IS NOT EMPTY" might work?
            # Or better, "issuekey IS NOT EMPTY"
            
            # Let's try a specific project we saw earlier: KAN or PDLC (PDLC was 410, so maybe it exists but endpoint was wrong?)
            # Let's try KAN first as it was listed.
            
            jql = "project = KAN ORDER BY created DESC"
            print(f"Searching with JQL: {jql}")
            
            resp = await client.post(
                f"{settings.JIRA_URL}/rest/api/3/search/jql",
                json={"jql": jql, "maxResults": 1, "fields": ["key"]},
                auth=auth
            )
            if resp.status_code == 200:
                issues = resp.json().get('issues', [])
                if issues:
                    key = issues[0]['key']
                    print(f"Found issue: {key}")
                    
                    # 2. Test our new local endpoint
                    print(f"\n--- Testing GET /api/v1/jira/issues/{key} ---")
                    local_resp = await client.get(f"http://localhost:8635/api/v1/jira/issues/{key}", timeout=20.0)
                    print(f"Status: {local_resp.status_code}")
                    if local_resp.status_code == 200:
                        data = local_resp.json()
                        print("Success!")
                        print(f"Key: {data.get('key')}")
                        print(f"Summary: {data.get('summary')}")
                        print(f"Description (First 100 chars): {str(data.get('description'))[:100]}")
                    else:
                        print(f"Failure: {local_resp.text}")
                else:
                    print("No issues found in Jira to test with.")
            else:
                print(f"Failed to search Jira: {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
