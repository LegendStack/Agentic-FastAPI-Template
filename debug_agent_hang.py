import asyncio
import logging
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Setup logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("test_agent")

from src.app.agents.backlog.backlog_agent import BacklogAssistantAgent
from src.app.agents.backlog.config import BacklogAgentConfig

async def test_hang():
    # Database setup (Postgres in WSL)
    db_url = "postgresql+asyncpg://postgres:1234@localhost:5432/postgres"
    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        logger.info("Initializing Agent...")
        from src.app.api.v1.backlog import get_agent
        agent = get_agent(session) 
        
        thread_id = "test-session-hang"
        message = "Create a feature for user profile management"
        
        logger.info(f"Calling agent.chat for thread {thread_id}...")
        try:
            # Set a timeout for the test
            result = await asyncio.wait_for(
                agent.chat(
                    thread_id=thread_id,
                    message=message,
                    output_format="json",
                    initial_stories=[]
                ),
                timeout=30.0
            )
            logger.info("Success!")
            logger.info(f"Summary: {result.get('summary')}")
            logger.info(f"Story Count: {result.get('story_count')}")
        except asyncio.TimeoutError:
            logger.error("Agent HANGED (Timeout reached)")
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_hang())
