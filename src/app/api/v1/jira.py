import logging
import asyncio
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

from ...core.config import settings

router = APIRouter(prefix="/jira", tags=["jira"])

logger = logging.getLogger(__name__)

@router.get("/projects/search")
async def search_jira_projects(query: str = "") -> list[dict[str, Any]]:
    """
    Search for JIRA projects using the search API (scalable).
    """
    if not settings.JIRA_URL or not settings.JIRA_API_TOKEN:
        raise HTTPException(status_code=400, detail="JIRA configuration missing.")

    url = f"{settings.JIRA_URL}/rest/api/3/project/search"
    auth = (settings.JIRA_USERNAME, settings.JIRA_API_TOKEN.get_secret_value())
    
    params = {
        "query": query,
        "maxResults": 20,
        "action": "browse"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, auth=auth, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            projects = data.get("values", [])
            
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
            logger.error(f"Failed to search JIRA projects: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to search JIRA projects: {str(e)}")

@router.get("/search/universal")
async def universal_jira_search(query: str = "") -> list[dict[str, Any]]:
    """
    Universal search across projects and issues (Epics/Stories).
    Scales to thousands of records via JIRA's server-side JQL and search APIs.
    """
    if not settings.JIRA_URL or not settings.JIRA_API_TOKEN:
        raise HTTPException(status_code=400, detail="JIRA configuration missing.")

    if not query:
        return []

    auth = (settings.JIRA_USERNAME, settings.JIRA_API_TOKEN.get_secret_value())
    timeout = 10.0

    async def search_projects():
        url = f"{settings.JIRA_URL}/rest/api/3/project/search"
        params = {"query": query, "maxResults": 10, "action": "browse"}
        async with httpx.AsyncClient() as client:
            response = await client.get(url, auth=auth, params=params, timeout=timeout)
            if response.status_code == 200:
                vals = response.json().get("values", [])
                return [{"id": p.get("id"), "key": p.get("key"), "name": p.get("name"), "type": "project"} for p in vals]
            return []

    async def search_issues():
        url = f"{settings.JIRA_URL}/rest/api/3/search/jql"
        # Search Epics and Stories where summary ~ query OR key = query
        jql = f"(summary ~ '{query}*' OR text ~ '{query}*' OR key = '{query}') AND issuetype IN (Epic, Story, Task)"
        payload = {"jql": jql, "maxResults": 20, "fields": ["summary", "status", "issuetype", "labels"]}
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, auth=auth, timeout=timeout)
            if response.status_code == 200:
                issues = response.json().get("issues", [])
                return [
                    {
                        "id": i.get("id"), 
                        "key": i.get("key"), 
                        "summary": i.get("fields", {}).get("summary"), 
                        "status": i.get("fields", {}).get("status", {}).get("name"),
                        "issuetype": i.get("fields", {}).get("issuetype", {}).get("name"),
                        "labels": i.get("fields", {}).get("labels", []),
                        "type": i.get("fields", {}).get("issuetype", {}).get("name").lower()
                    } for i in issues
                ]
            return []

    # Run in parallel for performance
    project_task = asyncio.create_task(search_projects())
    issue_task = asyncio.create_task(search_issues())
    
    results = await asyncio.gather(project_task, issue_task)
    # Flatten and return
    return [item for sublist in results for item in sublist]

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

@router.get("/projects/{project_key}/epics")
async def get_jira_epics(project_key: str) -> list[dict[str, Any]]:
    """
    Fetch the list of Epics for a specific project.
    """
    if not settings.JIRA_URL or not settings.JIRA_API_TOKEN:
        raise HTTPException(status_code=400, detail="JIRA configuration missing.")

    # Using JQL to find Epics in the project
    # Note: GET /rest/api/2/search is deprecated (410 Gone).
    # We use POST /rest/api/3/search/jql as the replacement.
    url = f"{settings.JIRA_URL}/rest/api/3/search/jql"
    auth = (settings.JIRA_USERNAME, settings.JIRA_API_TOKEN.get_secret_value())
    
    jql = f"project = '{project_key}' AND issuetype = Epic"
    
    async with httpx.AsyncClient() as client:
        try:
            # Payload for POST search
            payload = {
                "jql": jql,
                "maxResults": 50,
                "fields": ["summary", "description", "status", "labels"]
            }
            
            response = await client.post(
                url, 
                json=payload,
                auth=auth, 
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            issues = data.get("issues", [])
            
            return [
                {
                    "id": i.get("id"),
                    "key": i.get("key"),
                    "summary": i.get("fields", {}).get("summary"),
                    "status": i.get("fields", {}).get("status", {}).get("name"),
                    "labels": i.get("fields", {}).get("labels", [])
                }
                for i in issues
            ]
        except Exception as e:
            logger.error(f"Failed to fetch JIRA epics for {project_key}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch JIRA epics: {str(e)}")


@router.get("/issues/{issue_key}")
async def get_jira_issue(issue_key: str) -> dict[str, Any]:
    """
    Fetch a specific JIRA issue's details (summary, description, status).
    """
    if not settings.JIRA_URL or not settings.JIRA_API_TOKEN:
        raise HTTPException(status_code=400, detail="JIRA configuration missing.")

    url = f"{settings.JIRA_URL}/rest/api/3/issue/{issue_key}"
    auth = (settings.JIRA_USERNAME, settings.JIRA_API_TOKEN.get_secret_value())
    
    async with httpx.AsyncClient() as client:
        try:
            # We only need specific fields
            response = await client.get(
                url, 
                params={"fields": "summary,description,status,issuetype,labels"}, 
                auth=auth, 
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            fields = data.get("fields", {})
            
            # Helper to extract text from ADF (Atlassian Document Format) if description is structured
            # Jira Cloud v3 uses ADF for description. v2 used raw markup. 
            # If it's ADF, it's a JSON object. If it's v2, it's a string.
            # For simplicity in this agent, we might need a parser or just dump it as text if it's complex.
            # However, for 'Decompose', we usually need the text content.
            # Let's inspect what we get. Typically langchain/agents handle string descriptions.
            # We will return the raw description and let the frontend or agent handle it, 
            # OR we try to convert simplified ADF to text.
            # For now, we return it as is, but we might want to check if it's a string or dict.
            
            description = fields.get("description")
            
            # Basic ADF text extraction (very naive)
            if isinstance(description, dict) and 'content' in description:
                try:
                    # Quick recursive text extractor for ADF
                    def extract_text(node):
                        if 'text' in node:
                            return node['text']
                        if 'content' in node:
                            return "".join(extract_text(child) for child in node['content'])
                        return ""
                        
                    description_text = extract_text(description)
                    # format with some newlines if needed, ADF is structured.
                    # This simple extractor joins everything. Ideally we need blocks.
                    
                    # Better ADF Text Extraction with blocks:
                    def extract_text_blocks(node):
                        text_parts = []
                        if 'text' in node:
                            text_parts.append(node['text'])
                        
                        if 'content' in node:
                            for child in node['content']:
                                child_text = extract_text_blocks(child)
                                if child_text:
                                    text_parts.append(child_text)
                                    
                        # add newlines for paragraphs/blocks
                        if node.get('type') == 'paragraph':
                            text_parts.append("\n\n")
                            
                        return "".join(text_parts)

                    description = extract_text_blocks(description).strip()
                except Exception:
                    # Fallback if extraction fails
                    description = str(fields.get("description"))

            return {
                "id": data.get("id"),
                "key": data.get("key"),
                "summary": fields.get("summary"),
                "description": description, # Now hopefully a string
                "status": fields.get("status", {}).get("name"),
                "issuetype": fields.get("issuetype", {}).get("name"),
                "labels": fields.get("labels", []),
                "url": f"{settings.JIRA_URL}/browse/{data.get('key')}"
            }
        except Exception as e:
            logger.error(f"Failed to fetch JIRA issue {issue_key}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch JIRA issue: {str(e)}")
            

@router.get("/projects/{project_key}/epics/{epic_key}/stories")
async def get_jira_epic_stories(project_key: str, epic_key: str) -> list[dict[str, Any]]:
    """
    Fetch stories/child issues for a specific Epic.
    """
    if not settings.JIRA_URL or not settings.JIRA_API_TOKEN:
        raise HTTPException(status_code=400, detail="JIRA configuration missing.")

    url = f"{settings.JIRA_URL}/rest/api/3/search/jql"
    auth = (settings.JIRA_USERNAME, settings.JIRA_API_TOKEN.get_secret_value())
    
    # JQL: Stories linked to this Epic
    # In Jira Cloud, this is usually 'parent = KEY' or 'Epic Link = KEY'
    jql = f"project = '{project_key}' AND (parent = '{epic_key}' OR 'Epic Link' = '{epic_key}')"
    
    async with httpx.AsyncClient() as client:
        try:
            payload = {
                "jql": jql,
                "maxResults": 100,
                "fields": ["summary", "status", "issuetype", "description", "labels"]
            }
            
            response = await client.post(url, json=payload, auth=auth, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            issues = data.get("issues", [])
            
            return [
                {
                    "id": i.get("id"),
                    "key": i.get("key"),
                    "summary": i.get("fields", {}).get("summary"),
                    "status": i.get("fields", {}).get("status", {}).get("name"),
                    "issuetype": i.get("fields", {}).get("issuetype", {}).get("name"),
                    "labels": i.get("fields", {}).get("labels", []),
                }
                for i in issues
            ]
        except Exception as e:
            logger.error(f"Failed to fetch JIRA stories for epic {epic_key}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch JIRA stories: {str(e)}")
