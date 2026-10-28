# Tencent is pleased to support the open source community by making tRPC-FastAPI-Python available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# tRPC-FastAPI-Python is licensed under the Apache-2.0.
"""WebSocket client that sends one message to the example server."""

import asyncio
import websockets


async def test_websocket():
    """Connect to the example server, send one message, and print the reply."""
    uri = "ws://127.0.0.1:8000/ws"
    async with websockets.connect(uri) as websocket:
        # Send a message.
        await websocket.send("你好，服务器！")
        print("消息已发送")

        # Receive the response.
        response = await websocket.recv()
        print(f"收到服务器消息: {response}")

        # Further send/receive calls are possible; this demo closes after one exchange.
        await websocket.close()

if __name__ == "__main__":
    asyncio.run(test_websocket())
