
import asyncio
import httpx
import sys

BASE_URL = "http://localhost:8635/api/v1/agents/conversations"

async def test_delete_conversation():
    async with httpx.AsyncClient() as client:
        # 1. Create a new conversation
        print("Creating new conversation...")
        response = await client.post(BASE_URL, json={"title": "Delete Test", "agent_name": "backlog_assistant"})
        if response.status_code != 200:
            print(f"Failed to create conversation: {response.text}")
            sys.exit(1)
        
        data = response.json()
        thread_id = data["thread_id"]
        print(f"Created conversation: {thread_id}")

        # 2. Verify it exists in the list
        print("Verifying existence in list...")
        response = await client.get(BASE_URL, params={"agent_name": "backlog_assistant"})
        conversations = response.json().get("conversations", [])
        found = any(c["thread_id"] == thread_id for c in conversations)
        if not found:
            print("Conversation not found in list immediately after creation!")
            sys.exit(1)
        print("Conversation found in list.")

        # 3. Delete the conversation
        print(f"Deleting conversation {thread_id}...")
        response = await client.delete(f"{BASE_URL}/{thread_id}")
        if response.status_code != 200:
            print(f"Failed to delete conversation: {response.status_code} - {response.text}")
            sys.exit(1)
        print("Delete request successful.")

        # 4. Verify it is GONE from the list
        print("Verifying removal from list...")
        response = await client.get(BASE_URL, params={"agent_name": "backlog_assistant"})
        conversations = response.json().get("conversations", [])
        found = any(c["thread_id"] == thread_id for c in conversations)
        if found:
            print("ERROR: Conversation STILL FOUND in list after deletion!")
            sys.exit(1)
        else:
            print("SUCCESS: Conversation successfully removed from list.")

if __name__ == "__main__":
    try:
        asyncio.run(test_delete_conversation())
    except Exception as e:
        print(f"An error occurred: {e}")
