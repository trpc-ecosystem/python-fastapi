# Tencent is pleased to support the open source community by making tRPC-FastAPI-Python available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# tRPC-FastAPI-Python is licensed under the Apache-2.0.
"""
TRPC FastAPI server process module.

The SDK calls :func:`start_fastapi` once per fastapi listen address, in every
process that serves that address:

- merge, single loop: the main thread, ``worker`` is the ``MergeWorker``;
- merge, threaded (``handle_num > 1`` or ``io_handle_type: separate``):
  serving thread 0 only, ``worker`` is a ``WorkerLoopView`` whose writes reach
  the real worker;
- separate: every rpc task (the I/O process never touches fastapi ports);
- peer: every peer worker.

The starter runs after the process's plugins are initialized and before its
event loop starts, so it builds the FastAPI app and binds the socket
synchronously, then hands both to uvicorn on a daemon thread and returns.
uvicorn runs its own event loop there and installs no signal handlers, so
SIGTERM stays with the SDK worker, which stops uvicorn through the exit
callbacks hung on ``worker``.

Object layout per serving process:

- one :class:`FastapiProcess`, stored as a process variable, mapping each
  uvicorn thread to the app it serves;
- one :class:`TrpcFastapiServerProcess` and one uvicorn thread per fastapi
  listen address.

Everything is created after fork, so serving processes never share these objects.
"""
import inspect
import os
import threading
from time import sleep
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import Dict
from typing import Optional
from typing import Set

import uvicorn
from fastapi import FastAPI
from fastapi import Request
from fastapi import Response

from trpc_sdk.abc import TrpcContext
from trpc_sdk.common import get_current_process_var
from trpc_sdk.common import set_current_process_var
from trpc_sdk.filters import get_server_filter
from trpc_sdk.http import HTTP_RSP_KEY
from trpc_sdk.http import pop_http_rsp_header
from trpc_sdk.log import logger

from ._codec import TrpcFastApiServerHttpCodec
from ._config import get_fastapi_server_config
from ._config import get_uvicorn_server_config
from ._constants import ALL_METHODS
from ._constants import CALLBACK_NAME
from ._constants import FASTAPI_PROCESS_VAR
from ._handler_adapter import trpc_http_handler
from ._handler_adapter import make_trpc_context
from ._routes import fastapi_routes
from ._utils import create_uvicorn_compatible_socket
from ._utils import get_http_code

# Filled at import time (or from a WORKER plugin) and inherited by every
# forked process; read when a process builds its apps.
_user_fastapi_app: Dict[str, FastAPI] = {}

# Extra seconds the post-drain join waits for uvicorn, on top of the drain the
# SDK already waited, so lifespan shutdown and task cancellation can finish.
_STOP_JOIN_GRACE_SECONDS = 2.0


def register_fastapi_app(service_name: str, app: FastAPI) -> None:
    """Register a FastAPI application for a specific service.

    Must happen before the service's app is built: at import time, or from a
    ``WORKER`` plugin, which the SDK initializes before it starts listeners.

    Args:
        service_name: Name of the TRPC service to associate with the FastAPI app
        app: FastAPI application instance to register
    """
    _user_fastapi_app[service_name] = app


class FastapiProcess:
    """Per-process registry of the FastAPI apps served by this process.

    Attributes:
        fastapi_app_map: uvicorn thread id -> the app that thread serves.
        callback_services: ``id()`` of every service that already has the
            callback filter, so a service with several fastapi addresses in
            one process gets it once.
    """

    def __init__(self) -> None:
        """Create an empty registry; filled as uvicorn threads start."""
        self.fastapi_app_map: Dict[int, FastAPI] = {}
        self.callback_services: Set[int] = set()

    @property
    def fastapi_app(self) -> FastAPI:
        """Get the FastAPI app served by the calling uvicorn thread.

        Returns:
            FastAPI: The app of the address the current request came in on.

        Raises:
            ValueError: If called from a thread that is not a uvicorn thread.
        """
        thread_id = threading.current_thread().ident
        app = self.fastapi_app_map.get(thread_id)
        if app is None:
            raise ValueError("get_fastapi_app() must be called from a fastapi request thread")
        return app


def get_or_create_fastapi_process() -> FastapiProcess:
    """Return this process's :class:`FastapiProcess`, creating it on first use.

    Returns:
        FastapiProcess: The instance stored on ``multiprocessing.current_process()``.
    """
    fastapi_process = get_current_process_var(FASTAPI_PROCESS_VAR)
    if fastapi_process is None:
        fastapi_process = FastapiProcess()
        set_current_process_var(FASTAPI_PROCESS_VAR, fastapi_process)
    return fastapi_process


class TrpcFastapiServerProcess:
    """One fastapi listen address served by one uvicorn thread.

    Reads ``worker.tran_opts[index]`` and ``worker.services[index]``, the
    tables every SDK worker fills in ``_bind_process_info``, and appends to
    ``worker.exit_callbacks`` / ``worker.post_drain_callbacks``, so it works
    the same under every worker, including a ``WorkerLoopView``.
    """

    def __init__(self, fastapi_process: FastapiProcess, worker: Any, index: int) -> None:
        """Capture the address's options and service; nothing is built yet.

        Args:
            fastapi_process: Registry of the serving process.
            worker: SDK worker serving the address.
            index: Position of the address in the worker's tables.
        """
        self.fastapi_process = fastapi_process
        self.worker = worker
        self.opts = worker.tran_opts[index]
        self.service = worker.services[index]
        self.fastapi_app: FastAPI = None
        self.server: Optional[uvicorn.Server] = None
        self._th: threading.Thread = None
        self._rpc_methods: Set[str] = set()

    @property
    def host(self) -> str:
        """Host part of the listen address."""
        return self.opts.address[0]

    def build_app(self) -> FastAPI:
        """Install the callback filter and build the FastAPI app with every route.

        Returns:
            FastAPI: The user-registered app for this service, or a new one.
        """
        filter_obj = get_server_filter(CALLBACK_NAME)
        service_key = id(self.service)
        if filter_obj and service_key not in self.fastapi_process.callback_services:
            self.service.opt.add_filter(filter_obj)
            self.fastapi_process.callback_services.add(service_key)

        service_name = self.service.opt.service_name
        app = _user_fastapi_app.get(service_name)
        if app is None:
            app = FastAPI(**get_fastapi_server_config())
        app.middleware("http")(self.filter_middleware)
        fastapi_routes(self.opts, app)
        self.register_rpc_routes(app)

        self.fastapi_app = app
        return app

    def register_rpc_routes(self, app: FastAPI) -> None:
        """Expose every unary RPC of the service as a route on ``app``.

        Stream methods are not exposed.

        Args:
            app: FastAPI application to register routes on
        """
        for method in self.opts.service.unary_handlers.keys():
            logger.debug(f"register rpc method method: {method}")
            self._rpc_methods.add(method)
            app.api_route(method, methods=ALL_METHODS, response_model=None)(trpc_http_handler(self.opts))

    get_rpc_method = register_rpc_routes

    def _construct_uvicorn_config(self, drain_seconds: float = 0.0) -> Dict[str, Any]:
        """Construct uvicorn configuration for this address.

        Args:
            drain_seconds: The worker's drain time, used as uvicorn's
                ``timeout_graceful_shutdown`` unless the YAML sets one.

        Returns:
            Dict: Uvicorn configuration dictionary
        """
        uvicorn_config = get_uvicorn_server_config() or {}
        uvicorn_config["host"] = self.host
        uvicorn_config["port"] = self.opts.port
        if ("timeout_graceful_shutdown" not in uvicorn_config
                and "timeout_graceful_shutdown" in inspect.signature(uvicorn.Config).parameters):
            uvicorn_config["timeout_graceful_shutdown"] = drain_seconds
        if self.opts.tls_key:
            uvicorn_config["ssl_keyfile"] = self.opts.tls_key
        if self.opts.tls_cert:
            uvicorn_config["ssl_certfile"] = self.opts.tls_cert
        return uvicorn_config

    def start(self) -> None:
        """Build the app, bind the socket, then serve it on a daemon thread.

        Called from the SDK starter before the event loop runs, so it must
        return quickly. App construction and the bind run on the caller's
        thread so a bad config or a busy port fails startup with a traceback
        instead of killing the process from inside the uvicorn thread.

        uvicorn joins the SDK shutdown: it stops accepting in the worker's
        exit callbacks, alongside the SDK listeners, and the worker waits
        for it after the drain.

        Raises:
            OSError: If the listen socket cannot be bound.
        """
        app = self.build_app()
        sock = create_uvicorn_compatible_socket(self.host, self.opts.port)
        drain_seconds = float(getattr(self.worker, "drain_seconds", 0.0) or 0.0)
        uvicorn_config_dict = self._construct_uvicorn_config(drain_seconds)
        logger.debug(f"uvicorn_config_dict: {uvicorn_config_dict}")
        self.server = uvicorn.Server(uvicorn.Config(app, **uvicorn_config_dict))

        self._th = threading.Thread(target=self._serve,
                                    args=(self.server, sock),
                                    name=f"trpc-fastapi-uvicorn-{self.opts.port}",
                                    daemon=True)
        self.worker.exit_callbacks.append(self.request_stop)
        self.worker.post_drain_callbacks.append(lambda: self.join(drain_seconds + _STOP_JOIN_GRACE_SECONDS))
        self._th.start()

    def request_stop(self) -> None:
        """Ask uvicorn to stop accepting and shut down; returns at once."""
        if self.server is not None:
            self.server.should_exit = True

    def join(self, timeout: float) -> None:
        """Wait for the uvicorn thread to finish its shutdown.

        Args:
            timeout: Seconds to wait at most; the thread is a daemon, so the
                process still exits if uvicorn overruns it.
        """
        thread = self._th
        if thread is None or not thread.is_alive():
            return
        thread.join(timeout)
        if thread.is_alive():
            logger.warning(f"fastapi uvicorn on port {self.opts.port} did not stop within {timeout:.1f}s; "
                           "exiting anyway")

    def _serve(self, server: uvicorn.Server, sock: Any) -> None:
        """uvicorn thread entry: publish this thread's app, then run uvicorn.

        uvicorn installs signal handlers only on the main thread, so running
        here leaves SIGTERM to the SDK worker.

        Args:
            server: uvicorn server wrapping this address's app.
            sock: Socket already bound by :meth:`start`.
        """
        self.fastapi_process.fastapi_app_map[threading.get_ident()] = self.fastapi_app
        service_name = self.service.opt.service_name
        try:
            logger.info(f"Starting fastapi service '{service_name}' on {self.host}:{self.opts.port}")
            server.run(sockets=[sock])
        except BaseException as e:  # pylint: disable=broad-except
            logger.error(f"Error in fastapi service '{service_name}': {e}")
            # Give the log a second to flush before the process goes down.
            sleep(1)
            os._exit(1)

    async def filter_middleware(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Middleware for processing TRPC context in FastAPI requests.

        Sets up TRPC context with request metadata and handles response headers.
        RPC routes are passed straight through: ``trpc_http_handler`` already
        runs the filter chain through ``Service.handle``.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware in the chain

        Returns:
            Response: HTTP response with TRPC headers
        """
        trpc_context = make_trpc_context(self.opts, request)
        logger.debug(f"path: {request.url.path}")
        if request.url.path in self._rpc_methods:
            response = await call_next(request)
        else:

            async def _http_func(ctx: TrpcContext, req: Request) -> Any:
                TrpcFastApiServerHttpCodec.decode_trpc_req_header(ctx, req)
                return await call_next(req)

            response = await self.opts.service.handle_http(trpc_context, _http_func)

        if not isinstance(response, Response):
            stored = trpc_context.pop_meta_data(HTTP_RSP_KEY)
            if isinstance(stored, Response):
                response = stored
            else:
                # The filter chain failed: handle_http returned the codec's
                # error body and left the status code on the context.
                body = response if isinstance(response, bytes) else b""
                response = Response(content=body, status_code=get_http_code(trpc_context))

        headers = pop_http_rsp_header(trpc_context)
        if headers:
            headers.update(response.headers)
            response.init_headers(headers)
        return response


def start_fastapi(worker: Any, index: int) -> None:
    """SDK protocol starter: serve the fastapi address at ``index``.

    Registered with ``trpc_sdk.server.register_protocol_handle`` for every
    fastapi protocol.

    Args:
        worker: SDK worker serving the address.
        index: Position of the address in the worker's tables.
    """
    fastapi_process = get_or_create_fastapi_process()
    TrpcFastapiServerProcess(fastapi_process, worker, index).start()
