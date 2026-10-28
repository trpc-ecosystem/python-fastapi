# Tencent is pleased to support the open source community by making tRPC-FastAPI-Python available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# tRPC-FastAPI-Python is licensed under the Apache-2.0.
"""Tests for protocol registration, the SDK starter and the per-process model."""
import asyncio
import inspect
import threading
from types import SimpleNamespace
from unittest import mock

import pytest
import uvicorn
from fastapi import FastAPI
from starlette.responses import Response

from trpc_sdk.abc import PluginInitPos
from trpc_sdk.abc import PluginType
from trpc_sdk.http import LOCAL_ADDR
from trpc_sdk.http import ServerHttpParser
from trpc_sdk.plugin import DEFAULT_PLUGIN_MANAGER
from trpc_sdk.runtime._threadmodel._worker_view import WorkerLoopView
from trpc_sdk.transport import UserProtocolTransport
from trpc_sdk.transport import get_protocol_handle

from trpc_fastapi import FastapiServerTransport
from trpc_fastapi import FastapiServerTransportFactory
from trpc_fastapi import TRPC_FASTAPI_PROTOCOL
from trpc_fastapi import get_fastapi_app
from trpc_fastapi import register_fastapi_app
from trpc_fastapi import register_protocol_to_fastapi
from trpc_fastapi import _trpc_server_process
from trpc_fastapi._codec import TrpcFastApiServerHttpCodec
from trpc_fastapi._registry import TrpcFastapiPlugin
from trpc_fastapi._trpc_server_process import FastapiProcess
from trpc_fastapi._trpc_server_process import TrpcFastapiServerProcess
from trpc_fastapi._trpc_server_process import get_or_create_fastapi_process
from trpc_fastapi._trpc_server_process import start_fastapi
from trpc_fastapi.version import __version__

from .conftest import make_service
from .conftest import make_worker


def _assert_fastapi_protocol(protocol):
    """Check that ``protocol`` is wired to the fastapi codec, the HTTP parser and the starter."""
    expected = {
        PluginType.SERVER_CODEC: TrpcFastApiServerHttpCodec,
        PluginType.SERVER_PARSER: ServerHttpParser,
    }
    for plugin_type, cls in expected.items():
        spec = DEFAULT_PLUGIN_MANAGER.get_plugin_spec(plugin_type, protocol)
        assert spec.cls is cls
        assert spec.init_pos == PluginInitPos.WORKER
    assert get_protocol_handle(protocol) is start_fastapi


def test_import_registers_default_protocol():
    """Test importing the package wires the default protocol into the SDK."""
    _assert_fastapi_protocol(TRPC_FASTAPI_PROTOCOL)


@pytest.mark.parametrize("protocol", [TRPC_FASTAPI_PROTOCOL, "a2a_test_protocol"])
def test_register_protocol_to_fastapi_registers_plugins_and_handle(protocol):
    """Test a protocol gets codec, parser and the starter at once."""
    register_protocol_to_fastapi(protocol)

    _assert_fastapi_protocol(protocol)


def test_version_plugin_marked_for_report():
    """Test the plugin is reported with the package version."""
    spec = DEFAULT_PLUGIN_MANAGER.get_plugin_spec(PluginType.USER_DEFINED, TRPC_FASTAPI_PROTOCOL)
    assert spec.cls is TrpcFastapiPlugin
    assert spec.report
    assert spec.version == __version__


def test_transport_is_user_protocol_transport_bound_to_starter():
    """Test the exported transport and factory build a UserProtocolTransport for start_fastapi."""
    transport = FastapiServerTransportFactory().create()

    assert isinstance(transport, FastapiServerTransport)
    assert isinstance(transport, UserProtocolTransport)
    assert transport.starter is start_fastapi


def test_no_server_transport_plugin_registered():
    """Test the SDK's UserProtocolTransport is left to serve the protocol."""
    assert DEFAULT_PLUGIN_MANAGER.get_plugin_spec(PluginType.SERVER_TRANSPORT, TRPC_FASTAPI_PROTOCOL) is None


def test_get_or_create_fastapi_process_is_idempotent():
    """Test one FastapiProcess per process."""
    first = get_or_create_fastapi_process()
    assert isinstance(first, FastapiProcess)
    assert get_or_create_fastapi_process() is first


def test_get_fastapi_app_outside_fastapi_raises_value_error():
    """Test get_fastapi_app reports misuse with ValueError, with or without a process."""
    with pytest.raises(ValueError):
        get_fastapi_app()
    get_or_create_fastapi_process()
    with pytest.raises(ValueError):
        get_fastapi_app()


def test_start_fastapi_returns_and_serves_on_thread():
    """Test the starter binds synchronously, then runs uvicorn on a daemon thread."""
    service = make_service()
    worker = make_worker(service)
    sock = object()
    served = threading.Event()
    serving_thread = {}

    def fake_run(server, sockets=None):
        serving_thread["ident"] = threading.get_ident()
        serving_thread["sockets"] = sockets
        served.set()

    with mock.patch.object(_trpc_server_process, "create_uvicorn_compatible_socket", return_value=sock) as create, \
            mock.patch("uvicorn.Server.run", autospec=True, side_effect=fake_run):
        start_fastapi(worker, 0)
        create.assert_called_once_with("127.0.0.1", 18000)
        assert served.wait(5)

    assert serving_thread["ident"] != threading.get_ident()
    assert serving_thread["sockets"] == [sock]
    app_map = get_or_create_fastapi_process().fastapi_app_map
    assert isinstance(app_map[serving_thread["ident"]], FastAPI)


def test_start_raises_when_bind_fails():
    """Test a busy port fails the starter itself instead of the uvicorn thread."""
    fastapi_process = FastapiProcess()
    server_process = TrpcFastapiServerProcess(fastapi_process, make_worker(make_service()), 0)

    with mock.patch.object(_trpc_server_process, "create_uvicorn_compatible_socket",
                           side_effect=OSError("address in use")), \
            mock.patch("uvicorn.Server.run") as run, \
            mock.patch.object(threading.Thread, "start") as thread_start:
        with pytest.raises(OSError):
            server_process.start()

    run.assert_not_called()
    thread_start.assert_not_called()


def test_callback_filter_added_once_per_service():
    """Test two addresses of one service in one process add the filter once."""
    service = make_service()
    fastapi_process = FastapiProcess()
    worker = make_worker(service, service)

    with mock.patch.object(service.opt, "add_filter", wraps=service.opt.add_filter) as add_filter:
        TrpcFastapiServerProcess(fastapi_process, worker, 0).build_app()
        TrpcFastapiServerProcess(fastapi_process, worker, 1).build_app()

    assert add_filter.call_count == 1


def test_registered_app_is_used_without_building_another():
    """Test a user-registered app is reused and no default FastAPI is constructed."""
    service = make_service()
    user_app = FastAPI()
    register_fastapi_app(service.opt.service_name, user_app)

    with mock.patch.object(_trpc_server_process, "FastAPI") as fastapi_cls:
        app = TrpcFastapiServerProcess(FastapiProcess(), make_worker(service), 0).build_app()

    assert app is user_app
    fastapi_cls.assert_not_called()


def test_build_app_registers_unary_rpc_routes():
    """Test every unary RPC becomes a route on the app."""
    service = make_service()
    server_process = TrpcFastapiServerProcess(FastapiProcess(), make_worker(service), 0)

    app = server_process.build_app()

    paths = {route.path for route in app.routes}
    assert set(service.unary_handlers) <= paths
    assert server_process.get_rpc_method == server_process.register_rpc_routes


@pytest.mark.asyncio
async def test_filter_middleware_without_stored_response_does_not_raise():
    """Test a non-Response result with no HTTP_RSP_KEY yields a Response, not KeyError."""
    server_process = TrpcFastapiServerProcess(FastapiProcess(), make_worker(make_service()), 0)
    fake_service = SimpleNamespace(opt=SimpleNamespace(protocol=TRPC_FASTAPI_PROTOCOL),
                                   handle_http=mock.AsyncMock(return_value=b""))
    server_process.opts = SimpleNamespace(idle_timeout=0,
                                          address=("127.0.0.1", 18000),
                                          port=18000,
                                          service_name="svc",
                                          service=fake_service)
    request = SimpleNamespace(url=SimpleNamespace(path="/plain"), client=SimpleNamespace(host="10.0.0.1"))

    response = await server_process.filter_middleware(request, mock.AsyncMock())

    assert isinstance(response, Response)
    assert response.status_code == 200
    fake_service.handle_http.assert_awaited_once()
    ctx = fake_service.handle_http.await_args.args[0]
    assert ctx.get_meta_data(LOCAL_ADDR) == "127.0.0.1:18000"


def _start_with_blocking_run(worker):
    """Run the starter with a fake uvicorn that blocks until ``should_exit``."""
    started = threading.Event()

    def fake_run(server, sockets=None):
        started.set()
        while not server.should_exit:
            threading.Event().wait(0.01)

    with mock.patch.object(_trpc_server_process, "create_uvicorn_compatible_socket", return_value=object()), \
            mock.patch("uvicorn.Server.run", autospec=True, side_effect=fake_run):
        start_fastapi(worker, 0)
        assert started.wait(5)


def test_exit_and_post_drain_callbacks_stop_uvicorn():
    """Test the worker's exit callback stops uvicorn and the post-drain callback joins it."""
    worker = make_worker(make_service(), drain_seconds=0.5)

    _start_with_blocking_run(worker)

    assert len(worker.exit_callbacks) == 1
    assert len(worker.post_drain_callbacks) == 1
    thread = next(t for t in threading.enumerate() if t.name == "trpc-fastapi-uvicorn-18000")
    worker.exit_callbacks[0]()
    worker.post_drain_callbacks[0]()
    assert not thread.is_alive()


def test_callbacks_reach_real_worker_through_loop_view():
    """Test a threaded merge worker's WorkerLoopView forwards the callbacks to the real worker."""
    worker = make_worker(make_service())
    loop = asyncio.new_event_loop()
    try:
        _start_with_blocking_run(WorkerLoopView(worker, loop))
    finally:
        loop.close()

    assert len(worker.exit_callbacks) == 1
    assert len(worker.post_drain_callbacks) == 1
    worker.exit_callbacks[0]()
    worker.post_drain_callbacks[0]()


def test_drain_seconds_becomes_graceful_shutdown_timeout():
    """Test uvicorn gets the worker's drain time unless the YAML sets its own."""
    server_process = TrpcFastapiServerProcess(FastapiProcess(), make_worker(make_service()), 0)
    supported = "timeout_graceful_shutdown" in inspect.signature(uvicorn.Config).parameters

    config = server_process._construct_uvicorn_config(3.0)
    assert config["host"] == "127.0.0.1"
    assert config["port"] == 18000
    assert config.get("timeout_graceful_shutdown") == (3.0 if supported else None)

    with mock.patch.object(_trpc_server_process, "get_uvicorn_server_config",
                           return_value={"timeout_graceful_shutdown": 7}):
        assert server_process._construct_uvicorn_config(3.0)["timeout_graceful_shutdown"] == 7
