import redis
from src.app.core.config import settings

try:
    r = redis.from_url(settings.REDIS_URL)
    r.flushall()
    print("Redis cache flushed successfully.")
except Exception as e:
    print(f"Failed to flush Redis: {e}")
