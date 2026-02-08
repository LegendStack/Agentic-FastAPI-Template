import requests

url_decompose = "http://localhost:8635/api/v1/backlog/decompose"
url_export_base = "http://localhost:8635/api/v1/backlog/export"

# 1. Decompose first
print("--- Step 1: Decomposing ---")
payload_decomp = {"epic_description": "Sample Integration Epic", "project_key": "KAN"}
resp_decomp = requests.post(url_decompose, json=payload_decomp)
thread_id = resp_decomp.json().get("thread_id")
print(f"Thread ID: {thread_id}")

# 2. Export to Jira
print("\n--- Step 2: Exporting to Jira ---")
resp_export = requests.post(f"{url_export_base}/{thread_id}")
data = resp_export.json()

print(f"Status: {data.get('status')}")
print(f"Has Stories: {'stories' in data}")
if data.get("stories"):
    print(f"Story Count: {len(data['stories'])}")
    print(f"First Story Jira Key: {data['stories'][0].get('jira_key')}")
    if data["stories"][0].get("jira_key"):
        print("[PASS] Stories have Jira keys.")
    else:
        print("[FAIL] Stories missing Jira keys in response.")
else:
    print("[FAIL] Response missing 'stories' field.")

# 3. Check messages to see if confirmation was added
print("\n--- Step 3: Verifying Conversation Persistence ---")
resp_stories = requests.get(f"http://localhost:8635/api/v1/backlog/stories/{thread_id}")
messages = resp_stories.json().get("messages", [])
assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
if assistant_msgs:
    last_msg = assistant_msgs[-1].get("content", "")
    print(f"Last Assistant Message Preview: {last_msg[:100]}...")
    if "JIRA issues saved successfully" in last_msg:
        print("[PASS] Confirmation message found in history.")
        if "Epic" in last_msg:
            print("[PASS] Epic mentioned in message.")
        else:
            print("[FAIL] Epic missing from message.")
    else:
        print("[FAIL] Confirmation message not found.")
else:
    print("[FAIL] No assistant messages found.")
