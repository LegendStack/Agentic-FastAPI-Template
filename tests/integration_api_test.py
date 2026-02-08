import requests

BASE_URL = "http://127.0.0.1:8635/api/v1"


def test_full_flow():
    print("\n🚀 Starting Real-World API Integration Test...")

    # 1. Decompose Epic
    decompose_url = f"{BASE_URL}/backlog/decompose"
    epic_data = {
        "epic_description": "Implement a multi-tenant subscription system with billing and usage tracking for a SaaS platform. Use Stripe for payments.",
        "context": "We use FastAPI and PostgreSQL. The billing model is per-user for the base plan and usage-based for extra API calls.",
        "output_format": "json",
        "story_template": "standard",
        "enable_edge_cases": True,
        "enable_complexity_estimation": True,
    }

    print("\nStep 1: Decomposing Epic...")
    response = requests.post(decompose_url, json=epic_data)
    if response.status_code != 200:
        print(f"❌ Decomposition failed: {response.text}")
        return

    result = response.json()
    thread_id = result["thread_id"]
    stories = result["stories"]
    print(f"✅ Decomposition successful! Thread ID: {thread_id}")
    print(f"Generated {len(stories)} stories.")

    # 2. Refine to BDD
    chat_url = f"{BASE_URL}/backlog/chat/{thread_id}"
    refinement_data = {
        "message": "These look good. Now, please refine all these stories to use BDD (Given-When-Then) format for the acceptance criteria.",
        "output_format": "json",
    }

    print("\nStep 2: Refining to BDD format...")
    response = requests.post(chat_url, json=refinement_data)
    if response.status_code != 200:
        print(f"❌ Refinement failed: {response.text}")
        return

    result = response.json()
    bdd_stories = result["stories"]
    print("✅ Refinement successful!")

    # Verify BDD in first story
    first_story = bdd_stories[0]
    ac = first_story["acceptance_criteria"][0]
    print(f"Sample AC from story '{first_story['title']}':")
    print(f"  Description: {ac.get('description')}")
    if ac.get("given"):
        print(f"  Given: {ac.get('given')}")
        print(f"  When: {ac.get('when')}")
        print(f"  Then: {ac.get('then')}")
    else:
        print("⚠️ Warning: BDD fields missing in AC.")

    # 3. Export to JIRA
    export_url = f"{BASE_URL}/backlog/export/{thread_id}"
    # Using project_key from .env default if not provided, or explicit if known
    export_data = {"project_key": "KAN"}

    print("\nStep 3: Exporting to JIRA (Project: KAN)...")
    response = requests.post(export_url, json=export_data)
    if response.status_code != 200:
        print(f"❌ Export failed: {response.text}")
        return

    result = response.json()
    print(f"✅ Export status: {result['status']}")
    print(f"Message: {result['message']}")

    issues = result.get("issues", [])
    if issues:
        print("\nCreated JIRA Issues:")
        for issue in issues:
            print(f"- {issue.get('jira_key')}: {issue.get('url')}")
    else:
        print("⚠️ No JIRA issues returned.")

    print("\n🏁 Integration test complete!")


if __name__ == "__main__":
    test_full_flow()
