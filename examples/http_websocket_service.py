# Tencent is pleased to support the open source community by making tRPC-FastAPI-Python available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# tRPC-FastAPI-Python is licensed under the Apache-2.0.
"""WebSocket chat example registered on the FastAPI app."""

from fastapi import WebSocket
from fastapi.responses import HTMLResponse
from starlette.websockets import WebSocketDisconnect

from trpc_sdk.log import logger
from trpc_fastapi import fastapi_register_websocket
from trpc_fastapi import fastapi_register_get

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id='messages'>
        </ul>
        <script>
            var ws = new WebSocket("ws://localhost:8000/ws");
            ws.onmessage = function(event) {
                var messages = document.getElementById('messages')
                var message = document.createElement('li')
                var content = document.createTextNode(event.data)
                message.appendChild(content)
                messages.appendChild(message)
            };
            function sendMessage(event) {
                var input = document.getElementById("messageText")
                ws.send(input.value)
                input.value = ''
                event.preventDefault()
            }
        </script>
    </body>
</html>
"""


@fastapi_register_get("/ws_index")
async def get():
    """Return the chat page.

    Returns:
        HTML page that opens a WebSocket to ``/ws``.
    """
    return HTMLResponse(html)

@fastapi_register_websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Echo text frames until the client disconnects.

    Args:
        websocket: Client connection. Accepted before the read loop.
    """
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Message text was: {data}")
    except WebSocketDisconnect as e:
        logger.debug(f"websocket disconnect: {e}")
    except Exception as e:  # pylint: disable=broad-except
        logger.error(f"websocket error: {e}, type: {type(e)}")
