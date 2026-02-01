# Customization Cookbook

> **Goal**: Add YOUR business logic to LegendStack in minutes, not hours.

This cookbook provides copy-paste recipes for common customizations. Each recipe is self-contained—mix and match as needed.

---

## Table of Contents

1. [Change the System Prompt](#1-change-the-system-prompt)
2. [Add a Custom Tool](#2-add-a-custom-tool)
3. [Create a Custom Node](#3-create-a-custom-node)
4. [Integrate Your API](#4-integrate-your-api)
5. [Add Custom Safety Rules](#5-add-custom-safety-rules)
6. [Modify the Agent Flow](#6-modify-the-agent-flow)
7. [Add a New Data Source](#7-add-a-new-data-source)
8. [Customize Entity Extraction](#8-customize-entity-extraction)

---

## 1. Change the System Prompt

**File**: `src/app/agents/demo/nodes/generate_node.py`

```python
# Find SYSTEM_PROMPT and modify:

SYSTEM_PROMPT = """You are a helpful AI assistant for {YOUR_COMPANY}.

Your responsibilities:
- Answer questions about {YOUR_PRODUCT}
- Help users troubleshoot issues
- Escalate complex problems to human support

Tone: Professional but friendly.
Never discuss: Competitor products, pricing negotiations.

Available Context:
{context}
"""
```

**That's it.** The prompt is injected into every LLM call automatically.

---

## 2. Add a Custom Tool

Tools let the agent take actions (search, calculate, call APIs).

**File**: Create `src/app/agents/tools/my_tool.py`

```python
from langchain_core.tools import tool

@tool
def search_inventory(product_name: str) -> str:
    """Search the inventory for a product by name.
    
    Args:
        product_name: The name of the product to search for.
    
    Returns:
        Inventory status and quantity.
    """
    # YOUR LOGIC HERE
    # Example: Call your inventory API
    inventory = call_your_inventory_api(product_name)
    
    return f"Product: {product_name}, Stock: {inventory['quantity']}, Location: {inventory['warehouse']}"


@tool  
def create_support_ticket(
    title: str,
    description: str,
    priority: str = "medium"
) -> str:
    """Create a support ticket in the ticketing system.
    
    Args:
        title: Brief title of the issue.
        description: Detailed description.
        priority: low, medium, or high.
    
    Returns:
        Ticket ID and confirmation.
    """
    # YOUR LOGIC HERE
    ticket_id = create_ticket_in_jira(title, description, priority)
    
    return f"Created ticket {ticket_id} with priority {priority}"
```

**Register the tool** in your agent:

```python
from app.agents.tools.my_tool import search_inventory, create_support_ticket

# In your agent's __init__:
self.tools = [search_inventory, create_support_ticket]
```

---

## 3. Create a Custom Node

Nodes are processing steps in the agent graph.

**File**: Create `src/app/agents/demo/nodes/my_node.py`

```python
"""
My Custom Node
==============
Does something specific to my business.
"""

import logging
from typing import Any

from ..config import DemoAgentConfig
from ..state import DemoAgentState

logger = logging.getLogger(__name__)


class MyCustomNode:
    """
    A custom processing node.
    
    Pattern:
    1. Read from state
    2. Process
    3. Return updates to state
    """
    
    def __init__(self, config: DemoAgentConfig):
        self.config = config
        # Initialize any dependencies here
    
    async def __call__(self, state: DemoAgentState) -> dict[str, Any]:
        """Process the state."""
        
        # Skip if cache hit (optional)
        if state.get("cache_hit", False):
            return {}
        
        # Read what you need
        user_input = state.get("sanitized_input", "")
        context = state.get("context", "")
        
        # YOUR LOGIC HERE
        result = await self.do_something(user_input, context)
        
        # Return updates (merged into state)
        return {
            "my_custom_field": result,
            "metadata": {
                **state.get("metadata", {}),
                "my_node_ran": True,
            },
        }
    
    async def do_something(self, user_input: str, context: str) -> str:
        """Your business logic here."""
        # Example: Call external service
        return "processed result"
```

**Add to the graph** in `demo_agent.py`:

```python
from .nodes.my_node import MyCustomNode

# In _init_nodes():
self.my_node = MyCustomNode(self.config)

# In _build_graph():
workflow.add_node("my_node", self.my_node)
workflow.add_edge("entity", "my_node")  # Insert after entity
workflow.add_edge("my_node", "generate")  # Continue to generate
```

---

## 4. Integrate Your API

**File**: Create `src/app/core/my_api_client.py`

```python
"""Client for My External API."""

import httpx
from app.core.config import settings

class MyAPIClient:
    """Async client for My External Service."""
    
    def __init__(self):
        self.base_url = settings.MY_API_BASE_URL
        self.api_key = settings.MY_API_KEY
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30.0,
        )
    
    async def get_data(self, query: str) -> dict:
        """Fetch data from the API."""
        response = await self._client.get(
            "/api/v1/data",
            params={"q": query}
        )
        response.raise_for_status()
        return response.json()
    
    async def post_action(self, payload: dict) -> dict:
        """Send an action to the API."""
        response = await self._client.post(
            "/api/v1/actions",
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()


# Singleton instance
_client: MyAPIClient | None = None

def get_my_api_client() -> MyAPIClient:
    """Get or create the API client."""
    global _client
    if _client is None:
        _client = MyAPIClient()
    return _client
```

**Add to settings** in `src/app/core/config.py`:

```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    MY_API_BASE_URL: str = "https://api.myservice.com"
    MY_API_KEY: str = ""
```

---

## 5. Add Custom Safety Rules

**File**: Modify `src/app/agents/demo/nodes/input_node.py`

```python
class InputNode:
    # Add YOUR blocked terms
    HARMFUL_KEYWORDS = [
        "hack", "exploit", "attack",  # Original
        "competitor_name",  # YOUR ADDITION
        "confidential_project",  # YOUR ADDITION
    ]
    
    # Add YOUR PII patterns
    PII_PATTERNS = {
        # Existing patterns...
        "employee_id": (r'\bEMP-\d{6}\b', "[EMPLOYEE_ID_MASKED]"),  # YOUR ADDITION
        "internal_code": (r'\b[A-Z]{3}-\d{4}\b', "[INTERNAL_CODE_MASKED]"),  # YOUR ADDITION
    }
```

**Or create a completely custom guard**:

```python
class CompanyPolicyGuard:
    """Enforce company-specific policies."""
    
    BLOCKED_TOPICS = ["competitor analysis", "salary information"]
    
    def check(self, text: str) -> tuple[bool, str | None]:
        """Check if text violates policies.
        
        Returns:
            (is_allowed, violation_reason)
        """
        text_lower = text.lower()
        
        for topic in self.BLOCKED_TOPICS:
            if topic in text_lower:
                return False, f"Discussion of '{topic}' is not permitted."
        
        return True, None
```

---

## 6. Modify the Agent Flow

**File**: `src/app/agents/demo/demo_agent.py`

The graph is defined in `_build_graph()`. Common modifications:

### Skip a Node

```python
# Make RAG optional based on query
workflow.add_conditional_edges(
    "input",
    self._should_use_rag,
    {
        "use_rag": "cache_check",
        "skip_rag": "generate",  # Go directly to generation
    }
)

def _should_use_rag(self, state) -> str:
    query = state.get("sanitized_input", "").lower()
    # Skip RAG for simple greetings
    if any(w in query for w in ["hello", "hi", "hey"]):
        return "skip_rag"
    return "use_rag"
```

### Add Parallel Nodes

```python
# Run RAG and Graph-RAG in parallel
workflow.add_node("rag", self.rag_node)
workflow.add_node("graph_rag", self.graph_rag_node)

# Both start after cache miss
workflow.add_edge("cache_check", "rag")
workflow.add_edge("cache_check", "graph_rag")

# Both merge into combine node
workflow.add_edge("rag", "combine")
workflow.add_edge("graph_rag", "combine")
```

---

## 7. Add a New Data Source

Create a connector for your data source:

**File**: Create `src/app/agents/connectors/my_connector.py`

```python
from app.agents.connectors.base import BaseConnector

class MyDatabaseConnector(BaseConnector):
    """Connector for My Custom Database."""
    
    name = "my_database"
    
    async def connect(self) -> None:
        """Establish connection."""
        # YOUR CONNECTION LOGIC
        pass
    
    async def fetch_documents(
        self,
        query: str,
        limit: int = 10
    ) -> list[dict]:
        """Fetch documents matching query."""
        # YOUR QUERY LOGIC
        results = await self.db.query(query, limit=limit)
        
        return [
            {
                "id": r["id"],
                "content": r["text"],
                "metadata": {"source": "my_database"},
            }
            for r in results
        ]
    
    async def disconnect(self) -> None:
        """Close connection."""
        await self.db.close()
```

**Register it**:

```python
from app.agents.connectors.registry import ConnectorRegistry
from app.agents.connectors.my_connector import MyDatabaseConnector

ConnectorRegistry.register(MyDatabaseConnector)
```

---

## 8. Customize Entity Extraction

**File**: Modify `src/app/agents/demo/nodes/entity_node.py`

```python
class DemoEntityNode:
    # Add YOUR entity patterns
    ENTITY_PATTERNS = {
        # Existing...
        "Person": [...],
        "Project": [...],
        
        # YOUR ADDITIONS
        "Product": [
            r"(?:product|item|sku)\s+([A-Z0-9-]+)",
            r"([A-Z]{2,3}-\d{4,6})",  # Product codes
        ],
        "Customer": [
            r"(?:customer|client|account)\s+([A-Z0-9]+)",
            r"(?:company|org)\s+([A-Za-z\s]+)",
        ],
    }
```

---

## Tips for Effective Customization

1. **Start with the Demo Agent** - Don't modify core files until you understand the flow

2. **Use feature flags** - Add toggles in `DemoAgentConfig` for your features

3. **Test incrementally** - Run `pytest tests/test_demo_agent.py` after each change

4. **Keep nodes focused** - One node, one responsibility

5. **Log liberally** - Use `logger.info()` to trace execution during development

---

## Next Steps

- [Production Checklist](production-checklist.md) - Security & scaling
- [Integration Guide](integration.md) - Connect real services
