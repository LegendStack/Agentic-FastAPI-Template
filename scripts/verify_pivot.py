import requests

# First, create a thread with Mars stories
url_decompose = "http://localhost:8635/api/v1/backlog/decompose"
payload_mars = {"epic_description": "Space Exploration Mission to Mars", "project_key": "KAN"}
print("--- Creating Mars Thread ---")
resp_mars = requests.post(url_decompose, json=payload_mars)
thread_id = resp_mars.json().get("thread_id")
print(f"Thread ID: {thread_id}")

# Now, send a Skilled Trades epic into the SAME thread via chat
url_chat = f"http://localhost:8635/api/v1/backlog/chat/{thread_id}"
payload_pivot = {
    "message": "Epic: Skilled Trades Micro-Business (Plumbing, Electrical, HVAC fixes) Mobile/on-demand service",
    "project_key": "KAN",
}
print("\n--- Sending Skilled Trades into Mars Thread (Pivot) ---")
resp_pivot = requests.post(url_chat, json=payload_pivot)
data = resp_pivot.json()

stories = data.get("stories", [])
print(f"Pivot Result Stories: {[s.get('title')[:30] for s in stories[:3]]}")

if any("Mars" in str(s) or "Space" in str(s) for s in stories):
    print("[FAIL] Pivot failed - Mars stories still present.")
else:
    print("[PASS] Pivot successful - New epic stories generated.")

# Check if is_first_message was effectively reset (it should have been handled internally in InputNode)
