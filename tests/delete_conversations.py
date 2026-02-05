import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from sqlalchemy import delete
from app.core.db.database import async_engine
from app.models.agentic import Conversation, Message, LangGraphCheckpoint

async def delete_all_conversations():
    print("🚀 Starting Data Cleanup: Deleting all conversations and messages...")
    try:
        async with async_engine.begin() as conn:
            # 1. Delete all messages first (foreign key dependency)
            res_m = await conn.execute(delete(Message))
            print(f"✅ Deleted {res_m.rowcount} messages.")
            
            # 2. Delete all conversations
            res_c = await conn.execute(delete(Conversation))
            print(f"✅ Deleted {res_c.rowcount} conversations.")
            
            # 3. Delete all LangGraph checkpoints (actual agent memory)
            res_l = await conn.execute(delete(LangGraphCheckpoint))
            print(f"✅ Deleted {res_l.rowcount} LangGraph checkpoints.")
            
        print("\n✨ All conversation data has been permanently deleted.")
        return True
    except Exception as e:
        print(f"❌ Error during deletion: {e}")
        return False

if __name__ == "__main__":
    confirm = input("Are you absolutely sure you want to DELETE ALL CONVERSATIONS? (y/N): ")
    if confirm.lower() == 'y':
        asyncio.run(delete_all_conversations())
    else:
        print("Cleanup cancelled.")
