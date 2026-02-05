import asyncio
import uuid
import requests
import json

BASE_URL = "http://localhost:8635/api/v1"

async def test_conversational_export_flow():
    print("Starting Conversational JIRA Export Test")
    
    # 1. Create a new decomposition
    project_key = "JIRA-PROJ-99"
    epic_desc = "Building a conversational export feature for the backlog agent."
    
    print(f"\nPhase 1: Starting new chat for {project_key}...")
    response = requests.post(
        f"{BASE_URL}/backlog/decompose",
        json={"epic_description": epic_desc},
        params={"project_key": project_key}
    )
    
    data = response.json()
    thread_id = data["thread_id"]
    print(f"✅ Created Thread: {thread_id}")

    # 2. Refinement Turn
    print("\nPhase 2: Refinement turn...")
    requests.post(
        f"{BASE_URL}/backlog/chat/{thread_id}",
        json={"message": "Make sure to include a safety check for production environments."}
    )
    print("✅ Refinement sent")

    # 3. CONVERSATIONAL EXPORT
    print("\nPhase 3: Triggering conversational export via chat...")
    export_msg = "This looks perfect. Please export everything to JIRA now."
    chat_response = requests.post(
        f"{BASE_URL}/backlog/chat/{thread_id}",
        json={"message": export_msg}
    )
    
    if chat_response.status_code != 200:
        print(f"❌ Conversational export failed: {chat_response.text}")
        return

    result_data = chat_response.json()
    formatted = result_data.get("formatted_output", "")
    
    # Verify export markers in the formatted output
    if "JIRA Export: SUCCESS" in formatted:
        print("Success! Export confirmation found in chat response.")
        # Check for mock links
        if "https://jira.example.com/browse/MOCK-" in formatted:
            print("JIRA Mock links verified in output.")
        else:
            print("❌ JIRA links missing from output!")
    else:
        print("❌ Export confirmation NOT found in response!")
        print(f"DEBUG Output: {formatted}")

if __name__ == "__main__":
    asyncio.run(test_conversational_export_flow())
