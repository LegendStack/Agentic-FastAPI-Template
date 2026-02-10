import asyncio
import logging
from src.app.agents.backlog.backlog_agent import BacklogAssistantAgent
from src.app.agents.backlog.schemas import UserStory, AcceptanceCriteria

# Setup logging to see what's happening
logging.basicConfig(level=logging.INFO)

async def test_refine_direct():
    agent = BacklogAssistantAgent()
    await agent.initialize()
    
    stories = [
        UserStory(
            id="STORY-001", 
            title="Setup GA Account", 
            description="Create a new GA4 property and tracking ID for the production environment.", 
            acceptance_criteria=[AcceptanceCriteria(description="Property created")]
        )
    ]
    
    print("🚀 Calling agent.chat directly...")
    try:
        result = await agent.chat(
            thread_id="test-thread-123",
            message="Add a new story for tracking button clicks.",
            initial_stories=stories
        )
        print("✅ SUCCESS")
        print(f"Stories: {len(result.get('stories', []))}")
    except Exception as e:
        print("❌ FAILED")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_refine_direct())
