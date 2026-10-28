# Tencent is pleased to support the open source community by making tRPC-FastAPI-Python available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# tRPC-FastAPI-Python is licensed under the Apache-2.0.
"""End-to-end tests of a built app through FastAPI's TestClient.

The app comes from ``TrpcFastapiServerProcess.build_app`` on a real SDK
service, so requests go through the middleware, the SDK filter chain and,
for RPC routes, ``Service.handle``.
"""
import json

from fastapi import HTTPException
from fastapi import Request
from fastapi import WebSocket
from fastapi.testclient import TestClient

from trpc_sdk.http import HTTP_TRPC_HEADER

from trpc_fastapi import fastapi_register_get
from trpc_fastapi import fastapi_register_websocket
from trpc_fastapi import get_protocol_name
from trpc_fastapi import get_service_name
from trpc_fastapi import get_trpc_ctx
from trpc_fastapi import register_before_process_request_callback
from trpc_fastapi import TRPC_FASTAPI_PROTOCOL
from trpc_fastapi._trpc_server_process import FastapiProcess
from trpc_fastapi._trpc_server_process import TrpcFastapiServerProcess

from .conftest import ECHO_RPC
from .conftest import SERVICE_NAME
from .conftest import make_service
from .conftest import make_worker


def build_client() -> TestClient:
    """Build the app for one fastapi address and wrap it in a TestClient."""
    server_process = TrpcFastapiServerProcess(FastapiProcess(), make_worker(make_service()), 0)
    return TestClient(server_process.build_app())


def test_plain_route_sees_trpc_context():
    """Test a plain route runs with a tRPC context describing its service."""

    @fastapi_register_get("/hello")
    async def hello(request: Request):
        ctx = get_trpc_ctx()
        return {"service": get_service_name(ctx), "protocol": get_protocol_name(ctx)}

    response = build_client().get("/hello")

    assert response.status_code == 200
    assert response.json() == {"service": SERVICE_NAME, "protocol": TRPC_FASTAPI_PROTOCOL}


def test_before_callback_runs_for_plain_route():
    """Test the callback filter is installed on the service and sees the request."""
    seen = []
    register_before_process_request_callback(lambda ctx, req: seen.append(req.url.path))

    @fastapi_register_get("/hello")
    async def hello():
        return {}

    assert build_client().get("/hello").status_code == 200
    assert seen == ["/hello"]


def test_http_exception_still_maps_to_status():
    """Test FastAPI's own error handling is untouched by the middleware."""

    @fastapi_register_get("/missing")
    async def missing():
        raise HTTPException(status_code=404, detail="nope")

    response = build_client().get("/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "nope"}


def test_route_for_other_service_is_not_mounted():
    """Test service_name limits a route to that service's app."""

    @fastapi_register_get("/other", service_name="trpc.test.other.Service")
    async def other():
        return {}

    @fastapi_register_get("/mine", service_name=SERVICE_NAME)
    async def mine():
        return {}

    client = build_client()

    assert client.get("/other").status_code == 404
    assert client.get("/mine").status_code == 200


def test_rpc_route_runs_service_handler():
    """Test an RPC path is served by Service.handle with JSON serialization."""
    response = build_client().post(ECHO_RPC,
                                   content=json.dumps({"msg": "hi"}),
                                   headers={
                                       "Content-Type": "application/json",
                                       HTTP_TRPC_HEADER.trpc_request_id: "9",
                                   })

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert json.loads(response.content) == {"msg": "hi", "echo": True}


def test_rpc_route_unknown_method_reports_not_found():
    """Test a registered path whose handler is missing reports a tRPC error status."""
    service = make_service()
    server_process = TrpcFastapiServerProcess(FastapiProcess(), make_worker(service), 0)
    client = TestClient(server_process.build_app())
    service.unary_handlers.pop(ECHO_RPC)

    response = client.post(ECHO_RPC, content=b"{}", headers={"Content-Type": "application/json"})

    assert response.status_code == 404
    assert HTTP_TRPC_HEADER.trpc_error_message in response.headers


def test_websocket_route_round_trip():
    """Test a websocket route is wrapped with a tRPC context and stays usable."""

    @fastapi_register_websocket("/ws")
    async def ws(websocket: WebSocket):
        await websocket.accept()
        text = await websocket.receive_text()
        await websocket.send_text(f"{get_service_name(get_trpc_ctx())}:{text}")
        await websocket.close()

    with build_client().websocket_connect("/ws") as websocket:
        websocket.send_text("ping")
        assert websocket.receive_text() == f"{SERVICE_NAME}:ping"
