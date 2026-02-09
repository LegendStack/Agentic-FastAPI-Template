import asyncio
import httpx
import json
from datetime import datetime

BASE_URL = "http://127.0.0.1:8635/api/v1"

async def test_fast_track_flow():
    print("\n🚀 Testing Fast-Track Flow: Requirement → User Stories → Jira (Direct)")
    print("==========================================================")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1. Start Decomposition (Fast-Track)
        # We'll use a specific requirement and ask for direct stories
        payload = {
            "message": "Requirement: Add dark mode support to the mobile app. All screens should support theme switching, and high contrast mode should be maintained. Decompose this into user stories.",
            "output_format": "json"
        }
        
        print("\n▶️ Step 1: Sending Requirement for direct Story decomposition...")
        start = datetime.now()
        resp = await client.post(f"{BASE_URL}/backlog/chat", json=payload)
        
        if resp.status_code != 200:
            print(f"❌ Failed at Step 1: {resp.status_code}")
            print(resp.text)
            return

        data = resp.json()
        thread_id = data.get("thread_id")
        stories = data.get("stories", [])
        duration = (datetime.now() - start).total_seconds()
        
        print(f"✅ Success ({duration:.2f}s)")
        print(f"   Thread ID: {thread_id}")
        print(f"   Stories Generated: {len(stories)}")
        
        for i, s in enumerate(stories[:3]):
            print(f"   - Story {i+1}: {s.get('title')}")

        # 2. Verify Level
        target_issue_type = data.get("target_issue_type")
        print(f"\n▶️ Step 2: Verifying Target Issue Type...")
        if target_issue_type == "Story":
            print(f"✅ Target Issue Type is 'Story' as expected.")
        else:
            print(f"⚠️ Warning: Target Issue Type is '{target_issue_type}', expected 'Story'.")

        # 3. Export to Jira
        print(f"\n▶️ Step 3: Exporting to Jira...")
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
        status = export_data.get("status")
        message = export_data.get("message")
        issues = export_data.get("issues", [])
        
        print(f"✅ Export status: {status}")
        print(f"   Message: {message}")
        print(f"   Issues Created/Linked: {len(issues)}")
        
        if issues:
            print(f"   Created Issued Summary:")
            for issue in issues[:5]:
                print(f"   - {issue.get('jira_key')}: {issue.get('url')} ({issue.get('summary', 'No summary')})")

        print("\n🏁 Fast-Track Flow Test Complete.")

if __name__ == "__main__":
    asyncio.run(test_fast_track_flow())
