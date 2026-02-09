import asyncio
import httpx
import json
from datetime import datetime

BASE_URL = "http://127.0.0.1:8635/api/v1"

async def test_door_b_flow():
    print("\n🚀 Testing Door B Flow: External Story Injection → Refinement → Jira")
    print("==========================================================")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1. External Injection via /refine
        # We start with existing stories and no thread_id
        payload = {
            "stories": [
                {
                    "id": "INJECTED-001", 
                    "title": "Legacy Database Migration", 
                    "description": "Migrate data from the legacy Oracle DB to the new Postgres instance.", 
                    "acceptance_criteria": [{"description": "Data integrity verified"}]
                }
            ],
            "message": "Refine this story by adding specific mapping tasks and a backup step.",
            "output_format": "json"
        }
        
        print("\n▶️ Step 1: Injecting external stories for refinement...")
        resp = await client.post(f"{BASE_URL}/backlog/refine", json=payload)
        
        if resp.status_code != 200:
            print(f"❌ Failed at Step 1: {resp.status_code}")
            print(resp.text)
            return

        data = resp.json()
        thread_id = data.get("thread_id")
        stories = data.get("stories", [])
        
        print(f"✅ Success. Created thread: {thread_id}")
        print(f"   Now have {len(stories)} stories/tasks after refinement.")
        
        for i, s in enumerate(stories[:3]):
            print(f"   - Refined {i+1}: {s.get('title')}")

        # 2. Export to Jira
        print(f"\n▶️ Step 2: Exporting injected/refined stories to Jira...")
        # Note: DOOR B stories should be exportable just like any others
        export_resp = await client.post(
            f"{BASE_URL}/backlog/export/{thread_id}", 
            json={"project_key": "PDLC"}, 
            timeout=60.0
        )
        
        if export_resp.status_code != 200:
            print(f"❌ Export Failed: {export_resp.status_code}")
            print(export_resp.text)
            return
            
        export_data = export_resp.json()
        print(f"✅ Export status: {export_data.get('status')}")
        print(f"   Issues Created/Linked: {len(export_data.get('issues', []))}")

        print("\n🏁 Door B Flow Test Complete.")

if __name__ == "__main__":
    asyncio.run(test_door_b_flow())
