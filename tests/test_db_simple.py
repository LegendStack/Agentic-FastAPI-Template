import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from app.core.db.database import async_engine

async def test_db():
    print("Testing database connection...")
    try:
        async with async_engine.connect() as conn:
            result = await conn.execute("SELECT 1")
            print(f"Database connection successful: {result.scalar()}")
            return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_db())
