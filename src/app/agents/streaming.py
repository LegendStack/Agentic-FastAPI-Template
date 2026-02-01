"""
SSE (Server-Sent Events) streaming utilities for real-time agent responses.
Provides token-by-token streaming for responsive chat UX.
"""

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import Request
from fastapi.responses import StreamingResponse


async def sse_stream(generator: AsyncGenerator[dict[str, Any], None], request: Request) -> StreamingResponse:
    """
    Wraps an async generator to produce SSE-formatted responses.

    Usage:
        async def my_generator():
            yield {"type": "token", "content": "Hello"}
            yield {"type": "token", "content": " World"}
            yield {"type": "done", "content": ""}

        return await sse_stream(my_generator(), request)
    """

    async def event_generator():
        try:
            async for event in generator:
                if await request.is_disconnected():
                    break
                data = json.dumps(event)
                yield f"data: {data}\n\n"
            yield "data: [DONE]\n\n"
        except asyncio.CancelledError:
            yield "data: [CANCELLED]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


class StreamingChatResponse:
    """Helper class for building streaming chat responses."""

    def __init__(self):
        self.tokens = []
        self.metadata = {}

    async def stream_tokens(self, token_generator: AsyncGenerator[str, None]) -> AsyncGenerator[dict[str, Any], None]:
        """
        Converts a token generator to SSE events.

        Args:
            token_generator: Async generator yielding string tokens

        Yields:
            SSE event dictionaries with type and content
        """
        async for token in token_generator:
            self.tokens.append(token)
            yield {"type": "token", "content": token}

        # Final event with complete response
        yield {"type": "done", "content": "".join(self.tokens), "metadata": self.metadata}
