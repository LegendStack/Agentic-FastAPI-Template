<h1 align="center"> LegendStack Agentic FastAPI Template</h1>
<p align="center" markdown=1>
  <i><b>Enterprise-ready Agentic AI template</b> built on top of FastAPI and LangGraph. Batteries-included with production-ready defaults.</i>
</p>

<p align="center">
  <a href="https://github.com/LegendStack/agentic-fastapi-template">
    <img src="docs/assets/banner.png" alt="LegendStack Agentic Template" width="80%" height="auto">
  </a>
</p>

<p align="center">
📚 <a href="https://LegendStack.github.io/agentic-fastapi-template/">Docs</a> · 💬 <a href="https://discord.gg/legendstack">Discord</a>
</p>

> [!NOTE]
> **Educational Purpose**: This project is intended for educational purposes and as a reference implementation for Agentic AI patterns. While built with enterprise practices in mind, please review all security configurations before deploying to production.

<p align="center">
  <a href="https://fastapi.tiangolo.com">
      <img src="https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi" alt="FastAPI">
  </a>
  <a href="https://www.postgresql.org">
      <img src="https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL">
  </a>
  <a href="https://redis.io">
      <img src="https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=fff&style=for-the-badge" alt="Redis">
  </a>
  <a href="https://deepwiki.com/benavlabs/FastAPI-boilerplate">
      <img src="https://img.shields.io/badge/DeepWiki-1F2937?style=for-the-badge&logoColor=white" alt="DeepWiki">
  </a>
</p>

## Features

* ⚡️ **Fully Async**: FastAPI + SQLAlchemy 2.0 for maximum concurrency
* 🧱 **Pydantic V2**: Ultra-fast data validation and serialization
* 🔐 **Hybrid Auth**: JWT-based (access + refresh), SECURE cookie storage, and **Microsoft Entra ID** (Azure AD) native support
* 👮 **Advanced Rate Limiting**: Per-tenant limits with tiered service levels (Free/Standard/Premium)
* 🧰 **FastCRUD**: Automated CRUD endpoints with advanced filtering and pagination
* 🧑‍💼 **CRUDAdmin**: Clean, plug-and-play admin interface
* 🚦 **Background Processing**: ARQ (Redis-backed) for reliable task execution
* 🧊 **Elastic Caching**: Multi-layer Redis caching (server-side + client-side headers)
* 🐳 **Cloud-Native**: One-command Docker Compose setup
* 🚀 **Production Recipes**: Optimized NGINX, Gunicorn, and Uvicorn configurations

### 🤖 Agentic AI Framework (The LegendStack Edge)

Built on top of the original foundation, we've added a professional agentic layer:

*   **LangGraph Orchestration**: Robust multi-agent workflows with state management and persistent memory.
*   **Enterprise RAG Pipeline**: High-performance document ingestion (PDF, MD, TXT) with **pgvector** or **Azure AI Search** backends.
*   **Deep Reranking**: Built-in support for **Cross-Encoders** and **Cohere** reranking to boost search precision.
*   **Enterprise Connectors**: Native, incremental indexers for **Jira**, **Confluence**, **SharePoint**, and **OneDrive**.
*   **Human-in-the-Loop (HITL)**: Flexible approval workflows for sensitive AI actions (Email, DB writes, etc.).
*   **Universal Auth System**: Unified credential management supporting API Keys, OAuth2, and **Azure Managed Identity**.
*   **Real-Time Interaction**: SSE (Server-Sent Events) and **WebSockets** for low-latency, token-by-token streaming.
*   **Reliability Patterns**: Industrial-strength **Circuit Breakers** and **Retries** for all external LLM and API calls.
*   **Observability**: Full **OpenTelemetry** integration (Datadog/Honeycomb) with per-tenant **Cost Tracking**.
*   **Prompt Governance**: Professional Prompt Registry with versioning, rollbacks, and A/B test support.

<details>
<summary><b>🚀 Quick Start: Use Azure OpenAI in 3 lines</b></summary>

```python
from app.core.integration_config import configure_integrations, get_azure_openai_client

configure_integrations()  # Auto-configures from .env
client = get_azure_openai_client()
response = await client.chat([{"role": "user", "content": "Hello!"}], deployment="gpt-4o")
```

</details>

<details>
<summary><b>🔍 Quick Start: RAG with Reranking</b></summary>

```python
from app.agents import RerankingService, CrossEncoderReranker

# Search → Rerank → Use top results
docs = await vector_store.search("How to deploy?", k=20)
reranker = RerankingService(CrossEncoderReranker())
top_docs = await reranker.rerank("How to deploy?", docs, top_k=5)
```

</details>

<details>
<summary><b>🛡️ Quick Start: Resilient LLM Calls</b></summary>

```python
from app.agents import ResilientClient

client = ResilientClient(name="openai")  # Retry + circuit breaker
result = await client.execute(call_llm, prompt)  # Auto-retries on failure
```

</details>

<details>
<summary><b>📊 Quick Start: Rate Limiting</b></summary>

```python
from app.agents import rate_limiter

await rate_limiter.enforce_limit("tenant-123", tokens_requested=1000)
# ... make LLM call ...
await rate_limiter.record_usage("tenant-123", tokens_used=500)
```

</details>

> 📚 Full agentic docs: [`docs/agents/README.md`](docs/agents/README.md)


## Why and When to use it

**Perfect if you want:**

* A pragmatic starter with auth, CRUD, jobs, caching and rate-limits
* **Enterprise-ready AI agents** with LangGraph, RAG, and Azure OpenAI
* **Sensible defaults** with the freedom to opt-out of modules
* **Docs over boilerplate** in README - depth lives in the site

> **Not a fit** if you need a monorepo microservices scaffold - [see the docs](https://benavlabs.github.io/FastAPI-boilerplate/user-guide/project-structure/) for pointers.

## TL;DR - Quickstart

Use the template on GitHub, create your repo, then:

```bash
git clone https://github.com/LegendStack/agentic-fastapi-template
cd agentic-fastapi-template
```

**Quick setup:** Run the interactive setup script to choose your deployment configuration:

```bash
./setup.py
```

Or directly specify the deployment type: `./setup.py local`, `./setup.py staging`, or `./setup.py production`.

The script copies the right files for your deployment scenario. Here's what each option sets up:

### Option 1: Local development with Uvicorn

Best for: **Development and testing**

**Copies:**

- `scripts/local_with_uvicorn/Dockerfile` → `Dockerfile`
- `scripts/local_with_uvicorn/docker-compose.yml` → `docker-compose.yml`
- `scripts/local_with_uvicorn/.env.example` → `src/.env`

Sets up Uvicorn with auto-reload enabled. The example environment values work fine for development.

**Manual setup:** `./setup.py local` or copy the files above manually.

### Option 2: Staging with Gunicorn managing Uvicorn workers

Best for: **Staging environments and load testing**

**Copies:**

- `scripts/gunicorn_managing_uvicorn_workers/Dockerfile` → `Dockerfile`
- `scripts/gunicorn_managing_uvicorn_workers/docker-compose.yml` → `docker-compose.yml`
- `scripts/gunicorn_managing_uvicorn_workers/.env.example` → `src/.env`

Sets up Gunicorn managing multiple Uvicorn workers for production-like performance testing.

> [!WARNING]
> Change `SECRET_KEY` and passwords in the `.env` file for staging environments.

**Manual setup:** `./setup.py staging` or copy the files above manually.

### Option 3: Production with NGINX

Best for: **Production deployments**

**Copies:**

- `scripts/production_with_nginx/Dockerfile` → `Dockerfile`
- `scripts/production_with_nginx/docker-compose.yml` → `docker-compose.yml`
- `scripts/production_with_nginx/.env.example` → `src/.env`

Sets up NGINX as reverse proxy with Gunicorn + Uvicorn workers for production.

> [!CAUTION]
> You MUST change `SECRET_KEY`, all passwords, and sensitive values in the `.env` file before deploying!

**Manual setup:** `./setup.py production` or copy the files above manually.

---

**Start your application:**

```bash
docker compose up
```

**Access your app:**
- **Local**: http://127.0.0.1:8000 (auto-reload enabled) → [API docs](http://127.0.0.1:8000/docs)
- **Staging**: http://127.0.0.1:8000 (production-like performance)
- **Production**: http://localhost (NGINX reverse proxy)

### Next steps

**Create your first admin user:**
```bash
docker compose run --rm create_superuser
```

**Run database migrations** (if you add models):
```bash
cd src && uv run alembic revision --autogenerate && uv run alembic upgrade head
```

**Test background jobs:**
```bash
curl -X POST 'http://127.0.0.1:8000/api/v1/tasks/task?message=hello'
```

**Or run locally without Docker:**
```bash
uv sync && uv run uvicorn src.app.main:app --reload
```

> Full setup (from-scratch, .env examples, PostgreSQL & Redis, gunicorn, nginx) lives in the [docs](https://LegendStack.github.io/agentic-fastapi-template/getting-started/installation/).

## Configuration (minimal)

Create `src/.env` and set **app**, **database**, **JWT**, and **environment** settings. See the [docs](https://LegendStack.github.io/agentic-fastapi-template/getting-started/configuration/) for a copy-pasteable example and production guidance.

[https://LegendStack.github.io/agentic-fastapi-template/getting-started/configuration/](https://LegendStack.github.io/agentic-fastapi-template/getting-started/configuration/)

* `ENVIRONMENT=local|staging|production` controls API docs exposure
* Set `ADMIN_*` to enable the first admin user

## Common tasks

```bash
# run locally with reload (without Docker)
uv sync && uv run uvicorn src.app.main:app --reload

# run Alembic migrations
cd src && uv run alembic revision --autogenerate && uv run alembic upgrade head

# enqueue a background job (example endpoint)
curl -X POST 'http://127.0.0.1:8000/api/v1/tasks/task?message=hello'
```

More examples (superuser creation, tiers, rate limits, admin usage) in the [docs](https://LegendStack.github.io/agentic-fastapi-template/getting-started/first-run/).

## Contributing

Read [contributing](CONTRIBUTING.md).

## Inspiration

This project was built from the ground up as an Enterprise AI foundation, drawing inspiration from best practices in several open-source projects:

- [`benavlabs/FastAPI-boilerplate`](https://github.com/benavlabs/FastAPI-boilerplate) - Core API structure
- [`Full Stack FastAPI and PostgreSQL`](https://github.com/tiangolo/full-stack-fastapi-postgresql) - Project layout
- [`FastAPI Microservices`](https://github.com/Kludex/fastapi-microservices) - Resilience patterns
- [`Async Web API with FastAPI + SQLAlchemy 2.0`](https://github.com/rhoboro/async-fastapi-sqlalchemy)
- [`FastAPI Rocket Boilerplate`](https://github.com/asacristani/fastapi-rocket-boilerplate/tree/main)

## License

[`MIT`](LICENSE.md)

## Contact

LegendStack – [legendstack.it](https://legendstack.it), [Discord](https://discord.gg/legendstack)

<hr>
<a href="https://legendstack.it">
  <img src="https://github.com/LegendStack/agentic-fastapi-template/raw/main/docs/assets/banner.png" alt="Powered by LegendStack - legendstack.it"/>
</a>
# Agentic-FastAPI-Template
