# Tencent is pleased to support the open source community by making tRPC-FastAPI-Python available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# tRPC-FastAPI-Python is licensed under the Apache-2.0.
"""Routes module for TRPC FastAPI Plugin.
This module provides route registration and conversion functionality to integrate
TRPC framework routes with FastAPI application, including custom HTTP handlers,
static file serving, and route parameter handling.
"""
import os
from functools import partial
from typing import Any, Callable, Dict, List

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from trpc_sdk.abc import BaseServerTransportOption
from trpc_sdk.http import HttpRoute
from trpc_sdk.log import logger

from ._constants import ANY_METHOD
from ._constants import ALL_METHODS
from ._constants import GET_METHOD
from ._constants import DELETE_METHOD
from ._constants import PATCH_METHOD
from ._constants import OPTIONS_METHOD
from ._constants import HEAD_METHOD
from ._constants import TRACE_METHOD
from ._constants import POST_METHOD
from ._constants import PUT_METHOD
from ._constants import WEB_SOCKET_METHOD
from ._handler_adapter import fastapi_http_websocket_handler

_fastapi_routes: Dict[str, HttpRoute] = {}
_static_file_routes: Dict[str, str] = {}


def fastapi_register_static(prefix: str, path_to_folder: str) -> None:
    """Register static file routes with the FastAPI application.

    This function mounts static file directories to the FastAPI application
    using the routes defined in _static_file_routes.

    Args:
        prefix: HTTP path prefix for the static files
        path_to_folder: Local directory path containing static files
    """
    global _static_file_routes
    _static_file_routes[prefix] = path_to_folder


def fastapi_route(path: str,
                  method: List[str],
                  service_name: str = None,
                  route_params: Dict = None) -> Callable[..., Any]:
    """Register custom HTTP handlers with the TRPC FastAPI framework.

    This decorator function allows registering custom HTTP route handlers that
    will be integrated with the TRPC framework through FastAPI.

    Args:
        path: HTTP path for the route (e.g., '/api/users')
        method: List of HTTP methods allowed for this route (e.g., ['GET', 'POST'])
        service_name: Optional service name for service-specific routing
        route_params: Additional route parameters for FastAPI route configuration

    Returns:
        A decorator function that registers the handler with the framework

    Example:
        @fastapi_route('/api/users', ['GET', 'POST'])
        async def user_handler(request: Request):
            return {'message': 'User endpoint'}
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        handler = HttpRoute(func, method, path, service_name)
        prefix = f"{path}_{method}"
        if service_name:
            prefix = f"{prefix}_{service_name}"
        if route_params:
            setattr(handler, "route_params", route_params)
        _fastapi_routes[prefix] = handler

    return decorator


def _register_static_file(app: FastAPI):
    """Register static file routes with the FastAPI application.

    This function mounts static file directories to the FastAPI application
    using the prefixes registered with ``fastapi_register_static``.

    Args:
        app: FastAPI application instance to register static routes with

    Note:
        Logs a warning if the specified static file directory does not exist
    """
    global _static_file_routes
    for prefix, path_to_file in _static_file_routes.items():
        if not os.path.exists(path_to_file):
            logger.warning(f"Static file directory {path_to_file} not found")
            continue
        app.mount(prefix, StaticFiles(directory=path_to_file), name="static")


def fastapi_routes(opts: BaseServerTransportOption, app: FastAPI):
    """Convert TRPC routes to FastAPI routes and register them with the application.

    This function processes all registered TRPC routes and custom FastAPI routes,
    converting them to appropriate FastAPI route configurations. It handles:
    - TRPC framework routes with service name filtering
    - Custom HTTP handlers registered via fastapi_route decorator
    - WebSocket route registration
    - Static file route mounting

    Args:
        opts: TRPC server transport options containing service configuration
        app: FastAPI application instance to register routes with

    Returns:
        The FastAPI application with all routes registered
    """
    # Register custom FastAPI routes
    for handler in _fastapi_routes.values():
        if handler.service_name and handler.service_name != opts.service.opt.service_name:
            continue
        route_params = getattr(handler, "route_params", {})
        if handler.method == ANY_METHOD:
            app.api_route(handler.path, methods=ALL_METHODS, **route_params)(handler.handler)
            continue
        if handler.method == WEB_SOCKET_METHOD:
            # Starlette 1.x dropped Starlette.add_websocket_route, but the router method remains.
            # This method is compatible with both Starlette 0.x and 1.x.
            app.router.add_websocket_route(handler.path, fastapi_http_websocket_handler(opts, handler.handler))
            continue
        if not isinstance(handler.method, list):
            handler.method = [handler.method]
        app.api_route(handler.path, methods=handler.method, **route_params)(handler.handler)

    _register_static_file(app)

    return app


fastapi_register_get = partial(fastapi_route, method=[GET_METHOD])
fastapi_register_post = partial(fastapi_route, method=[POST_METHOD])
fastapi_register_put = partial(fastapi_route, method=[PUT_METHOD])
fastapi_register_delete = partial(fastapi_route, method=[DELETE_METHOD])
fastapi_register_patch = partial(fastapi_route, method=[PATCH_METHOD])
fastapi_register_options = partial(fastapi_route, method=[OPTIONS_METHOD])
fastapi_register_head = partial(fastapi_route, method=[HEAD_METHOD])
fastapi_register_trace = partial(fastapi_route, method=[TRACE_METHOD])
fastapi_register_websocket = partial(fastapi_route, method=WEB_SOCKET_METHOD)
fastapi_register_any = partial(fastapi_route, method=ANY_METHOD)
