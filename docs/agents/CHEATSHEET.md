# Agentic Framework Cheat Sheet 🚀

> Copy-paste snippets for common tasks. All examples are async-ready.

---

## 🔌 Setup

```python
# In your startup code (e.g., main.py or lifespan)
from app.core.integration_config import configure_integrations

configure_integrations()  # Reads from .env, configures all clients
```

---

## 💬 Azure OpenAI

```python
from app.core.integration_config import get_azure_openai_client

client = get_azure_openai_client()

# Chat
response = await client.chat(
    messages=[
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello!"}
    ],
    deployment="gpt-4o"
)
print(response["choices"][0]["message"]["content"])

# Embeddings
vectors = await client.embed(["text to embed"], deployment="text-embedding-ada-002")
```

---

## 🔍 Vector Search

```python
from app.agents import PgVectorStore

store = PgVectorStore(db_session, embedding_fn)

# Add documents
await store.add_documents([
    {"content": "Doc 1", "metadata": {"source": "file.pdf"}},
    {"content": "Doc 2", "metadata": {"source": "file.pdf"}},
])

# Search
results = await store.search("my query", k=5, filter={"source": "file.pdf"})
```

---

## 🎯 Reranking

```python
from app.agents import RerankingService, CrossEncoderReranker

reranker = RerankingService(CrossEncoderReranker())
top_docs = await reranker.rerank("my query", docs, top_k=5)
```

**With Cohere:**
```python
from app.agents import CohereReranker

reranker = RerankingService(CohereReranker(api_key="..."))
```

---

## 🧠 Memory Management

```python
from app.agents import MemoryManager, SummarizationStrategy

# With summarization (for long conversations)
memory = MemoryManager(conv_service, llm, strategy=SummarizationStrategy(...))

# Get context that fits in token budget
context = await memory.get_context("thread-123", max_tokens=4000)
```

---

## 🛡️ Resilience

```python
from app.agents import ResilientClient, RetryConfig, CircuitBreakerConfig

client = ResilientClient(
    name="openai",
    retry_config=RetryConfig(max_attempts=3),
    circuit_config=CircuitBreakerConfig(failure_threshold=5)
)

result = await client.execute(my_async_fn, arg1, arg2)
```

**Decorator style:**
```python
from app.agents import with_retry

@with_retry(max_attempts=3)
async def flaky_operation():
    ...
```

---

## 📊 Rate Limiting

```python
from app.agents import rate_limiter, RateLimitExceeded

try:
    await rate_limiter.enforce_limit("tenant-123", tokens_requested=1000)
    response = await call_llm(prompt)
    await rate_limiter.record_usage("tenant-123", tokens_used=response.usage.total)
except RateLimitExceeded:
    return {"error": "Rate limit exceeded"}

# Set tier
rate_limiter.set_tenant_tier("tenant-123", "premium")  # free, standard, premium, enterprise

# Get usage
usage = await rate_limiter.get_usage("tenant-123")
print(f"{usage.tokens_used}/{usage.tokens_limit} tokens")
```

---

## 📝 Prompts

```python
from app.agents import prompt_registry

# Get prompt
prompt = await prompt_registry.get("system_prompt")

# Create new version
await prompt_registry.set("system_prompt", "New content", created_by="admin")

# Rollback
await prompt_registry.rollback("system_prompt", version=1)

# A/B test
v1 = await prompt_registry.get("system_prompt", version=1)
v2 = await prompt_registry.get("system_prompt", version=2)
```

---

## 🔗 Enterprise Integrations

**Jira:**
```python
from app.core.integration_config import get_jira_client

jira = get_jira_client()
issues = await jira.search_issues("project = MYPROJ AND status = Open")
issue = await jira.get_issue("MYPROJ-123")
```

**Confluence:**
```python
from app.core.integration_config import get_confluence_client

confluence = get_confluence_client()
page = await confluence.get_page("12345")
results = await confluence.search_content("space = DOCS AND text ~ 'deployment'")
```

**Microsoft Graph:**
```python
from app.core.integration_config import get_microsoft_graph_client

graph = get_microsoft_graph_client()
user = await graph.get_user()
files = await graph.list_drive_items("/Documents")
await graph.send_mail("user@example.com", "Subject", "Body")
```

---

## 📡 WebSocket Streaming

**Server:**
```python
from fastapi import WebSocket
from app.agents import ws_manager, AgentWSHandler

@app.websocket("/ws/chat/{thread_id}")
async def websocket_endpoint(ws: WebSocket, thread_id: str):
    await ws_manager.connect(ws, thread_id)
    handler = AgentWSHandler(ws_manager, agent, thread_id)
    try:
        await handler.handle_connection(ws)
    finally:
        await ws_manager.disconnect(thread_id)
```

**Client (JS):**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat/thread-123');
ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'token') document.body.innerHTML += msg.data.token;
};
ws.send(JSON.stringify({type: 'message', data: {content: 'Hello'}}));
```

---

## 📊 Indexers

**Documents:**
```python
from app.agents import DocumentIndexer

indexer = DocumentIndexer(vector_store, llm, source_dir="/docs")
stats = await indexer.run()  # Indexes PDF, TXT, MD files
```

**Jira:**
```python
from app.agents import JiraIndexer

indexer = JiraIndexer(vector_store, llm, 
    jira_url="https://...", username="...", api_token="...")
await indexer.run()
```

**SharePoint:**
```python
from app.agents import SharePointIndexer

indexer = SharePointIndexer(vector_store, llm,
    site_url="https://...", client_id="...", client_secret="...")
await indexer.run()
```

---

## 🔧 Component Registry

```python
from app.agents import registry

# List components
registry.list_vector_stores()  # ['pgvector', 'azure_search']
registry.list_indexers()       # ['document', 'jira']
registry.list_agents()         # ['doc_assistant']

# Register custom
registry.register_agent("my_agent", MyAgentClass)

# Get component
AgentClass = registry.get_agent("my_agent")
```

---

## ⚙️ Environment Variables

```env
# Auth modes: api_key | oauth2 | managed_identity | pat | basic
AZURE_OPENAI_AUTH_MODE=api_key
JIRA_AUTH_MODE=pat
CONFLUENCE_AUTH_MODE=oauth2
SHAREPOINT_AUTH_MODE=oauth2

# Rate limiting tiers: free | standard | premium | enterprise
DEFAULT_RATE_LIMIT_TIER=standard
```


---

## 🔒 Security & Privacy (V4.1)

**Zero-Trust Encryption:**
```python
from app.core.security_utils import TenantEncryption

# Encrypt data for a specific tenant
encrypted = TenantEncryption.encrypt("secret_value", "tenant-1")

# Decrypt (only works with correct tenant_id)
decrypted = TenantEncryption.decrypt(encrypted, "tenant-1")
```

**Entity-Aware Memory:**
```python
# Automatic: Just set env var
# ENABLE_ENTITY_MEMORY=true

# Manual: Check graph connections
from app.core.graph_db import GraphDBClient

client = GraphDBClient()
# Find entities related to "Project Omega"
result = await client.execute_query(
    "MATCH (e:Project {name: $name})<-[:RELATED]-(m) RETURN m",
    {"name": "project omega"}
)
```

---


## 🧪 Testing

```bash
# Run all agentic tests
uv run pytest tests/test_phase6_unit.py tests/test_phase6_integration.py tests/test_credentials.py -v

# Quick smoke test
uv run python -c "from app.agents import registry; print(registry.list_agents())"
```
