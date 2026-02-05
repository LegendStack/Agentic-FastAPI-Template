import asyncio
import httpx
import sys

# Constants
BASE_URL = "http://127.0.0.1:8635/api/v1"
PROJECT_KEY = "KAN"  # Known valid project

async def run_test_flow():
    print(f"Starting Full Backlog Flow Test against {BASE_URL}")

    async with httpx.AsyncClient(timeout=60.0) as client:
        # ---------------------------------------------------------
        # Step 1: Decompose Epic
        # ---------------------------------------------------------
        print("\nStep 1: Decomposing Epic...")
        decompose_payload = {
            "epic_description": "Create a 'Contact Us' form with name, email, subject, and message fields. It should save to the database and send an email notification.",
            "context": "React, FastAPI, PostgreSQL",
            "output_format": "json",
            "story_template": "bdd",
            "enable_edge_cases": True,
            "enable_complexity_estimation": True
        }
        
        resp = await client.post(f"{BASE_URL}/backlog/decompose", json=decompose_payload)
        
        if resp.status_code != 200:
            print(f"Decompose Failed: {resp.status_code} - {resp.text}")
            return
        
        data = resp.json()
        thread_id = data["thread_id"]
        stories = data["stories"]
        print(f"Decomposition Successful!")
        print(f"   Thread ID: {thread_id}")
        print(f"   Story Count: {len(stories)}")
        for s in stories[:2]:
            print(f"   - {s.get('title')}")

        # ---------------------------------------------------------
        # Step 2: Refine Stories (Chat)
        # ---------------------------------------------------------
        print("\nStep 2: Refining Stories (Chat)...")
        chat_payload = {
            "message": "Add a validation rule: Email must be from a corporate domain."
        }
        
        resp = await client.post(f"{BASE_URL}/backlog/chat/{thread_id}", json=chat_payload)
        
        if resp.status_code != 200:
            print(f"Chat Refinement Failed: {resp.status_code} - {resp.text}")
            return

        data = resp.json()
        stories = data["stories"]
        print(f"Refinement Successful!")
        print(f"   Story Count: {len(stories)}")
        # Check if the feedback was incorporated (simple heuristic check)
        validation_found = any("corporate" in str(s).lower() for s in stories)
        if validation_found:
             print("   Validation rule found in stories.")
        else:
             print("   Validation rule NOT explicitly found (AI might have missed it, but flow worked).")

        # ---------------------------------------------------------
        # Step 3: Export to JIRA
        # ---------------------------------------------------------
        print("\nStep 3: Exporting to JIRA...")
        export_payload = {
            "project_key": PROJECT_KEY
        }
        
        # NOTE: Using the direct export endpoint for definitive verification
        resp = await client.post(f"{BASE_URL}/backlog/export/{thread_id}", json=export_payload)
        
        if resp.status_code != 200:
            print(f"Export Failed: {resp.status_code} - {resp.text}")
            return

        data = resp.json()
        status = data.get("status")
        issues = data.get("issues", [])
        
        if status == "success" and issues:
            print(f"Export Successful!")
            print(f"   Created {len(issues)} JIRA Issues:")
            for issue in issues:
                print(f"   - {issue.get('key')}: {issue.get('self')}")
        else:
            print(f"Export Reported Failure/Empty:")
            print(f"   Status: {status}")
            print(f"   Message: {data.get('message')}")
            print(f"   Errors: {data.get('errors')}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_test_flow())
