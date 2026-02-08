import asyncio

import httpx


async def test_real_decompose():
    url = "http://127.0.0.1:8635/api/v1/backlog/decompose"

    payload = {
        "epic_description": "Add a dark mode toggle to the dashboard UI. The toggle should persist the user choice in local storage and update the theme-provider context.",
        "context": "React, Tailwind CSS, Framer Motion",
        "output_format": "json",
        "story_template": "bdd",
        "enable_edge_cases": True,
        "enable_complexity_estimation": True,
    }

    print(f"Sending request to: {url}")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=30.0)
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print(f"Thread ID: {result.get('thread_id')}")
                print(f"Story Count: {result.get('story_count')}")
                print(f"Summary: {result.get('summary')}")

                stories = result.get("stories", [])
                print("\nGenerated Stories:")
                for i, story in enumerate(stories[:3]):
                    print(f"{i + 1}. {story.get('title')}")

                # Check if it's still hardcoded
                if any("Initial Setup for" in s.get("title", "") for s in stories):
                    print("\n❌ FAILED: Still seeing hardcoded mock stories!")
                else:
                    print("\n✅ SUCCESS: Real LLM generated stories detected!")
            else:
                print(f"❌ Error: {response.text}")

        except Exception as e:
            print(f"💥 Request Failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_real_decompose())
