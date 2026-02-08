"""
Graph Database Client.
=====================
Client for interaction with Neo4j Graph Database.
"""

import logging
from typing import Any, Dict, List

from neo4j import AsyncGraphDatabase, GraphDatabase

from .config import settings

logger = logging.getLogger(__name__)


class GraphDBClient:
    """
    Client for Neo4j operations.

    Supports both synchronous and asynchronous sessions.
    """

    def __init__(self):
        self._uri = settings.NEO4J_URI
        self._user = settings.NEO4J_USER
        self._password = settings.NEO4J_PASSWORD.get_secret_value()
        self._driver = None
        self._async_driver = None

    def get_driver(self):
        """Returns the synchronous driver."""
        if self._driver is None:
            self._driver = GraphDatabase.driver(self._uri, auth=(self._user, self._password))
        return self._driver

    def get_async_driver(self):
        """Returns the asynchronous driver."""
        if self._async_driver is None:
            self._async_driver = AsyncGraphDatabase.driver(self._uri, auth=(self._user, self._password))
        return self._async_driver

    async def close(self):
        """Closes all drivers."""
        if self._driver:
            self._driver.close()
        if self._async_driver:
            await self._async_driver.close()

    async def execute_query(self, query: str, parameters: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        """
        Executes a Cypher query asynchronously.
        """
        driver = self.get_async_driver()
        async with driver.session() as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records


def get_graph_client() -> GraphDBClient:
    """Dependency for obtaining the GraphDBClient."""
    return GraphDBClient()
