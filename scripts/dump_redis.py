import redis
import os
import json
from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
r = redis.from_url(redis_url)

keys = r.keys("*")
for key in keys:
    key_str = key.decode('utf-8')
    print(f"\n--- Key: {key_str} ---")
    if r.type(key).decode('utf-8') == 'hash':
        data = r.hgetall(key)
        for field, value in data.items():
            print(f"Field: {field.decode('utf-8')}")
            # Try to decode value
            try:
                val_str = value.decode('utf-8')
                print(f"Value Preview: {val_str[:200]}...")
            except:
                print("Value: [Binary]")
