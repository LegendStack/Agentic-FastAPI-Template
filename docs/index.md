# Agentic FastAPI Template

<p align="center">
  <img src="assets/banner.png" alt="LegendStack Agentic FastAPI Template" width="80%" height="auto">
</p>

<p align="center">
  <i>Enterprise-ready Agentic AI template built on top of FastAPI and LangGraph.</i>
</p>

!!! warning "Documentation Status"
    This is our first version of the documentation. While functional, we acknowledge it's rough around the edges - there's a huge amount to document and we needed to start somewhere! We built this foundation (with a lot of AI assistance) so we can improve upon it. 
    
    Better documentation, examples, and guides are actively being developed. Contributions and feedback are greatly appreciated!

> [!NOTE]
> **Educational Purpose**: This project is intended for educational purposes and as a reference implementation for Agentic AI patterns. While built with enterprise practices in mind, please review all security configurations before deploying to production.

<p align="center">
  <a href="https://fastapi.tiangolo.com">
      <img src="https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi" alt="FastAPI">
  </a>
  <a href="https://docs.pydantic.dev/2.4/">
      <img src="https://img.shields.io/badge/Pydantic-E92063?logo=pydantic&logoColor=fff&style=for-the-badge" alt="Pydantic">
  </a>
  <a href="https://www.postgresql.org">
      <img src="https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL">
  </a>
  <a href="https://redis.io">
      <img src="https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=fff&style=for-the-badge" alt="Redis">
  </a>
  <a href="https://docs.docker.com/compose/">
      <img src="https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=fff&style=for-the-badge" alt="Docker">
  </a>
</p>

## What is Agentic FastAPI Template?

Agentic FastAPI Template is a comprehensive, enterprise-ready template for building scalable AI agents and async APIs. It combines advanced agent orchestration (LangGraph), RAG pipelines, enterprise integrations, and resilience patterns into a single production-ready foundation.

### 🌟 New in V3.0: The Agentic Framework
LegendStack has evolved into a complete framework with:
- **RAG Evaluation Engine**: Automated quality metrics using Ragas.
- **Safety Guardrails**: PII masking and hallucination detection.
- **Multi-Agent Orchestration**: Supervisor pattern for complex team workflows.
- **Graph-RAG**: Hybrid Vector + Neo4j relationship search.
- **LegendStack Studio**: Professional monitoring and HITL dashboard.
- **Developer CLI**: Scaffolding tool for rapid component development.

## Core Technologies

This boilerplate leverages cutting-edge Python technologies:

- **[LangGraph](https://github.com/langchain-ai/langgraph)** - Orchestrating multi-agent workflows with state and memory
- **[Azure OpenAI](https://azure.microsoft.com/en-us/products/ai-services/openai-service)** - Enterprise LLM service integration
- **[pgvector](https://github.com/pgvector/pgvector)** - Open-source vector similarity search for Postgres
- **[FastAPI](https://fastapi.tiangolo.com)** - Modern web framework for building APIs
- **[Pydantic V2](https://docs.pydantic.dev/2.4/)** - Ultra-fast data validation
- **[SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/)** - Advanced SQL toolkit and ORM

## Key Features

### Performance & Scalability
- Fully async architecture
- Pydantic V2 for ultra-fast data validation
- SQLAlchemy 2.0 with efficient query patterns
- Built-in caching with Redis
- Horizontal scaling with NGINX load balancing

### Security & Authentication
- JWT-based authentication with refresh tokens
- Cookie-based secure token storage
- Role-based access control with user tiers
- Rate limiting to prevent abuse
- Production-ready security configurations

### Developer Experience
- Comprehensive CRUD operations with [FastCRUD](https://github.com/igorbenav/fastcrud)
- Automatic API documentation
- Database migrations with Alembic
- Background task processing
- Extensive test coverage
- Docker Compose for easy development

### Production Ready
- Environment-based configuration
- Structured logging
- Health checks and monitoring
- NGINX reverse proxy setup
- Gunicorn with Uvicorn workers
- Database connection pooling

## Quick Start

Get up and running in less than 5 minutes:

```bash
# Clone the repository
git clone https://github.com/LegendStack/agentic-fastapi-template
cd agentic-fastapi-template

# Start with Docker Compose
docker compose up
```

That's it! Your API will be available at `http://localhost:8000/docs`

**[Continue with the Getting Started Guide →](getting-started/index.md)**

## Documentation Structure

### For New Users
- **[Getting Started](getting-started/index.md)** - Quick setup and first steps
- **[User Guide](user-guide/index.md)** - Comprehensive feature documentation

### For Developers
- **[Development](user-guide/development.md)** - Extending and customizing the boilerplate
- **[Testing](user-guide/testing.md)** - Testing strategies and best practices
- **[Production](user-guide/production.md)** - Production deployment guides

## Perfect For

- **REST APIs** - Build robust, scalable REST APIs
- **Microservices** - Create microservice architectures
- **SaaS Applications** - Multi-tenant applications with user tiers
- **Data APIs** - APIs for data processing and analytics

## Community & Support

- **[Discord Community](community.md)** - Join our Discord server to connect with other developers
- **[GitHub Issues](https://github.com/LegendStack/agentic-fastapi-template/issues)** - Bug reports and feature requests

<hr>
<a href="https://legendstack.it">
  <img src="https://github.com/LegendStack/agentic-fastapi-template/raw/main/docs/assets/banner.png" alt="Powered by LegendStack - legendstack.it"/>
</a>