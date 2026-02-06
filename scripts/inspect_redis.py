import redis
import os
from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
print(f"Connecting to Redis at {redis_url}")

r = redis.from_url(redis_url)

# In LangChain RedisSemanticCache, keys are usually prefixed
# Let's find all keys
keys = r.keys("*")
print(f"Found {len(keys)} keys")

for key in keys:
    key_str = key.decode('utf-8')
    # RedisSemanticCache uses a specific format. 
    # Usually it's a hash or a list.
    type_info = r.type(key).decode('utf-8')
    print(f"Key: {key_str} | Type: {type_info}")
    
    # If it's the vector index, we can't easily read it with standard redis-py
    # But often there are metadata keys.
