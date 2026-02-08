from fastapi import APIRouter

from ...core.config import AuthProvider, settings
from .admin_metrics import router as admin_metrics_router
from .agents import router as agents_router
from .backlog import router as backlog_router
from .health import router as health_router
from .jira import router as jira_router
from .login import router as login_router
from .logout import router as logout_router
from .posts import router as posts_router
from .rate_limits import router as rate_limits_router
from .tasks import router as tasks_router
from .tiers import router as tiers_router
from .users import router as users_router

router = APIRouter(prefix="/v1")
router.include_router(health_router)

# Only include local auth endpoints if NOT using an external provider like Entra ID
if settings.AUTH_PROVIDER == AuthProvider.LOCAL:
    router.include_router(login_router)
    router.include_router(logout_router)

router.include_router(users_router)
router.include_router(posts_router)
router.include_router(tasks_router)
router.include_router(tiers_router)
router.include_router(rate_limits_router)
router.include_router(agents_router)
router.include_router(backlog_router)
router.include_router(jira_router)
router.include_router(admin_metrics_router)
