
import requests
import json

BASE_URL = "http://127.0.0.1:8635/api/v1"

def test_marketing_epic():
    print("\n🚀 Testing AI Marketing Epic Decomposition...")
    
    decompose_url = f"{BASE_URL}/backlog/decompose"
    epic_data = {
        "epic_description": "AI Marketing & Content: Tools that automate content generation, hashtag research, and competitor analysis.",
        "context": "Minimalist tech stack for rapid prototyping.",
        "output_format": "json",
        "story_template": "standard"
    }
    
    print(f"\nStep 1: Decomposing Epic...")
    response = requests.post(decompose_url, json=epic_data)
    
    print(f"Status Code: {response.status_code}")
    if response.status_code != 200:
        print(f"❌ Decomposition failed: {response.text}")
        return
    
    result = response.json()
    thread_id = result.get("thread_id")
    stories = result.get("stories", [])
    summary = result.get("summary", "")
    
    print(f"✅ Decomposition successful! Thread ID: {thread_id}")
    print(f"Summary: {summary}")
    print(f"Number of stories: {len(stories)}")
    
    print("\nTop 3 Story Titles:")
    for s in stories[:3]:
        print(f"- {s.get('title')}")
        # Explicitly check for "Billing" or "Stripe" or "Subscription"
        if any(word in s.get('title', '').lower() for word in ['billing', 'stripe', 'subscription', 'payment']):
            print(f"‼️ HALLUCINATION DETECTED: Found relevant billing word in title: {s.get('title')}")

if __name__ == "__main__":
    test_marketing_epic()
