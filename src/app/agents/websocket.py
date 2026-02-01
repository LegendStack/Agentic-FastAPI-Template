"""
WebSocket Streaming for Agents.
================================
Bidirectional real-time communication for agent interactions.

WebSocket provides lower latency than SSE and supports bidirectional
communication (user can send messages while receiving stream).
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class WSMessageType(str, Enum):
    """WebSocket message types."""

    # Client -> Server
    USER_MESSAGE = "user_message"
    CANCEL = "cancel"
    PING = "ping"

    # Server -> Client
    TOKEN = "token"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    COMPLETE = "complete"
    ERROR = "error"
    PONG = "pong"
    STATUS = "status"


class WSMessage(BaseModel):
    """WebSocket message format."""

    type: WSMessageType
    data: dict[str, Any] = {}
    timestamp: datetime = None

    def __init__(self, **data):
        if "timestamp" not in data or data["timestamp"] is None:
            data["timestamp"] = datetime.utcnow()
        super().__init__(**data)


@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection."""

    websocket: WebSocket
    thread_id: str
    user_id: str | None = None
    tenant_id: str | None = None
    connected_at: datetime = None

    def __post_init__(self):
        if self.connected_at is None:
            self.connected_at = datetime.utcnow()


class BaseWSHandler(ABC):
    """Abstract base for WebSocket handlers."""

    @abstractmethod
    async def on_connect(self, conn: ConnectionInfo) -> None:
        """Called when client connects."""
        pass

    @abstractmethod
    async def on_message(self, conn: ConnectionInfo, message: WSMessage) -> None:
        """Called when client sends a message."""
        pass

    @abstractmethod
    async def on_disconnect(self, conn: ConnectionInfo) -> None:
        """Called when client disconnects."""
        pass


class ConnectionManager:
    """
    Manages WebSocket connections.

    Tracks active connections and provides broadcast capabilities.
    """

    def __init__(self):
        self._connections: dict[str, ConnectionInfo] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self, websocket: WebSocket, thread_id: str, user_id: str | None = None, tenant_id: str | None = None
    ) -> ConnectionInfo:
        """Accept and register a new connection."""
        await websocket.accept()

        conn = ConnectionInfo(websocket=websocket, thread_id=thread_id, user_id=user_id, tenant_id=tenant_id)

        async with self._lock:
            self._connections[thread_id] = conn

        logger.info(f"WebSocket connected: {thread_id}")
        return conn

    async def disconnect(self, thread_id: str) -> None:
        """Remove a connection."""
        async with self._lock:
            if thread_id in self._connections:
                del self._connections[thread_id]
                logger.info(f"WebSocket disconnected: {thread_id}")

    async def send(self, thread_id: str, message: WSMessage) -> bool:
        """Send message to a specific connection."""
        async with self._lock:
            conn = self._connections.get(thread_id)

        if conn is None:
            return False

        try:
            await conn.websocket.send_json(message.model_dump(mode="json"))
            return True
        except Exception as e:
            logger.error(f"Failed to send to {thread_id}: {e}")
            return False

    async def send_token(self, thread_id: str, token: str) -> bool:
        """Send a single token to the client."""
        return await self.send(thread_id, WSMessage(type=WSMessageType.TOKEN, data={"token": token}))

    async def send_complete(self, thread_id: str, content: str) -> bool:
        """Send completion message."""
        return await self.send(thread_id, WSMessage(type=WSMessageType.COMPLETE, data={"content": content}))

    async def send_error(self, thread_id: str, error: str) -> bool:
        """Send error message."""
        return await self.send(thread_id, WSMessage(type=WSMessageType.ERROR, data={"error": error}))

    async def send_status(self, thread_id: str, status: str) -> bool:
        """Send status update."""
        return await self.send(thread_id, WSMessage(type=WSMessageType.STATUS, data={"status": status}))

    async def broadcast(self, message: WSMessage, tenant_id: str | None = None) -> int:
        """Broadcast message to all connections (optionally filtered by tenant)."""
        sent = 0
        async with self._lock:
            for thread_id, conn in self._connections.items():
                if tenant_id and conn.tenant_id != tenant_id:
                    continue
                try:
                    await conn.websocket.send_json(message.model_dump(mode="json"))
                    sent += 1
                except Exception:
                    pass
        return sent

    def get_connection(self, thread_id: str) -> ConnectionInfo | None:
        """Get connection info."""
        return self._connections.get(thread_id)

    def list_connections(self) -> list[str]:
        """List all connected thread IDs."""
        return list(self._connections.keys())


class AgentWSHandler(BaseWSHandler):
    """
    WebSocket handler for agent chat.

    Usage:
        manager = ConnectionManager()
        handler = AgentWSHandler(manager, agent_factory)

        @app.websocket("/ws/{thread_id}")
        async def websocket_endpoint(websocket, thread_id):
            await handler.handle(websocket, thread_id)
    """

    def __init__(self, manager: ConnectionManager, agent_factory: callable):
        self.manager = manager
        self.agent_factory = agent_factory
        self._cancel_flags: dict[str, bool] = {}

    async def on_connect(self, conn: ConnectionInfo) -> None:
        """Initialize agent for this connection."""
        self._cancel_flags[conn.thread_id] = False
        await self.manager.send_status(conn.thread_id, "connected")

    async def on_message(self, conn: ConnectionInfo, message: WSMessage) -> None:
        """Handle incoming messages."""
        if message.type == WSMessageType.PING:
            await self.manager.send(conn.thread_id, WSMessage(type=WSMessageType.PONG))
            return

        if message.type == WSMessageType.CANCEL:
            self._cancel_flags[conn.thread_id] = True
            await self.manager.send_status(conn.thread_id, "cancelled")
            return

        if message.type == WSMessageType.USER_MESSAGE:
            content = message.data.get("content", "")
            await self._process_message(conn, content)

    async def _process_message(self, conn: ConnectionInfo, content: str) -> None:
        """Process user message and stream response."""
        self._cancel_flags[conn.thread_id] = False

        try:
            await self.manager.send_status(conn.thread_id, "processing")

            # Get agent
            agent = self.agent_factory(conn.thread_id)

            # Stream tokens
            full_response = ""
            async for token in agent.stream(content, {"thread_id": conn.thread_id}):
                # Check for cancellation
                if self._cancel_flags.get(conn.thread_id):
                    break

                if isinstance(token, str):
                    full_response += token
                    await self.manager.send_token(conn.thread_id, token)
                elif isinstance(token, dict):
                    # Tool call or other structured output
                    await self.manager.send(conn.thread_id, WSMessage(type=WSMessageType.TOOL_CALL, data=token))

            await self.manager.send_complete(conn.thread_id, full_response)

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await self.manager.send_error(conn.thread_id, str(e))

    async def on_disconnect(self, conn: ConnectionInfo) -> None:
        """Cleanup when connection closes."""
        if conn.thread_id in self._cancel_flags:
            del self._cancel_flags[conn.thread_id]

    async def handle(
        self, websocket: WebSocket, thread_id: str, user_id: str | None = None, tenant_id: str | None = None
    ) -> None:
        """Main handler for WebSocket endpoint."""
        conn = await self.manager.connect(websocket, thread_id, user_id, tenant_id)

        try:
            await self.on_connect(conn)

            while True:
                data = await websocket.receive_json()
                message = WSMessage(**data)
                await self.on_message(conn, message)

        except WebSocketDisconnect:
            logger.info(f"Client disconnected: {thread_id}")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            await self.on_disconnect(conn)
            await self.manager.disconnect(thread_id)


# Global connection manager
ws_manager = ConnectionManager()
