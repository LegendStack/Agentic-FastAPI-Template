import asyncio
import httpx
import json
from datetime import datetime

BASE_URL = "http://127.0.0.1:8635/api/v1"

async def test_refinement_flow():
    print("\n🚀 Testing Refinement Flow: Multi-turn decomposition → Jira")
    print("==========================================================")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1. Initial Decomposition
        payload = {
            "message": "Epic: Password Management. Users should be able to reset passwords and manage security questions. Decompose this into a few stories.",
            "output_format": "json"
        }
        
        print("\n▶️ Step 1: Initial decomposition...")
        resp = await client.post(f"{BASE_URL}/backlog/chat", json=payload)
        
        if resp.status_code != 200:
            print(f"❌ Failed at Step 1: {resp.status_code}")
            return

        data = resp.json()
        thread_id = data.get("thread_id")
        orig_count = len(data.get("stories", []))
        
        print(f"✅ Success. Generated {orig_count} stories. Thread: {thread_id}")

        # 2. Refinement Turn
        print(f"\n▶️ Step 2: Refining with feedback (Adding BDD scenarios)...")
        refine_payload = {
            "message": "These look good. Please update all stories to use BDD format (Given/When/Then) and add edge cases for password strength."
        }
        
        refine_resp = await client.post(f"{BASE_URL}/backlog/chat/{thread_id}", json=refine_payload)
        
        if refine_resp.status_code != 200:
            print(f"❌ Failed at Step 2: {refine_resp.status_code}")
            print(refine_resp.text)
            return
            
        refine_data = refine_resp.json()
        refined_stories = refine_data.get("stories", [])
        
        print(f"✅ Refinement Success. Now have {len(refined_stories)} stories.")
        if refined_stories:
            first_ac = refined_stories[0].get("acceptance_criteria", [])
            if first_ac and "given" in first_ac[0].get("description", "").lower():
                print(f"✅ BDD format detected in refined ACs.")
            else:
                print(f"⚠️ Warning: BDD format NOT clearly detected in ACs.")

        # 3. Export to Jira
        print(f"\n▶️ Step 3: Exporting refined stories to Jira...")
        export_resp = await client.post(
            f"{BASE_URL}/backlog/export/{thread_id}", 
            json={"project_key": "PDLC"}, 
            timeout=60.0
        )
        
        if export_resp.status_code != 200:
            print(f"❌ Export Failed: {export_resp.status_code}")
            return
            
        export_data = export_resp.json()
        print(f"✅ Export status: {export_data.get('status')}")
        print(f"   Issues Created/Linked: {len(export_data.get('issues', []))}")

        print("\n🏁 Refinement Flow Test Complete.")

if __name__ == "__main__":
    asyncio.run(test_refinement_flow())
