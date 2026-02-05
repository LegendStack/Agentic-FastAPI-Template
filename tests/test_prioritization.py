import asyncio
import logging
from src.app.agents.backlog import BacklogAssistantAgent, BacklogAgentConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_prioritization():
    print("\n🚀 Testing Value Order Prioritization...")
    
    # Use mocks to isolate the prioritization logic with deterministic scores
    config = BacklogAgentConfig(USE_MOCKS=True)
    agent = BacklogAssistantAgent(config=config)
    
    # Epic for decomposition
    epic = "Test Epic for Prioritization"
    
    print("Step 1: Running Mock Decomposition...")
    # The mock returns STORY-001 (ROI 1.0), STORY-002 (ROI 5.0), STORY-003 (ROI 2.0)
    result = await agent.decompose(epic)
    
    stories = result.get("stories", [])
    print(f"✅ Generated {len(stories)} stories.")
    
    print("\nVerifying Order (Expected: ROI Descending):")
    for i, story in enumerate(stories):
        roi = story.get('business_value_score') / story.get('effort_score')
        print(f"{i+1}. {story.get('id')}: {story.get('title')}")
        print(f"   Value: {story.get('business_value_score')}, Effort: {story.get('effort_score')}, ROI: {roi:.2f}")

    # Assert correct order
    expected_order = ["STORY-002", "STORY-003", "STORY-001"]
    actual_order = [s.get("id") for s in stories]
    
    if actual_order == expected_order:
        print("\n✨ SUCCESS: Stories are prioritized correctly by ROI!")
    else:
        print(f"\n❌ FAILURE: Order mismatch. Expected: {expected_order}, Actual: {actual_order}")
        
if __name__ == "__main__":
    asyncio.run(test_prioritization())
