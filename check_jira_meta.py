import asyncio

import httpx

from src.app.core.config import settings


async def check_meta():
    base_url = settings.JIRA_URL
    auth = (settings.JIRA_USERNAME, settings.JIRA_API_TOKEN.get_secret_value())

    # Check project KAN and issue type Epic
    url = f"{base_url}/rest/api/2/issue/createmeta"
    params = {"projectKeys": "KAN", "issuetypeNames": "Epic", "expand": "projects.issuetypes.fields"}

    async with httpx.AsyncClient() as client:
        print(f"Checking metadata for {base_url}...")
        response = await client.get(url, params=params, auth=auth)
        if response.status_code != 200:
            print(f"Failed with {response.status_code}: {response.text}")
            # Try rest/api/3
            url = f"{base_url}/rest/api/3/issue/createmeta"
            response = await client.get(url, params=params, auth=auth)
            print(f"v3 retry status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            projects = data.get("projects", [])
            if not projects:
                print("No project 'KAN' found or accessible.")
                return

            p = projects[0]
            issuetypes = p.get("issuetypes", [])
            if not issuetypes:
                print("No issue type 'Epic' found for project 'KAN'.")
                return

            fields = issuetypes[0].get("fields", {})
            print("\nFields for Epic:")
            for field_key, field_info in fields.items():
                if field_info.get("required"):
                    print(f"- {field_key}: {field_info.get('name')} (REQUIRED)")
                else:
                    if "Epic Name" in field_info.get("name", ""):
                        print(f"- {field_key}: {field_info.get('name')} (Optional?)")
        else:
            print(f"Final failure: {response.text}")


if __name__ == "__main__":
    asyncio.run(check_meta())
