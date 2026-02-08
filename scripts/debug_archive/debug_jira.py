import asyncio

import httpx


async def main():
    async with httpx.AsyncClient() as client:
        try:
            print("Fetching Projects...")
            resp = await client.get("http://localhost:8635/api/v1/jira/projects", timeout=20.0)
            print(f"Projects Status: {resp.status_code}")
            projects = resp.json()
            for p in projects:
                print(f"Project: {p['name']} (Key: {p['key']})")

            if projects:
                first_key = projects[0]["key"]
                print(f"\nFetching Epics for {first_key}...")
                resp = await client.get(f"http://localhost:8635/api/v1/jira/projects/{first_key}/epics", timeout=20.0)
                print(f"Epics Status: {resp.status_code}")
                # print(resp.text[:200]) # Print first 200 chars of response

            print("\nFetching Epics for PDLC (Expecting Failure)...")
            resp = await client.get("http://localhost:8635/api/v1/jira/projects/PDLC/epics", timeout=20.0)
            print(f"PDLC Epics Status: {resp.status_code}")
            print(resp.text[:200])

        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
