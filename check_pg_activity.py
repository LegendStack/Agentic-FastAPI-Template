import asyncio
import asyncpg

async def check():
    print("Checking for active transactions...", flush=True)
    try:
        conn = await asyncpg.connect(user='postgres', password='1234', database='postgres', host='localhost')
        rows = await conn.fetch("SELECT pid, state, query FROM pg_stat_activity WHERE state != 'idle'")
        for row in rows:
            print(f"PID: {row['pid']} | State: {row['state']} | Query: {row['query']}", flush=True)
        await conn.close()
    except Exception as e:
        print(f"Error: {e}", flush=True)

if __name__ == "__main__":
    asyncio.run(check())
