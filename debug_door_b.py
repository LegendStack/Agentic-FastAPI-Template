import asyncio
import httpx
import json

BASE_URL = "http://127.0.0.1:8635/api/v1"

async def debug_door_b():
    payload = {
        "stories": [
            {
                "id": "STORY-001", 
                "title": "Setup GA Account", 
                "description": "Create a new GA4 property and tracking ID for the production environment.", 
                "acceptance_criteria": [{"description": "Property created"}]
            }
        ],
        "message": "Add a new story for tracking button clicks.",
        "output_format": "json"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("Sending Door B request...")
        try:
            resp = await client.post(f"{BASE_URL}/backlog/refine", json=payload)
            print(f"Status: {resp.status_code}")
            try:
                print("Response JSON:")
                print(json.dumps(resp.json(), indent=2))
            except:
                print("Response Text (Not JSON):")
                print(resp.text)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_door_b())
