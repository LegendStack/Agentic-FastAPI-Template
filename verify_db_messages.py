
import asyncio
from src.app.core.db.database import local_session
from src.app.agents.conversations import ConversationService

async def verify_messages(thread_id: str):
    async with local_session() as db:
        service = ConversationService(db)
        messages = await service.get_messages(thread_id)
        print(f"\n--- Messages for Thread {thread_id} ---")
        for m in messages:
            print(f"[{m.role.upper()}] {m.content[:100]}...")
        
        roles = [m.role for m in messages]
        if "assistant" in roles and any("proceed" in m.content.lower() for m in messages if m.role == "assistant"):
            print("\n✅ SUCCESS: Confirmation message found in database!")
        else:
            print("\n❌ FAILURE: Confirmation message NOT found in database.")

if __name__ == "__main__":
    import sys
    thread_id = sys.argv[1] if len(sys.argv) > 1 else "946f5301-b328-47f3-a7ab-a44d7f7b6b45"
    asyncio.run(verify_messages(thread_id))
