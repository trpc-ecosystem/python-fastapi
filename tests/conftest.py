# Tencent is pleased to support the open source community by making tRPC-FastAPI-Python available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# tRPC-FastAPI-Python is licensed under the Apache-2.0.
"""Shared fixtures for the trpc-fastapi tests.

Nothing here binds a port: services are real SDK ``Service`` objects, but the
listen socket and ``uvicorn.Server.run`` are mocked by the tests that start
an address.
"""
import multiprocessing
from types import SimpleNamespace
from typing import Any
from typing import Dict

import pytest
from google.protobuf import struct_pb2

from trpc_sdk.abc import Method
from trpc_sdk.abc import ServiceDesc
from trpc_sdk.config import TrpcConfig
from trpc_sdk.server import ServiceOption
from trpc_sdk.server import create_service

import trpc_fastapi  # noqa: F401  # registers the http_fastapi protocol
from trpc_fastapi import TRPC_FASTAPI_PROTOCOL
from trpc_fastapi import _callback
from trpc_fastapi import _routes
from trpc_fastapi import _trpc_server_process
from trpc_fastapi._constants import FASTAPI_PROCESS_VAR

SERVICE_NAME = "trpc.test.helloworld.FastApiGreeter"
ECHO_RPC = f"/{SERVICE_NAME}/Echo"


async def echo(ctx: Any, request: struct_pb2.Struct) -> struct_pb2.Struct:
    """Unary handler: return the request with ``echo`` set to true."""
    rsp = struct_pb2.Struct()
    rsp.update(dict(request))
    rsp["echo"] = True
    return rsp


def make_service(service_name: str = SERVICE_NAME, port: int = 18000, protocol: str = TRPC_FASTAPI_PROTOCOL):
    """Build a real SDK service served by trpc-fastapi, with one ``Echo`` RPC.

    Args:
        service_name: Service name; also the first path segment of the RPC.
        port: Listen port recorded on the transport options. Never bound.
        protocol: Service protocol.

    Returns:
        The ``Service``; its ``opt.transport_option`` is the address's options.
    """
    opt = ServiceOption()
    opt.set_protocol(protocol)
    opt.set_network("tcp")
    opt.set_address(("127.0.0.1", port))
    opt.set_timeout(5000)
    service = create_service(service_name, opt)
    method = Method(name=f"/{service_name}/Echo", req_cls=struct_pb2.Struct, rsp_cls=struct_pb2.Struct, impl_func=echo)
    service.register(ServiceDesc(service_name=f"/{service_name}", methods=[method]), False)
    return service


def make_worker(*services: Any, drain_seconds: float = 0.0) -> SimpleNamespace:
    """Fake SDK worker carrying only the attributes the starter reads and writes."""
    return SimpleNamespace(services=list(services),
                           tran_opts=[s.opt.transport_option for s in services],
                           exit_callbacks=[],
                           post_drain_callbacks=[],
                           drain_seconds=drain_seconds)


@pytest.fixture(autouse=True)
def isolate_plugin_state(monkeypatch):
    """Give every test empty route/app/callback registries and no process var."""
    monkeypatch.setattr(_routes, "_fastapi_routes", {})
    monkeypatch.setattr(_routes, "_static_file_routes", {})
    monkeypatch.setattr(_trpc_server_process, "_user_fastapi_app", {})
    monkeypatch.setattr(_callback, "_before_process_request_callback", [])
    monkeypatch.setattr(_callback, "_after_process_response_callback", [])
    process = multiprocessing.current_process()
    if hasattr(process, FASTAPI_PROCESS_VAR):
        delattr(process, FASTAPI_PROCESS_VAR)
    yield
    if hasattr(process, FASTAPI_PROCESS_VAR):
        delattr(process, FASTAPI_PROCESS_VAR)


@pytest.fixture
def load_config(tmp_path, monkeypatch):
    """Load a YAML string into ``TrpcConfig`` and restore the old state afterwards."""
    monkeypatch.setattr(TrpcConfig, "_config", TrpcConfig.config())
    monkeypatch.setattr(TrpcConfig, "_plugins_config", TrpcConfig.plugins_config())
    monkeypatch.setattr(TrpcConfig, "_config_parser", TrpcConfig.config_parser())

    def _load(content: str) -> Dict:
        path = tmp_path / "trpc_python.yaml"
        path.write_text(content, encoding="utf-8")
        return TrpcConfig.load(str(path))

    return _load
