import asyncio
import requests
import uuid

BASE_URL = "http://localhost:8635/api/v1"

async def test_conversational_save_flow():
    project_key = "PROJ-CHAT-TEST"
    
    # Phase 1: Decompose
    print("Starting Phase 1: Decompose")
    resp1 = requests.post(
        f"{BASE_URL}/backlog/decompose", 
        json={"epic_description": "Building a conversational save to JIRA feature."}, 
        params={"project_key": project_key}
    )
    if resp1.status_code != 200:
        print(f"DECOMPOSE_FAILED: {resp1.text}")
        return

    data = resp1.json()
    thread_id = data["thread_id"]
    print(f"✅ Decompose Successful. Thread: {thread_id}")

    # Phase 2: Save Intent
    print("\nStarting Phase 2: Conversational Save to JIRA")
    save_msg = "this looks perfect, please save to JIRA"
    chat_response = requests.post(
        f"{BASE_URL}/backlog/chat/{thread_id}", 
        json={"message": save_msg},
        params={"project_key": project_key} # Pass project key again just in case
    )
    
    if chat_response.status_code == 200:
        formatted = chat_response.json().get("formatted_output", "")
        if "JIRA SAVE: SUCCESS" in formatted:
            print("✅ VERIFICATION_SUCCESS")
        else:
            print("❌ VERIFICATION_FAILURE: Confirmation marker 'JIRA SAVE: SUCCESS' missing from response")
            # print(f"DEBUG Output: {formatted}")
    else:
        print(f"❌ VERIFICATION_FAILURE: Chat Status {chat_response.status_code}, {chat_response.text}")

if __name__ == "__main__":
    asyncio.run(test_conversational_save_flow())
