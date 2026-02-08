import time

import requests

BASE_URL = "http://127.0.0.1:8635/api/v1"


def verify_token_visibility():
    """Verify that token usage is returned by the API."""

    print("🚀 Starting Token Visibility Verification (API Mode)...")

    # 1. Decompose Epic
    decompose_url = f"{BASE_URL}/backlog/decompose"
    epic_data = {
        "epic_description": "As a user, I want to see token usage in my chat window so I know the cost.",
        "output_format": "json",
    }

    print("\n1. Decomposing epic...")
    try:
        response = requests.post(decompose_url, json=epic_data)
        if response.status_code not in [200, 201]:
            print(f"❌ Decomposition failed: {response.status_code} - {response.text}")
            return None

        result = response.json()
        thread_id = result["thread_id"]
        print(f"✅ Decomposition complete. Thread ID: {thread_id}")

        # 2. Verify usage in immediate response
        usage = result.get("usage")
        if usage:
            print(f"✅ Usage metadata found in immediate response: {usage}")
            if usage.get("input_tokens", 0) > 0 or usage.get("output_tokens", 0) > 0:
                print("   - Token counts look valid (non-zero).")
            else:
                print("   ⚠️ Token counts are zero (simulated/mock response).")
        else:
            print("❌ 'usage' field MISSING in API response!")

        # 3. Verify usage in history (get_stories)
        print("\n2. Verifying history persistence...")
        history_url = f"{BASE_URL}/backlog/stories/{thread_id}"

        # Give DB a moment to settle if needed, though API await should handle it
        time.sleep(1)

        response = requests.get(history_url)
        if response.status_code != 200:
            print(f"❌ Failed to fetch history: {response.text}")
            return

        history_result = response.json()
        messages = history_result.get("messages", [])
        print(f"   Found {len(messages)} messages in history.")

        token_found = False
        for msg in messages:
            # Check for token fields
            in_tokens = msg.get("input_tokens", 0)
            out_tokens = msg.get("output_tokens", 0)

            print(f"   - Role: {msg.get('role')}, In: {in_tokens}, Out: {out_tokens}")

            if msg.get("role") == "assistant" and (in_tokens > 0 or out_tokens > 0):
                token_found = True

        if token_found:
            print("✅ Found assistant message with persisted token counts in history API.")
        else:
            print("⚠️ No tokens found in history messages (persistence might be lagging or using state fallback).")

    except Exception as e:
        print(f"❌ Integration test error: {e}")


if __name__ == "__main__":
    verify_token_visibility()
