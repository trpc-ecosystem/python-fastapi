# Tencent is pleased to support the open source community by making tRPC-FastAPI-Python available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# tRPC-FastAPI-Python is licensed under the Apache-2.0.
"""
TRPC FastAPI Plugin Module

This module provides integration between TRPC framework and FastAPI web framework.
It enables TRPC services to be exposed as FastAPI HTTP endpoints with automatic
route registration, middleware support, and WebSocket capabilities.

Key Features:
- Automatic HTTP route registration for TRPC services
- WebSocket support for real-time communication
- Middleware integration for request/response processing
- Context management for TRPC services
- Codec support for various data formats

Main Components:
- FastapiServerTransport: Core transport implementation
- fastapi_route: Decorator for registering custom routes
- Context management utilities
- Plugin registration system

Importing this package registers the ``http_fastapi`` protocol with the
tRPC SDK; import it before ``create_server``.
"""

from .version import __version__ as trpc_fastapi_version

from ._callback import register_before_process_request_callback
from ._callback import register_after_process_response_callback
from ._constants import TRPC_FASTAPI_PROTOCOL
from ._constants import ANY_METHOD
from ._constants import GET_METHOD
from ._constants import POST_METHOD
from ._constants import PUT_METHOD
from ._constants import DELETE_METHOD
from ._constants import PATCH_METHOD
from ._constants import OPTIONS_METHOD
from ._constants import HEAD_METHOD
from ._constants import TRACE_METHOD
from ._constants import WEB_SOCKET_METHOD
from ._config import load_fastapi_config
from ._handler_adapter import get_trpc_ctx
from ._routes import fastapi_route
from ._routes import fastapi_register_static
from ._routes import fastapi_register_any
from ._routes import fastapi_register_get
from ._routes import fastapi_register_post
from ._routes import fastapi_register_put
from ._routes import fastapi_register_delete
from ._routes import fastapi_register_patch
from ._routes import fastapi_register_options
from ._routes import fastapi_register_head
from ._routes import fastapi_register_trace
from ._routes import fastapi_register_websocket
from ._server_transport import FastapiServerTransport
from ._server_transport import get_fastapi_app
from ._server_transport import FastapiServerTransportFactory
from ._trpc_server_process import register_fastapi_app
from ._registry import register_protocol_to_fastapi
from ._utils import get_service_name
from ._utils import get_protocol_name

__all__ = [
    "TRPC_FASTAPI_PROTOCOL",  # TRPC FastAPI protocol
    "ANY_METHOD",  # Any method
    "GET_METHOD",  # Get method
    "POST_METHOD",  # Post method
    "PUT_METHOD",  # Put method
    "DELETE_METHOD",  # Delete method
    "PATCH_METHOD",  # Patch method
    "OPTIONS_METHOD",  # Options method
    "HEAD_METHOD",  # Head method
    "TRACE_METHOD",  # Trace method
    "WEB_SOCKET_METHOD",  # WebSocket method
    "trpc_fastapi_version",  # Plugin version information
    "FastapiServerTransport",  # Main transport implementation
    "fastapi_route",  # Route registration decorator
    "fastapi_register_static",  # Static file registration utility
    "fastapi_register_any",  # Any method registration utility
    "fastapi_register_get",  # Get method registration utility
    "fastapi_register_post",  # Post method registration utility
    "fastapi_register_put",  # Put method registration utility
    "fastapi_register_delete",  # Delete method registration utility
    "fastapi_register_patch",  # Patch method registration utility
    "fastapi_register_options",  # Options method registration utility
    "fastapi_register_head",  # Head method registration utility
    "fastapi_register_trace",  # Trace method registration utility
    "fastapi_register_websocket",  # WebSocket method registration utility
    "register_fastapi_app",  # FastAPI app registration utility
    "get_trpc_ctx",  # Context access utility
    "get_fastapi_app",  # FastAPI app access utility
    "register_before_process_request_callback",  # Register before process request callback
    "register_after_process_response_callback",  # Register after process response callback
    "register_protocol_to_fastapi",  # Register protocol to fastapi
    "FastapiServerTransportFactory",  # FastAPI server transport factory
    "get_service_name",  # Get service name utility
    "get_protocol_name",  # Get protocol name utility
    "load_fastapi_config",  # Load fastapi config utility
]
