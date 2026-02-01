# Integration Guide

> **Goal**: Go from mock services to YOUR production infrastructure in 15 minutes.

This guide walks you through connecting LegendStack to real services. Each section is independent—do only what you need.

---

## Quick Reference

| Service | Mock Class | Real Service | Time |
|---------|-----------|--------------|------|
| LLM | `MockLLM` | Azure OpenAI | 5 min |
| Vector Store | `MockVectorStore` | Azure AI Search / pgvector | 5 min |
| Graph DB | `MockGraphDB` | Neo4j | 5 min |
| Cache | In-memory | Redis | 2 min |

---

## 1. Connect Azure OpenAI

### Step 1: Get Your Credentials

From the [Azure Portal](https://portal.azure.com):
1. Navigate to your Azure OpenAI resource
2. Go to **Keys and Endpoint**
3. Copy:
   - Endpoint URL
   - API Key
   - Deployment name (e.g., `gpt-4o`)

### Step 2: Update Environment

Add to `src/.env`:

```env
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Embeddings (if using separate deployment)
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002
```

### Step 3: Use Real LLM in Your Agent

```python
# Instead of MockLLM, use the real client
from app.core.integration_config import get_azure_openai_client

# In your agent's _init_services():
if self.config.USE_MOCKS:
    self.llm = MockLLM()
else:
    self.llm = get_azure_openai_client()
```

### Step 4: Verify

```python
# Quick test
from app.core.integration_config import get_azure_openai_client

client = get_azure_openai_client()
response = await client.chat(
    messages=[{"role": "user", "content": "Hello!"}],
    model="gpt-4o"
)
print(response.choices[0].message.content)
```

### Troubleshooting

| Error | Solution |
|-------|----------|
| `AuthenticationError` | Check API key is correct |
| `DeploymentNotFound` | Verify deployment name matches Azure portal |
| `RateLimitError` | Your quota is exceeded—wait or upgrade |
| `InvalidRequestError` | Check API version compatibility |

---

## 2. Connect Azure AI Search

### Step 1: Get Your Credentials

From the [Azure Portal](https://portal.azure.com):
1. Navigate to your Azure AI Search resource
2. Go to **Keys**
3. Copy:
   - Search endpoint
   - Admin key (for indexing) or Query key (for search only)

### Step 2: Update Environment

```env
# Azure AI Search
AZURE_SEARCH_ENDPOINT=https://YOUR-SEARCH.search.windows.net
AZURE_SEARCH_API_KEY=your-admin-key
AZURE_SEARCH_INDEX_NAME=your-index-name
```

### Step 3: Use Real Vector Store

```python
from app.agents.vector_stores import VectorStoreFactory

# Create Azure Search vector store
vector_store = VectorStoreFactory.create(
    store_type="azure_search",
    index_name="your-index-name"
)

# Search
results = await vector_store.similarity_search(
    query="What is RAG?",
    k=5
)
```

### Step 4: Create Your Index

If you don't have an index yet:

```python
from app.agents.vector_stores import AzureSearchVectorStore

store = AzureSearchVectorStore(index_name="my-knowledge-base")

# Add documents
await store.add_documents([
    {"id": "1", "content": "Your document text here", "metadata": {...}},
])
```

---

## 3. Connect Neo4j (Graph-RAG)

### Step 1: Get Your Credentials

From [Neo4j Aura](https://neo4j.com/cloud/aura/) or your self-hosted instance:
1. Connection URI (e.g., `neo4j+s://xxxx.databases.neo4j.io`)
2. Username (usually `neo4j`)
3. Password

### Step 2: Update Environment

```env
# Neo4j
NEO4J_URI=neo4j+s://YOUR-INSTANCE.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
```

### Step 3: Use Real Graph DB

```python
from app.core.graph_db import GraphDBClient

# The client auto-connects using env vars
graph_client = GraphDBClient()

# Query
results = await graph_client.execute_query(
    "MATCH (n:Entity {name: $name})-[r]->(m) RETURN n, r, m",
    {"name": "LegendStack"}
)
```

### Step 4: Seed Your Graph

```python
# Create initial entities
await graph_client.execute_query("""
    MERGE (p:Project {name: $name})
    SET p.description = $description
""", {"name": "MyProject", "description": "My awesome project"})
```

---

## 4. Connect Redis (Caching)

### Step 1: Update Environment

```env
# Redis
REDIS_CACHE_HOST=your-redis-host.redis.cache.windows.net
REDIS_CACHE_PORT=6380
REDIS_CACHE_PASSWORD=your-access-key
REDIS_CACHE_SSL=true
```

### Step 2: Verify Connection

```python
from app.core.cache import get_redis_client

client = get_redis_client()
await client.ping()  # Should return True
```

---

## 5. Switch Demo Agent to Real Services

The Demo Agent has a `USE_MOCKS` toggle. To use real services:

```python
from app.agents.demo import LegendDemoAgent, DemoAgentConfig

# Create config with mocks disabled
config = DemoAgentConfig(
    USE_MOCKS=False,  # <-- This is the key change
    # All other features still work
    ENABLE_RAG=True,
    ENABLE_GRAPH_RAG=True,
    ENABLE_SEMANTIC_CACHE=True,
)

# Agent will now use real Azure OpenAI, AI Search, Neo4j
agent = LegendDemoAgent(config=config)
```

> **Note**: You'll need to implement the real service initialization in `demo_agent.py` `_init_services()` method. The mock version shows you exactly what interface each service needs.

---

## Environment Template

Here's a complete `.env` for production:

```env
# === Application ===
APP_NAME="My Agentic App"
ENVIRONMENT="production"

# === Azure OpenAI ===
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002

# === Azure AI Search ===
AZURE_SEARCH_ENDPOINT=https://YOUR-SEARCH.search.windows.net
AZURE_SEARCH_API_KEY=your-key
AZURE_SEARCH_INDEX_NAME=knowledge-base

# === Neo4j ===
NEO4J_URI=neo4j+s://YOUR-INSTANCE.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password

# === Redis ===
REDIS_CACHE_HOST=your-redis.redis.cache.windows.net
REDIS_CACHE_PORT=6380
REDIS_CACHE_PASSWORD=your-key
REDIS_CACHE_SSL=true

# === Database ===
POSTGRES_SERVER=your-postgres.postgres.database.azure.com
POSTGRES_USER=admin
POSTGRES_PASSWORD=your-password
POSTGRES_DB=agenticapp

# === Security ===
SECRET_KEY=generate-with-openssl-rand-hex-32
```

---

## Next Steps

- [Customization Cookbook](cookbook.md) - Add your business logic
- [Production Checklist](production-checklist.md) - Security & scaling
