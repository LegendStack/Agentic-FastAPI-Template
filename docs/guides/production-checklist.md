# Production Checklist

> **Goal**: Ensure your LegendStack deployment is secure, observable, and scalable.

Use this checklist before going live. Each item is actionable with specific guidance.

---

## Quick Summary

| Category | Items | Status |
|----------|-------|--------|
| 🔐 Security | 8 items | ☐ |
| 📊 Observability | 5 items | ☐ |
| 🚀 Performance | 6 items | ☐ |
| 💰 Cost Management | 4 items | ☐ |
| 🔄 Operations | 5 items | ☐ |

---

## 🔐 Security Checklist

### 1. ☐ Rotate All Default Secrets

```bash
# Generate new SECRET_KEY
openssl rand -hex 32

# Generate new database password
openssl rand -base64 24
```

**Verify**: No secrets in `.env` match any in `.env.example`

### 2. ☐ Configure CORS Properly

**File**: `src/app/core/config.py`

```python
# ❌ WRONG (allows everything)
CORS_ORIGINS: list[str] = ["*"]

# ✅ RIGHT (explicit origins)
CORS_ORIGINS: list[str] = [
    "https://yourapp.com",
    "https://admin.yourapp.com",
]
```

### 3. ☐ Enable Rate Limiting

```env
# Recommended production settings
ENABLE_RATE_LIMITING=true
DEFAULT_RATE_LIMIT_TIER=standard

# Tier limits (requests per minute)
RATE_LIMIT_STANDARD=60
RATE_LIMIT_PREMIUM=300
RATE_LIMIT_ENTERPRISE=1000
```

### 4. ☐ Use Azure Key Vault for Secrets

Instead of `.env` files in production:

```python
# In src/app/core/config.py
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

credential = DefaultAzureCredential()
vault = SecretClient(
    vault_url="https://your-vault.vault.azure.net",
    credential=credential
)

# Fetch secrets
AZURE_OPENAI_API_KEY = vault.get_secret("azure-openai-key").value
```

### 5. ☐ Enable PII Protection

```env
ENABLE_PII_GUARD=true
ENABLE_MODERATION=true
```

**Verify**: Send test message with email/phone, confirm it's masked in logs.

### 6. ☐ Configure HTTPS

```yaml
# docker-compose.prod.yml
services:
  traefik:
    labels:
      - "traefik.http.routers.app.tls=true"
      - "traefik.http.routers.app.tls.certresolver=letsencrypt"
```

### 7. ☐ Set Secure Headers

**Already configured** in FastAPI middleware, but verify:

```python
# Check src/app/main.py has:
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["yourapp.com", "*.yourapp.com"]
)
```

### 8. ☐ Audit Authentication

- [ ] JWT tokens expire appropriately (`ACCESS_TOKEN_EXPIRE_MINUTES=30`)
- [ ] Refresh tokens are stored securely
- [ ] Failed login attempts are rate-limited
- [ ] Password requirements are enforced

---

## 📊 Observability Checklist

### 1. ☐ Enable OpenTelemetry Tracing

```env
ENABLE_TRACING=true
OTEL_EXPORTER_OTLP_ENDPOINT=https://your-collector:4318
OTEL_SERVICE_NAME=legendstack-prod
```

**Verify**: Traces appear in your observability platform (Jaeger, Honeycomb, etc.)

### 2. ☐ Configure Structured Logging

```env
LOG_LEVEL=INFO
LOG_FORMAT=json  # For production log aggregation
```

**Verify**: Logs are parseable by your log aggregator (ELK, Datadog, etc.)

### 3. ☐ Set Up Health Checks

Expose these endpoints to your load balancer:

| Endpoint | Purpose | Expected Response |
|----------|---------|-------------------|
| `/api/v1/health` | Liveness | 200 OK |
| `/api/v1/ready` | Readiness | 200 OK (checks DB, Redis) |

### 4. ☐ Configure Alerting

Set up alerts for:

- [ ] Error rate > 1%
- [ ] P95 latency > 5s
- [ ] Redis connection failures
- [ ] Database connection pool exhaustion
- [ ] LLM API errors

### 5. ☐ Enable Cost Tracking

```env
ENABLE_COST_TRACKING=true
```

**Verify**: Cost info appears in response metadata and logs.

---

## 🚀 Performance Checklist

### 1. ☐ Enable Semantic Caching

```env
ENABLE_SEMANTIC_CACHE=true
SEMANTIC_CACHE_THRESHOLD=0.9
SEMANTIC_CACHE_TTL_HOURS=24
```

**Verify**: Second identical query returns faster with `cache_hit: true`

### 2. ☐ Configure Connection Pools

```env
# Database
POSTGRES_POOL_SIZE=20
POSTGRES_MAX_OVERFLOW=10

# Redis
REDIS_POOL_SIZE=50
```

### 3. ☐ Set Appropriate Timeouts

```env
# LLM calls
LLM_REQUEST_TIMEOUT_SECONDS=60
LLM_MAX_RETRIES=3

# External APIs
HTTP_CLIENT_TIMEOUT_SECONDS=30
```

### 4. ☐ Configure Worker Concurrency

```yaml
# docker-compose.prod.yml
services:
  web:
    command: uvicorn src.app.main:app --workers 4 --host 0.0.0.0 --port 8000
```

Rule of thumb: `workers = 2 * CPU cores + 1`

### 5. ☐ Enable Response Compression

Already configured in FastAPI, but verify:

```python
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
```

### 6. ☐ Optimize Vector Search

```env
# Limit results to reduce latency
RAG_TOP_K=5
RAG_SIMILARITY_THRESHOLD=0.7

# Enable reranking for quality
ENABLE_RERANKING=true
RERANK_TOP_N=3
```

---

## 💰 Cost Management Checklist

### 1. ☐ Set Token Budgets

```env
# Per-request limits
MAX_INPUT_TOKENS=4000
MAX_OUTPUT_TOKENS=1000

# Per-tenant daily limits (optional)
TENANT_DAILY_TOKEN_LIMIT=100000
```

### 2. ☐ Configure Model Selection

Use cheaper models for simple tasks:

```python
# In your agent config
SIMPLE_QUERY_MODEL = "gpt-3.5-turbo"  # Cheaper
COMPLEX_QUERY_MODEL = "gpt-4o"  # When needed
```

### 3. ☐ Monitor Usage

Set up dashboards for:

- [ ] Daily token usage by tenant
- [ ] Cost per request (average, P50, P95)
- [ ] Cache hit rate (higher = lower cost)

### 4. ☐ Implement Quotas

```python
# Example: Check quota before LLM call
if tenant.daily_tokens_used > tenant.daily_token_limit:
    raise QuotaExceededError("Daily token limit reached")
```

---

## 🔄 Operations Checklist

### 1. ☐ Configure Backups

```bash
# PostgreSQL daily backup
pg_dump -h $POSTGRES_SERVER -U $POSTGRES_USER $POSTGRES_DB | gzip > backup.sql.gz

# Upload to blob storage
az storage blob upload --container backups --file backup.sql.gz
```

### 2. ☐ Set Up Database Migrations

```bash
# Run migrations on deploy
alembic upgrade head
```

**Verify**: Migration runs in CI/CD pipeline before app starts.

### 3. ☐ Configure Auto-Scaling

```yaml
# Kubernetes HPA example
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
spec:
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          averageUtilization: 70
```

### 4. ☐ Document Runbooks

Create runbooks for:

- [ ] How to roll back a deployment
- [ ] How to clear the Redis cache
- [ ] How to rotate API keys
- [ ] How to handle LLM API outage
- [ ] How to restore from backup

### 5. ☐ Test Disaster Recovery

- [ ] Simulate database failure → verify failover
- [ ] Simulate Redis failure → verify graceful degradation
- [ ] Simulate LLM API outage → verify fallback behavior

---

## Final Sign-Off

Before going live, verify:

| Check | Owner | Date |
|-------|-------|------|
| Security review complete | _______ | _____ |
| Load test passed | _______ | _____ |
| Monitoring configured | _______ | _____ |
| Runbooks documented | _______ | _____ |
| Backup/restore tested | _______ | _____ |

---

## Quick Commands

```bash
# Run security scan
bandit -r src/

# Check for outdated dependencies
pip list --outdated

# Test the health endpoints
curl https://yourapp.com/api/v1/health
curl https://yourapp.com/api/v1/ready

# View recent logs
docker logs --tail 100 legendstack-web-1

# Check Redis connection
redis-cli -h $REDIS_HOST ping
```

---

## Next Steps

- [Integration Guide](integration.md) - Connect real services
- [Customization Cookbook](cookbook.md) - Add your business logic
