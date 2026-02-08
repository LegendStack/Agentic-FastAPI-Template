import time

import requests

url = "http://localhost:8635/api/v1/backlog/decompose"
payload = {
    "epic_description": "Skilled Trades Micro-Business (Plumbing, Electrical, HVAC fixes) Mobile/on-demand service",
    "project_key": "KAN",
}
headers = {"Content-Type": "application/json"}

# 1. Cold start (should miss cache)
print("--- Request 1: Cold Start ---")
t0 = time.time()
response = requests.post(url, json=payload, headers=headers)
t1 = time.time()
print(f"Status: {response.status_code}")
print(f"Time: {t1 - t0:.2f}s")
data = response.json()
stories = data.get("stories", [])
print(f"Stories: {[s.get('title')[:30] for s in stories[:3]]}")
if any("Mars" in str(s) or "Space" in str(s) for s in stories):
    print("[FAIL] Hallucination detected!")
else:
    print("[PASS] No Mars hallucinations.")

# 2. Warm start (should hit cache)
print("\n--- Request 2: Warm Start (Cache Check) ---")
t0 = time.time()
response = requests.post(url, json=payload, headers=headers)
t1 = time.time()
print(f"Status: {response.status_code}")
print(f"Time: {t1 - t0:.2f}s")
if t1 - t0 < 1.0:
    print("[SUCCESS] Cache hit confirmed!")
else:
    print("[WARNING] Cache miss - possibly distance threshold or logic issue.")

print("\nFull Story Titles (Warm):")
for s in response.json().get("stories", []):
    print(f"- {s.get('title')}")
