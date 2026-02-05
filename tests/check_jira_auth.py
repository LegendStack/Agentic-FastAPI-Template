import asyncio
import httpx
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
from app.core.config import settings

async def check_jira():
    print(f"Testing JIRA URL: {settings.JIRA_URL}")
    print(f"Username: {settings.JIRA_USERNAME}")
    token = settings.JIRA_API_TOKEN.get_secret_value() if settings.JIRA_API_TOKEN else "None"
    print(f"Token (first 10): {token[:10]}...")
    
    headers = {"Accept": "application/json"}
    
    async def print_debug(response):
        print(f"Status: {response.status_code}")
        print("--- Headers ---")
        for k, v in response.headers.items():
            if k.lower().startswith("x-seraph") or k.lower() in ["www-authenticate", "x-ausername", "content-type"]:
                print(f"{k}: {v}")
        
        if "html" in response.headers.get("content-type", ""):
            import re
            title_match = re.search(r'<title>(.*?)</title>', response.text, re.IGNORECASE)
            if title_match:
                print(f"HTML Title: {title_match.group(1)}")
            else:
                 print("HTML Body (no title found):", response.text[:200])
        else:
             try:
                import json
                print(json.dumps(response.json(), indent=2)[:500])
             except:
                print(f"Body: {response.text[:500]}")

    # Test 1a: Basic Auth (Standard for Cloud) - Configured Email
    print(f"\n--- Test 1a: /myself for {settings.JIRA_USERNAME} ---")
    auth_basic = (settings.JIRA_USERNAME, token)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{settings.JIRA_URL}/rest/api/2/myself", 
                auth=auth_basic,
                headers=headers,
                timeout=10.0
            )
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                print(f"Logged in as: {data.get('displayName')} ({data.get('emailAddress')})")
                print(f"Account ID: {data.get('accountId')}")
            else:
                await print_debug(resp)
        except Exception as e:
            print(f"Error: {e}")

    # Test 1b: Basic Auth - Alternative Email (from ghost env)
    alt_email = "mano.chowdary.t@gmail.com"
    print(f"\n--- Test 1b: /myself with Alternative Email {alt_email} ---")
    auth_alt = (alt_email, token)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{settings.JIRA_URL}/rest/api/2/myself", 
                auth=auth_alt,
                headers=headers,
                timeout=10.0
            )
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                print(f"Logged in as: {data.get('displayName')} ({data.get('emailAddress')})")
                print(f"✅ SUCCESS! This email works with the token.")
            else:
                await print_debug(resp)
        except Exception as e:
            print(f"Error: {e}")

    # Test 2: Project Endpoint v2 (Raw)
    print("\n--- Test 2: Project Endpoint (/rest/api/2/project) ---")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{settings.JIRA_URL}/rest/api/2/project", 
                auth=auth_basic,
                headers=headers,
                timeout=10.0
            )
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                print(f"Raw Body: {resp.text}")
            else:
                await print_debug(resp)
        except Exception as e:
            print(f"Error: {e}")

    # Test 2: Server Existence Check (Unauthenticated)
    print("\n--- Test 2: Server Reachability (No Auth) ---")
    async with httpx.AsyncClient() as client:
        try:
            # Checking a public-ish endpoint or just root to see if host exists
            resp = await client.get(
                f"{settings.JIRA_URL}/status", 
                timeout=10.0
            )
            print(f"Status (should be 200/401/403): {resp.status_code}")
        except Exception as e:
            print(f"Error reaching server root: {e}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(check_jira())
