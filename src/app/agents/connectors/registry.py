"""
Connector Registry.
==================
Central registry for data ingestion connectors.
"""

import logging
from typing import Dict, Type

from ..base import BaseIndexer

logger = logging.getLogger(__name__)


class ConnectorRegistry:
    """
    Registry for managing and obtaining ingestion connectors.
    """

    _connectors: Dict[str, Type[BaseIndexer]] = {}

    @classmethod
    def register(cls, name: str):
        """Decorator for registering a connector."""

        def wrapper(connector_cls: Type[BaseIndexer]):
            cls._connectors[name] = connector_cls
            logger.info(f"Registered connector: {name}")
            return connector_cls

        return wrapper

    @classmethod
    def get_connector(cls, name: str, **kwargs) -> BaseIndexer:
        """Obtains an instance of a registered connector."""
        if name not in cls._connectors:
            raise ValueError(f"Connector '{name}' not found in registry.")

        connector_cls = cls._connectors[name]
        return connector_cls(**kwargs)

    @classmethod
    def list_connectors(cls) -> Dict[str, str]:
        """Lists all registered connectors and their docstrings."""
        return {name: cls._connectors[name].__doc__ or "No description" for name in cls._connectors}
