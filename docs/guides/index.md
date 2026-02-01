# Developer Guides

Practical, actionable guides for going from demo to production.

---

## The Bridge Guides

These guides answer: *"I cloned this template. Now what?"*

| Guide | Purpose | Time |
|-------|---------|------|
| [Integration Guide](integration.md) | Connect YOUR Azure OpenAI, AI Search, Neo4j, Redis | 15 min |
| [Customization Cookbook](cookbook.md) | Add YOUR business logic, tools, and nodes | 30 min |
| [Production Checklist](production-checklist.md) | Security, scaling, and operations before you deploy | Review |

---

## Quick Start Path

```
┌─────────────────────────────────────────────────────────────────┐
│  1. Clone Template                                               │
│     git clone https://github.com/LegendStack/agentic-fastapi    │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. Run with Mocks                                               │
│     docker compose up                                            │
│     → Test at http://localhost:8000/docs                        │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. Follow Integration Guide                                     │
│     → Connect Azure OpenAI                                       │
│     → Connect Azure AI Search                                    │
│     → Connect Neo4j (optional)                                   │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. Customize with Cookbook                                      │
│     → Change system prompt                                       │
│     → Add your tools                                             │
│     → Integrate your APIs                                        │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. Production Checklist                                         │
│     → Security hardening                                         │
│     → Observability setup                                        │
│     → Performance tuning                                         │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  6. Deploy!                                                      │
│     → Azure Container Apps                                       │
│     → Kubernetes                                                 │
│     → Docker Compose on VM                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Time to Production

| Path | Estimated Time |
|------|----------------|
| Demo with mocks | 5 minutes |
| Connected to real services | 30 minutes |
| Customized for your use case | 2-4 hours |
| Production-ready | 1-2 days |

---

## See Also

- [Getting Started](../getting-started/index.md) - First-time setup
- [Tutorials](../tutorials/index.md) - Interactive learning
- [API Reference](../user-guide/index.md) - Detailed documentation
