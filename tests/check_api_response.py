import httpx
import asyncio

async def check():
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get("http://127.0.0.1:8635/api/v1/jira/projects")
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check())
