# Agentic Framework Documentation

A production-ready, enterprise-grade agentic AI framework built on FastAPI with pluggable components and best practices.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture Overview](#architecture-overview)
3. [Authentication & Integrations](#authentication--integrations)
4. [Agent Components](#agent-components)
5. [Memory Management](#memory-management)
6. [RAG & Reranking](#rag--reranking)
7. [Resilience Patterns](#resilience-patterns)
8. [Rate Limiting](#rate-limiting)
9. [Prompt Versioning](#prompt-versioning)
10. [WebSocket Streaming](#websocket-streaming)
11. [Enterprise Indexers](#enterprise-indexers)
12. [Admin API](#admin-api)
13. [Observability](#observability)
14. [RAG Evaluation (V3.0)](#rag-evaluation-v30)
15. [Safety & Guardrails (V3.0)](#safety--guardrails-v30)
16. [Multi-Agent Orchestration (V3.0)](#multi-agent-orchestration-v30)
17. [Graph-RAG (V3.0)](#graph-rag-v30)
18. [LegendStack Studio & CLI (V3.0)](#legendstack-studio--cli-v30)

---

## Quick Start

### 1. Configure Environment

```bash
cp src/.env.example src/.env
# Edit .env with your credentials
```

### 2. Start Services

```bash
docker-compose up -d
uv run uvicorn src.app.main:app --reload
```

### 3. Initialize Integrations

```python
from app.core.integration_config import configure_integrations

# Auto-configure all integrations from environment
configure_integrations()
```

---

## Architecture Overview

```
src/app/
├── agents/                 # Agentic framework (30+ modules)
│   ├── base.py            # Core abstractions
│   ├── azure_openai.py    # LLM service
│   ├── supervisor.py      # [NEW] Multi-agent orchestrator
│   ├── graph_retriever.py # [NEW] Hybrid Graph-RAG
│   ├── vector_stores.py   # pgvector implementation
│   ├── connectors/        # [NEW] Ingestion marketplace
│   │   ├── registry.py    # Central connector registry
│   │   ├── slack.py       # Example connector
│   │   └── zendesk.py     # Example connector
│   ├── conversations.py   # Thread management
│   ├── hitl.py            # Human-in-the-loop
│   ├── resilience.py      # Circuit breaker, retry
│   ├── rate_limiting.py   # Per-tenant limits
│   └── __init__.py        # Component registry
├── eval/                  # [NEW] RAG Evaluation Engine
│   ├── engine.py          # Ragas integration
│   └── __init__.py
├── guardrails/            # [NEW] Safety filters
│   ├── pii.py             # PII masking
│   ├── moderation.py      # Content moderation
│   └── __init__.py
├── cli/                   # [NEW] Scaffolding tool
│   └── main.py            # legendstack-cli
├── core/
│   ├── graph_db.py        # [NEW] Neo4j client
│   ├── credentials.py     # Auth providers
│   └── clients.py         # Integration clients
└── api/v1/
    ├── agents.py          # Agent API
    └── admin_agents.py    # Admin API
```

---

## Authentication & Integrations

### Overview

The framework supports multiple authentication methods per integration:

| Integration | API Key | OAuth2 | Managed Identity | PAT |
|------------|---------|--------|------------------|-----|
| Azure OpenAI | ✅ | ✅ | ✅ | - |
| Azure AI Search | ✅ | ✅ | ✅ | - |
| Microsoft Graph | - | ✅ | ✅ | - |
| Jira Cloud | - | ✅ | - | - |
| Jira Server | - | - | - | ✅ |
| Confluence Cloud | - | ✅ | - | - |
| Confluence Server | - | - | - | ✅ |
| SharePoint | - | ✅ | ✅ | - |
| Cohere | ✅ | - | - | - |

### Configuration

```env
# Azure OpenAI - API Key mode
AZURE_OPENAI_AUTH_MODE="api_key"
AZURE_OPENAI_API_KEY="your-key"
AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"

# Azure OpenAI - OAuth2 mode
AZURE_OPENAI_AUTH_MODE="oauth2"
AZURE_OPENAI_CLIENT_ID="app-client-id"
AZURE_OPENAI_CLIENT_SECRET="client-secret"
AZURE_TENANT_ID="tenant-id"

# Azure OpenAI - Managed Identity (in Azure)
AZURE_OPENAI_AUTH_MODE="managed_identity"
AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
```

### Usage

```python
from app.core.integration_config import (
    configure_integrations,
    get_azure_openai_client,
    get_azure_search_client,
    get_jira_client,
    get_confluence_client,
    get_microsoft_graph_client,
    get_cohere_client,
)

# Auto-configure from environment
configure_integrations()

# Azure OpenAI
openai = get_azure_openai_client()
response = await openai.chat(
    messages=[{"role": "user", "content": "Hello!"}],
    deployment="gpt-4o"
)

# Azure AI Search
search = get_azure_search_client()
results = await search.vector_search(
    vector=embedding,
    k=10,
    filter="category eq 'docs'"
)

# Jira
jira = get_jira_client()
issues = await jira.search_issues("project = MYPROJ ORDER BY created DESC")
new_issue = await jira.create_issue("MYPROJ", "Bug title", "Bug")

# Microsoft Graph
graph = get_microsoft_graph_client()
user = await graph.get_user()
files = await graph.list_drive_items("/Documents")
await graph.send_mail("user@example.com", "Subject", "Body")
```

### Custom Credential Provider

```python
from app.core.credentials import OAuth2ClientCredentialsProvider
from app.core.clients import IntegrationClientFactory, IntegrationConfig, Integration

# Create custom provider
provider = OAuth2ClientCredentialsProvider(
    client_id="your-client-id",
    client_secret="your-secret",
    token_url="https://auth.example.com/oauth/token",
    scope="api://your-api/.default"
)

# Get credentials
creds = await provider.get_credentials()
print(creds.token.access_token)  # Auto-refreshed when expired
```

---

## Agent Components

### Component Registry

```python
from app.agents import registry

# List available components
print(registry.list_vector_stores())  # ['pgvector', 'azure_search']
print(registry.list_indexers())       # ['document', 'jira']
print(registry.list_agents())         # ['doc_assistant']

# Register custom components
registry.register_vector_store("pinecone", PineconeVectorStore)
registry.register_agent("custom_agent", MyCustomAgent)
```

### Creating a Custom Agent

```python
from app.agents import BaseAgent, AgentMessage

class MyAgent(BaseAgent):
    """Custom agent implementation."""
    
    async def process(self, message: AgentMessage) -> AgentMessage:
        # Get context from vector store
        docs = await self.vector_store.search(message.content, k=5)
        
        # Build prompt with context
        context = "\n".join([d["content"] for d in docs])
        
        # Call LLM
        response = await self.llm.chat([
            {"role": "system", "content": f"Context:\n{context}"},
            {"role": "user", "content": message.content}
        ])
        
        return AgentMessage(
            role="assistant",
            content=response.content
        )

# Register
registry.register_agent("my_agent", MyAgent)
```

---

## Memory Management

### Truncation Strategy

Keeps most recent messages within token budget:

```python
from app.agents import MemoryManager, TruncationStrategy

# Create with default strategy
memory = MemoryManager(conversation_service, llm_service)

# Get context within token limit
context = await memory.get_context("thread-123", max_tokens=4000)
```

### Summarization Strategy

Summarizes older messages to preserve context:

```python
from app.agents import MemoryManager, SummarizationStrategy

# Use summarization for long conversations
strategy = SummarizationStrategy(
    conversation_service,
    llm_service,
    summary_threshold=20  # Summarize when > 20 messages
)
memory = MemoryManager(conversation_service, llm_service, strategy=strategy)

# Get context with automatic summarization
context = await memory.get_context("thread-123", max_tokens=4000)
```

---

## RAG & Reranking

### Cross-Encoder Reranking

```python
from app.agents import RerankingService, CrossEncoderReranker

# Create reranker
reranker = CrossEncoderReranker(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2")
service = RerankingService(reranker)

# Rerank retrieved documents
query = "How do I deploy to production?"
docs = await vector_store.search(query, k=20)
reranked = await service.rerank(query, docs, top_k=5)
```

### Cohere Reranking

```python
from app.agents import CohereReranker, RerankingService

reranker = CohereReranker(api_key="your-key", model="rerank-english-v2.0")
service = RerankingService(reranker)

reranked = await service.rerank(query, docs, top_k=5)
```

---

## Resilience Patterns

### Circuit Breaker

```python
from app.agents import CircuitBreaker, CircuitBreakerConfig

config = CircuitBreakerConfig(
    failure_threshold=5,       # Open after 5 failures
    timeout_seconds=60,        # Stay open for 60s
    half_open_max_calls=3      # Allow 3 test calls in half-open
)
breaker = CircuitBreaker(config, name="openai")

# Use as context manager
async with breaker:
    response = await call_openai(prompt)
```

### Retry with Backoff

```python
from app.agents import retry_with_backoff, RetryConfig

config = RetryConfig(
    max_attempts=3,
    initial_delay=1.0,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True
)

result = await retry_with_backoff(flaky_function, config)
```

### Resilient Client (Combined)

```python
from app.agents import ResilientClient

client = ResilientClient(
    name="openai",
    retry_config=RetryConfig(max_attempts=3),
    circuit_config=CircuitBreakerConfig(failure_threshold=5)
)

# Automatically retries with circuit breaker protection
result = await client.execute(call_llm, prompt)
```

---

## Rate Limiting

### Per-Tenant Limits

```python
from app.agents import rate_limiter, RateLimitExceeded

# Check and enforce limits
try:
    await rate_limiter.enforce_limit("tenant-123", tokens_requested=1000)
    
    # Make API call
    response = await call_llm(prompt)
    
    # Record usage
    await rate_limiter.record_usage(
        "tenant-123",
        tokens_used=response.usage.total_tokens
    )
except RateLimitExceeded as e:
    return {"error": "Rate limit exceeded", "retry_after": e.retry_after}
```

### Tier System

```python
from app.agents import RATE_LIMIT_TIERS

# Available tiers
# free:       10K tokens/min, 100 requests/min
# standard:   50K tokens/min, 500 requests/min
# premium:    200K tokens/min, 2000 requests/min
# enterprise: 1M tokens/min, 10000 requests/min

# Set tenant tier
rate_limiter.set_tenant_tier("tenant-123", "premium")

# Get usage stats
usage = await rate_limiter.get_usage("tenant-123")
print(f"Used {usage.tokens_used}/{usage.tokens_limit} tokens")
```

---

## Prompt Versioning

### Managing Prompts

```python
from app.agents import prompt_registry, initialize_default_prompts

# Initialize defaults
initialize_default_prompts()

# Get a prompt
system_prompt = await prompt_registry.get("doc_assistant_system")

# Create new version
await prompt_registry.set(
    "doc_assistant_system",
    "You are an expert document assistant...",
    created_by="admin",
    metadata={"experiment": "v2"}
)

# List versions
versions = await prompt_registry.list_versions("doc_assistant_system")
for v in versions:
    print(f"v{v.version}: {v.created_at} by {v.created_by}")

# Rollback
await prompt_registry.rollback("doc_assistant_system", version=1)
```

### A/B Testing

```python
import random

# Get specific versions for A/B test
v1_prompt = await prompt_registry.get("system_prompt", version=1)
v2_prompt = await prompt_registry.get("system_prompt", version=2)

# Select version
prompt = v1_prompt if random.random() < 0.5 else v2_prompt
```

---

## WebSocket Streaming

### Server Setup

```python
from fastapi import WebSocket
from app.agents import ws_manager, AgentWSHandler

@app.websocket("/ws/agent/{thread_id}")
async def agent_websocket(websocket: WebSocket, thread_id: str):
    conn = await ws_manager.connect(websocket, thread_id, user_id="user-123")
    
    handler = AgentWSHandler(ws_manager, agent, thread_id)
    
    try:
        await handler.handle_connection(websocket)
    finally:
        await ws_manager.disconnect(thread_id)
```

### Client Usage

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/agent/thread-123');

ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    
    switch (msg.type) {
        case 'token':
            // Streaming token
            appendToResponse(msg.data.token);
            break;
        case 'tool_call':
            // Tool being called
            showToolCall(msg.data);
            break;
        case 'complete':
            // Response complete
            finalizeResponse();
            break;
    }
};

// Send message
ws.send(JSON.stringify({
    type: 'message',
    data: { content: 'Hello!' }
}));
```

---

## Enterprise Indexers

### SharePoint

```python
from app.agents import SharePointIndexer

indexer = SharePointIndexer(
    vector_store=vector_store,
    llm_service=llm_service,
    site_url="https://contoso.sharepoint.com/sites/docs",
    client_id="app-client-id",
    client_secret="secret"
)

# Run indexing
stats = await indexer.run(force=False)  # Incremental
print(f"Indexed {stats['documents_indexed']} documents")
```

### Confluence

```python
from app.agents import ConfluenceIndexer

indexer = ConfluenceIndexer(
    vector_store=vector_store,
    llm_service=llm_service,
    base_url="https://company.atlassian.net/wiki",
    username="user@company.com",
    api_token="token",
    spaces=["DOCS", "KB"]
)

stats = await indexer.run()
```

### Jira

```python
from app.agents import JiraIndexer

indexer = JiraIndexer(
    vector_store=vector_store,
    llm_service=llm_service,
    jira_url="https://company.atlassian.net",
    username="user@company.com",
    api_token="token",
    projects=["PROJ1", "PROJ2"]
)

stats = await indexer.run()
```

---

## Admin API

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/admin/agents/stats` | GET | Agent usage statistics |
| `/api/v1/admin/agents/conversations` | GET | List conversations |
| `/api/v1/admin/agents/costs` | GET | LLM costs summary |
| `/api/v1/admin/agents/usage/{tenant_id}` | GET | Tenant rate limit usage |
| `/api/v1/admin/agents/usage/{tenant_id}/tier` | POST | Set tenant tier |
| `/api/v1/admin/agents/hitl/pending` | GET | Pending HITL requests |
| `/api/v1/admin/agents/hitl/stats` | GET | HITL queue statistics |

### Usage

```bash
# Get stats
curl http://localhost:8000/api/v1/admin/agents/stats

# Get costs for last 7 days
curl "http://localhost:8000/api/v1/admin/agents/costs?days=7"

# Set tenant tier
curl -X POST "http://localhost:8000/api/v1/admin/agents/usage/tenant-123/tier" \
  -H "Content-Type: application/json" \
  -d '{"tier": "premium"}'
```

---

## Observability

### OpenTelemetry Setup

```python
from app.agents import setup_telemetry, get_tracer, trace_llm_call

# Initialize telemetry
setup_telemetry(
    service_name="my-agent-app",
    otlp_endpoint="http://localhost:4317"
)

# Get tracer
tracer = get_tracer()

# Trace LLM calls
@trace_llm_call(model="gpt-4")
async def call_llm(prompt: str):
    return await openai.chat(...)
```

### Datadog Integration

```env
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT="http://datadog-agent:4317"
DD_SERVICE="my-agent-app"
DD_ENV="production"
DD_VERSION="2.1.0"
```

### Cost Tracking

```python
from app.agents import record_llm_cost, calculate_cost

# Record usage
await record_llm_cost(
    model="gpt-4",
    prompt_tokens=500,
    completion_tokens=200,
    tenant_id="tenant-123"
)

# Calculate costs
cost = calculate_cost("gpt-4", prompt_tokens=500, completion_tokens=200)
print(f"Cost: ${cost:.4f}")
```

---

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test files
uv run pytest tests/test_credentials.py tests/test_phase6_unit.py -v

# Run with coverage
uv run pytest tests/ --cov=src/app/agents --cov-report=html
```

---

---

## RAG Evaluation (V3.0)

Automated quality metrics for RAG pipelines using **Ragas**.

```python
from app.eval import get_eval_engine

engine = get_eval_engine()
results = await engine.run_eval(
    questions=["What is LegendStack?"],
    answers=["LegendStack is an agentic framework..."],
    contexts=[["LegendStack is an enterprise-ready template..."]],
    ground_truths=["LegendStack is an agentic AI template built on FastAPI."]
)

# Output includes Faithfulness, Answer Relevancy, etc.
print(results)
```

---

## Safety & Guardrails (V3.0)

Enterprise-grade security for LLM I/O.

### PII Masking
```python
from app.guardrails import get_pii_guard

guard = get_pii_guard()
masked_text = guard.mask("My email is john@example.com")
# Output: "My email is [MASKED]_EMAIL"
```

### Hallucination Detection
```python
from app.guardrails import get_moderator

moderator = get_moderator()
judgement = await moderator.check_hallucination(context, answer)
print(judgement["is_hallucination"])
```

---

## Multi-Agent Orchestration (V3.0)

Coordinate complex tasks between specialized agents using the **Supervisor Pattern**.

```python
from app.agents.supervisor import SupervisorAgent

supervisor = SupervisorAgent(workers=["Researcher", "DocumentExpert"])
result = await supervisor.run("Research the latest AI trends in the docs.", thread_id="thread-456")
```

---

## Graph-RAG (V3.0)

Hybrid search combining Vector similarity with **Neo4j** relationship traversal.

```python
from app.agents.graph_retriever import GraphRetriever
from app.core.graph_db import get_graph_client

retriever = GraphRetriever(vector_store, get_graph_client())
# Performs vector search + Cypher relationship expansion
results = await retriever.retrieve(query_vector, k=5)
```

---

## LegendStack Studio & CLI (V3.0)

### Scaffolding CLI
Generate framework-compliant components instantly.
```bash
uv run python src/app/cli/main.py create-agent MyNewAgent
uv run python src/app/cli/main.py create-connector Slack
```

### Studio Dashboard
Visual monitoring and HITL management.
```bash
uv run streamlit run studio/main.py
```

---

## Version History

| Version | Features |
|---------|----------|
| 1.0.0 | Core agents, pgvector, Azure OpenAI |
| 1.1.0 | Azure Search, HITL, multi-tenant, background tasks |
| 1.2.0 | OpenTelemetry, cost tracking, HNSW index |
| 2.0.0 | Memory, reranking, resilience, rate limiting, prompts, WebSocket |
| 3.0.0 | **Framework Expansion**: Eval Engine, Safety Guardrails, Multi-Agent, Graph-RAG, Studio & CLI |
