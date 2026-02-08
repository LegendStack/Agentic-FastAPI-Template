import requests

url = "http://localhost:8635/api/v1/backlog/decompose"
payload = {"epic_description": "Space Exploration Mission to Mars", "project_key": "KAN"}
headers = {"Content-Type": "application/json"}

try:
    print(f"Sending request to {url}...")
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    data = response.json()

    # Print summary of generated stories
    print("\nGenerated Stories:")
    for i, s in enumerate(data.get("stories", []), 1):
        print(f"{i}. {s['title']}")
        print(f"   Description: {s['description'][:100]}...")

    # Check for hallucinations
    hallucination = any(
        "billing" in s["title"].lower() or "billing" in s["description"].lower() for s in data.get("stories", [])
    )
    if hallucination:
        print("\n[WARNING] Hallucination detected! 'Billing' found in stories.")
    else:
        print("\n[SUCCESS] No 'Billing' hallucinations detected.")

except Exception as e:
    print(f"Error: {e}")
    if hasattr(e, "response") and e.response:
        print(f"Response: {e.response.text}")
