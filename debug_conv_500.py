
import asyncio
import os
import sys

# Add current directory to path so 'src' is importable
sys.path.append(os.path.abspath('.'))

from src.app.core.db.database import async_get_db
from src.app.agents.conversations import ConversationService

async def test():
    try:
        print("Starting test with days_limit=30...")
        async for db in async_get_db():
            service = ConversationService(db)
            print("Calling list_conversations...")
            convs = await asyncio.wait_for(
                service.list_conversations(agent_name='backlog_assistant', limit=50, days_limit=30),
                timeout=5.0
            )
            print(f"Success! Found {len(convs)} conversations.")
            for c in convs:
                 # Check if we can serialize to the format agents.py uses
                 data = {
                    "id": c.id,
                    "thread_id": c.thread_id,
                    "title": c.title,
                    "agent_name": c.agent_name,
                    "status": c.status,
                    "metadata": c.metadata_json,
                    "created_at": c.created_at.isoformat(),
                    "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                 }
                 import json
                 json.dumps(data)
            print("Serialization test passed.")
            break
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
