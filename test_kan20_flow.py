import asyncio
import httpx
import json
import uuid
from datetime import datetime

BASE_URL = "http://127.0.0.1:8635/api/v1"

async def test_kan20_flow():
    thread_id = str(uuid.uuid4())
    print(f"\n[STEP] Testing KAN-20 Flow: Intent Detection -> Confirmation -> Decomposition -> Jira")
    print(f"Thread ID: {thread_id}")
    print("==========================================================================")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1. Initial Request: "Decompose story KAN-20 into tasks"
        print("\nStep 1: Requesting decomposition for KAN-20...")
        payload = {
            "message": "I wanted to decompose story KAN-20 into tasks.",
            "output_format": "markdown"
        }
        resp = await client.post(f"{BASE_URL}/backlog/chat/{thread_id}", json=payload)
        
        if resp.status_code != 200:
            print(f"FAILED Step 1: {resp.status_code}")
            print(resp.text)
            return

        data = resp.json()
        print(f"Agent Response:\n{data.get('summary')}")
        
        # 2. Confirmation: "Yes, proceed"
        print("\nStep 2: Confirming decomposition...")
        payload = {
            "message": "Yes, proceed",
            "output_format": "markdown"
        }
        resp = await client.post(f"{BASE_URL}/backlog/chat/{thread_id}", json=payload)
        
        if resp.status_code != 200:
            print(f"FAILED Step 2: {resp.status_code}")
            print(resp.text)
            return

        data = resp.json()
        stories = data.get("stories", [])
        print(f"Success. Generated {len(stories)} tasks.")
        for s in stories[:3]:
            print(f"   - {s.get('id')}: {s.get('title')}")

        # 3. Refinement: "Add a technical note about database migrations"
        print("\nStep 3: Adding technical note...")
        payload = {
            "message": "Add a technical note about database migrations to the initialization task.",
            "output_format": "markdown"
        }
        resp = await client.post(f"{BASE_URL}/backlog/chat/{thread_id}", json=payload)
        
        if resp.status_code != 200:
            print(f"FAILED Step 3: {resp.status_code}")
            print(resp.text)
            return

        data = resp.json()
        print(f"Refinement complete.")

        # 4. Export to Jira
        print(f"\nStep 4: Exporting to Jira...")
        export_resp = await client.post(
            f"{BASE_URL}/backlog/export/{thread_id}", 
            json={"project_key": "KAN"}, 
            timeout=60.0
        )
        
        if export_resp.status_code != 200:
            print(f"FAILED Export: {export_resp.status_code}")
            print(export_resp.text)
            return
            
        export_data = export_resp.json()
        print(f"Export status: {export_data.get('status')}")
        print(f"   Issues Created: {len(export_data.get('issues', []))}")

        print("\nKAN-20 Flow Test Complete.")

if __name__ == "__main__":
    asyncio.run(test_kan20_flow())
