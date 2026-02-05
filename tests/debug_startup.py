import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from app.main import app
from app.core.config import settings

async def debug_startup():
    print("Starting Manual Application Debug...")
    print(f"RAG Backend: {settings.RAG_BACKEND}")
    print(f"Mocks Enabled: {settings.BACKLOG_USE_MOCKS}")
    
    try:
        # Manually trigger lifespan
        async with app.router.lifespan_context(app):
            print("Lifespan successfully initialized!")
            print("App is ready to receive requests.")
            # Keep it open for a second
            await asyncio.sleep(1)
            print("Shutting down cleanly.")
    except Exception as e:
        print(f"CRASH DETECTED during startup: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_startup())
