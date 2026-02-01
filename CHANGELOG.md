# Changelog

All notable changes to LegendStack Agentic FastAPI Template are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [5.0.0] - 2026-02-01

### Added
- **Demo Agent**: Comprehensive reference implementation showcasing all 17 framework features
  - 11 modular LangGraph nodes (Input, Cache, RAG, Graph-RAG, Memory, Entity, Generate, Reflector, HITL, Cost, Output)
  - 3 mock services for zero-dependency testing (MockLLM, MockVectorStore, MockGraphDB)
  - Configuration toggles for every feature
- **Interactive Tutorial**: 8-chapter Jupyter notebook (`notebooks/tutorial.ipynb`)
- **Streamlit Walkthrough**: Guided web app with live agent interaction (`studio/tutorial_app.py`)
- **Developer Bridge Guides**:
  - Integration Guide: Mock → Real services in 15 min
  - Customization Cookbook: 8 copy-paste recipes
  - Production Checklist: 28 items across 5 categories
- **OSS Polish**:
  - Redesigned README with value proposition and time-to-production metrics
  - GitHub issue templates (bug, feature, question)
  - Pull request template with review checklist

### Changed
- Unified documentation structure linking tutorials, guides, and reference docs
- Enhanced Getting Started with links to all learning resources

## [4.1.0] - 2026-01-30

### Added
- **Entity-Aware Memory**: Cross-thread relationship tracking using Neo4j knowledge graphs
- **Zero-Trust Security**: Multi-tenant BYOK encryption for RAG document segments
- **Encrypted Redis Cache**: Tenant-level encryption-at-rest for semantic cache

### Security
- Added per-tenant encryption key management
- Enhanced PII handling in entity extraction

## [4.0.0] - 2026-01-28

### Added
- **Semantic Caching**: Redis-backed similarity cache reducing LLM costs by 70%+
- **Self-Correction (Reflector)**: Autonomous quality improvement using eval loops
- **High-Fidelity Parsing**: Enterprise document ingestion via Unstructured.io

### Changed
- Upgraded EvalEngine with configurable quality thresholds
- Improved caching distance metrics for better cache hit rates

## [3.0.0] - 2026-01-25

### Added
- **LegendStack CLI**: Scaffolding tool to generate agents and connectors
- **LegendStack Studio**: Streamlit-based monitoring dashboard
- **Multi-Agent Orchestration**: Supervisor pattern with team-based workflows
- **Graph-RAG**: Neo4j integration for relationship-aware retrieval
- **Safety Guardrails**: PIIGuard and ContentModerator for input protection
- **RAG Evaluation**: EvalEngine with automatic test case generation
- **Connector SDK**: Pluggable architecture for enterprise data sources

### Changed
- Restructured agents module for better modularity
- Enhanced documentation with comprehensive agent development guide

## [2.1.0] - 2026-01-20

### Added
- **Microsoft Entra ID Integration**: Native Azure AD SSO support
- **Multi-Provider Auth**: Configurable auth (local JWT, Entra ID)
- **JIT User Provisioning**: Auto-create users on first SSO login
- **Tiered Rate Limiting**: Free/Standard/Premium service levels
- **OAuth2 Client Credentials**: For service-to-service auth

### Changed
- Unified authentication middleware architecture
- Enhanced token validation with JWKS caching

## [2.0.0] - 2026-01-15

### Added
- **LangGraph Orchestration**: Robust multi-agent workflows
- **Enterprise RAG Pipeline**: Document ingestion with pgvector
- **Reranking**: Cross-Encoder and Cohere support
- **Enterprise Connectors**: Jira, Confluence, SharePoint, OneDrive
- **Human-in-the-Loop**: Approval workflows for sensitive actions
- **Resilience Patterns**: Circuit breakers and retries
- **OpenTelemetry**: Full observability integration
- **Cost Tracking**: Per-tenant token usage monitoring
- **Prompt Registry**: Versioned prompt management

### Changed
- Upgraded to FastAPI 0.115+ with full Pydantic V2 support
- Migrated to SQLAlchemy 2.0 async patterns

## [1.0.0] - 2026-01-01

### Added
- Initial release based on FastAPI boilerplate
- JWT authentication with access/refresh tokens
- PostgreSQL with async SQLAlchemy
- Redis caching and background jobs (ARQ)
- Rate limiting middleware
- Docker Compose setup (local/staging/production)
- FastCRUD for automated endpoints
- CRUDAdmin panel

---

## Version History Summary

| Version | Codename | Highlights |
|---------|----------|------------|
| 5.0 | Developer Experience | Demo Agent, Tutorials, Guides |
| 4.1 | Enterprise Hardening | Entity Memory, Zero-Trust Security |
| 4.0 | Production Stability | Semantic Cache, Reflector, Parsing |
| 3.0 | Intelligence & Data | CLI, Studio, Graph-RAG, Safety |
| 2.1 | Auth Evolution | Entra ID, Multi-Provider |
| 2.0 | Agentic Foundation | LangGraph, RAG, Connectors |
| 1.0 | Initial Release | Core platform |
