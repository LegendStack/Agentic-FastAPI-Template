import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

from ...core.config import settings

router = APIRouter(prefix="/jira", tags=["jira"])

logger = logging.getLogger(__name__)

@router.get("/projects")
async def get_jira_projects() -> list[dict[str, Any]]:
    """
    Fetch the list of projects from JIRA.
    """
    if not settings.JIRA_URL or not settings.JIRA_API_TOKEN:
        raise HTTPException(status_code=400, detail="JIRA configuration missing.")

    url = f"{settings.JIRA_URL}/rest/api/2/project"
    auth = (settings.JIRA_USERNAME, settings.JIRA_API_TOKEN.get_secret_value())

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, auth=auth, timeout=10.0)
            response.raise_for_status()
            projects = response.json()
            
            # Map JIRA project format to UI format
            return [
                {
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "key": p.get("key"),
                    "avatar": p.get("avatarUrls", {}).get("48x48")
                }
                for p in projects
            ]
        except Exception as e:
            logger.error(f"Failed to fetch JIRA projects: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch JIRA projects: {str(e)}")
