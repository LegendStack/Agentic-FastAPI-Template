import asyncio
import httpx
import sys
import json
from datetime import datetime

BASE_URL = "http://127.0.0.1:8635/api/v1"

class DecompositionTester:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=120.0)
        self.results = []

    async def run_scenario(self, name, endpoint, payload, method="POST"):
        print(f"\n▶️ Running Scenario: {name}...")
        start = datetime.now()
        try:
            if method == "POST":
                resp = await self.client.post(f"{BASE_URL}{endpoint}", json=payload)
            else:
                resp = await self.client.get(f"{BASE_URL}{endpoint}")
            
            duration = (datetime.now() - start).total_seconds()
            
            status = "✅ PASS" if resp.status_code in [200, 201] else "❌ FAIL"
            print(f"   Status: {resp.status_code} ({duration:.2f}s)")
            
            data = resp.json()
            
            # Basic validations
            if resp.status_code == 200:
                if "stories" in data:
                    print(f"   Stories generated: {len(data['stories'])}")
                if "thread_id" in data:
                    print(f"   Thread ID: {data['thread_id']}")
            
            self.results.append({
                "scenario": name,
                "status": status,
                "code": resp.status_code,
                "duration": duration,
                "thread_id": data.get("thread_id"),
                "story_count": len(data.get("stories", [])),
                "error": data.get("error") if resp.status_code != 200 else None
            })
            return data
        except Exception as e:
            print(f"   💥 Error: {str(e)}")
            import traceback
            traceback.print_exc()
            self.results.append({
                "scenario": name,
                "status": "💥 ERROR",
                "error": str(e)
            })
            return None

    async def verify_everything(self):
        print("🚀 Starting Comprehensive Decomposition Verification")
        print("==================================================")

        # 1. Standard Decomposition
        await self.run_scenario(
            "Standard Decomposition",
            "/backlog/decompose",
            {"epic_description": "Implement a user profile page with editable fields for name, email, and bio.", "output_format": "json"}
        )

        # 2. Context-Aware Decomposition
        await self.run_scenario(
            "Context-Aware Decomposition",
            "/backlog/decompose",
            {
                "epic_description": "Add dark mode support.",
                "context": "We use Tailwind CSS and Headless UI. Prefer CSS variables for themes.",
                "output_format": "json"
            }
        )

        # 3. Format Variants (BDD)
        await self.run_scenario(
            "BDD Format Template",
            "/backlog/decompose",
            {
                "epic_description": "Password reset flow.",
                "story_template": "bdd",
                "output_format": "json"
            }
        )

        # 4. Feature Toggles (Disabled Edge Cases/Estimates)
        await self.run_scenario(
            "Toggle Off (No Edge Cases/Estimates)",
            "/backlog/decompose",
            {
                "epic_description": "Integration with Google Analytics.",
                "enable_edge_cases": False,
                "enable_complexity_estimation": False,
                "output_format": "json"
            }
        )

        # 5. Door B - Refinement of Existing Stories
        door_b_payload = {
            "stories": [
                {
                    "id": "STORY-001", 
                    "title": "Setup GA Account", 
                    "description": "Create a new GA4 property and tracking ID for the production environment.", 
                    "acceptance_criteria": [{"description": "Property created"}]
                },
                {
                    "id": "STORY-002", 
                    "title": "Install SDK", 
                    "description": "Add the gtag.js snippet to the main layout file of the application.", 
                    "acceptance_criteria": [{"description": "SDK loaded"}]
                }
            ],
            "message": "Add a new story for tracking button clicks specifically.",
            "output_format": "json"
        }
        await self.run_scenario("Door B Refinement (Direct Injection)", "/backlog/refine", door_b_payload)

        # 6. Chat Continuity (Multi-turn)
        # First, decompose to get a thread
        initial = await self.run_scenario(
            "Chat Thread Creation",
            "/backlog/decompose",
            {"epic_description": "Email notification system for task updates.", "output_format": "json"}
        )
        
        if initial and initial.get("thread_id"):
            thread_id = initial["thread_id"]
            await self.run_scenario(
                "Chat Refinement (Turn 2)",
                f"/backlog/chat/{thread_id}",
                {"message": "Make sure to mention that emails should be HTML formatted."}
            )

        print("\n📊 FINAL REPORT")
        print("==================================================")
        for r in self.results:
            print(f"{r['status']} | {r['scenario']} ({r.get('duration', 0):.2f}s) | Count: {r.get('story_count', 'N/A')}")
        
        with open("verification_report.json", "w") as f:
            json.dump(self.results, f, indent=2)
        print("\n✅ Report saved to verification_report.json")

    async def close(self):
        await self.client.aclose()

if __name__ == "__main__":
    tester = DecompositionTester()
    try:
        asyncio.run(tester.verify_everything())
    finally:
        asyncio.run(tester.close())
