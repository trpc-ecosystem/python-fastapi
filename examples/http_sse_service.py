# Tencent is pleased to support the open source community by making tRPC-FastAPI-Python available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# tRPC-FastAPI-Python is licensed under the Apache-2.0.
"""Server-sent events example that pushes one message per second."""

import asyncio
from fastapi.responses import StreamingResponse

from trpc_fastapi import fastapi_register_get


async def event_generator():
    """Yield one SSE message per second.

    Returns:
        An async iterator of ``data: ...`` frames.
    """
    counter = 0
    while True:
        counter += 1
        # SSE frame: data: <message>\n\n
        yield f"data: 这是第 {counter} 条消息\n\n"
        await asyncio.sleep(1)


@fastapi_register_get('/sse')
async def sse_endpoint():
    """Serve the event stream at ``/sse``.

    Returns:
        A streaming response with media type ``text/event-stream``.
    """
    return StreamingResponse(event_generator(), media_type='text/event-stream')
