# Tencent is pleased to support the open source community by making tRPC-FastAPI-Python available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# tRPC-FastAPI-Python is licensed under the Apache-2.0.
"""HTTP handler adapter for TRPC FastAPI integration.

This module provides adapter functions to bridge between TRPC framework
and FastAPI HTTP handlers, enabling seamless integration of TRPC services
with FastAPI web framework.
"""
import contextvars
import inspect
from functools import wraps
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import Union

from starlette.requests import HTTPConnection

from fastapi import Request
from fastapi import Response
from fastapi import WebSocket

from trpc_sdk.abc import BaseServerTransportOption
from trpc_sdk.abc import TrpcContext
from trpc_sdk.abc import get_message
from trpc_sdk.config import TrpcConfig
from trpc_sdk.http import HTTP_REQ_KEY
from trpc_sdk.http import LOCAL_ADDR
from trpc_sdk.http import TRANS_INFO_BASE64_KEY
from trpc_sdk.http import pop_http_rsp_header
from trpc_sdk.utils import now_ms

from ._constants import SERVER_NAME
from ._constants import PROTOCOL_NAME
from ._codec import TrpcFastApiServerHttpCodec
from ._utils import get_http_code

trpc_req_ctx: contextvars.ContextVar[TrpcContext] = contextvars.ContextVar("trpc_req_ctx", default=None)  # type: ignore


def get_trpc_ctx() -> TrpcContext:
    """Get the current TRPC context from context variable.

    Returns:
        TrpcContext: The current TRPC context instance

    Example:
        >>> ctx = get_trpc_ctx()
        >>> # Use ctx for TRPC operations
    """
    return trpc_req_ctx.get()


def make_trpc_context(opts: BaseServerTransportOption, connection: HTTPConnection) -> TrpcContext:
    """Make a TRPC context from a request and publish it to ``get_trpc_ctx``.

    The connection is stored on the message as ``server_raw_req``:
    ``Service.handle_http`` passes exactly that object to the filter chain
    as ``req``, and the codec reads the request back from it.

    Args:
        opts: Transport options of the listen address serving the request.
        connection: Starlette request or WebSocket.

    Returns:
        TrpcContext: The new request context.
    """
    trpc_context = TrpcContext()
    trpc_context.timeout = opts.idle_timeout
    trpc_context.recv_time = now_ms()
    trpc_context.with_meta_data(HTTP_REQ_KEY, connection)
    trpc_context.with_meta_data(LOCAL_ADDR, f"{opts.address[0]}:{opts.port}")
    is_base64 = TrpcConfig.server_config().encode_base64
    trpc_context.with_meta_data(TRANS_INFO_BASE64_KEY, is_base64)
    trpc_context.with_meta_data(SERVER_NAME, opts.service_name)
    trpc_context.with_meta_data(PROTOCOL_NAME, opts.service.opt.protocol)
    if connection.client is not None:
        trpc_context.remote_ip = connection.client.host
    trpc_req_ctx.set(trpc_context)
    message = get_message(trpc_context)
    message.set_server_raw_req(connection)
    message.set_server_rpc_name(connection.url.path)
    return trpc_context


HttpHandlerType = Callable[[Request], Union[Awaitable[Any], Any]]


def trpc_normal_http_handler(func: Callable[[TrpcContext, Request], Union[Awaitable[Any], Any]]) -> HttpHandlerType:
    """Adapter for normal HTTP handlers to work with TRPC framework.

    This function wraps a TRPC-compatible handler function to make it compatible
    with FastAPI's HTTP handler interface by removing the first TRPC context parameter
    while preserving other function metadata.

    Args:
        opts: TRPC server transport options containing service configuration
        func: Original handler function that accepts TRPC context and Request

    Returns:
        HttpHandlerType: FastAPI-compatible HTTP handler function

    Note:
        Uses functools.wraps to preserve original function metadata including
        signature and annotations while adapting for TRPC integration.
    """

    @wraps(func)
    async def wrapper(request: Request) -> Any:
        ctx = trpc_req_ctx.get()
        return await func(ctx, request)

    # Get original function signature
    original_sig = inspect.signature(func)
    params = list(original_sig.parameters.values())

    # Remove first parameter (usually ctx parameter)
    if len(params) > 0:
        # Create new parameter list, skipping first parameter
        new_params = params[1:]

        # Create new signature
        new_sig = original_sig.replace(parameters=new_params)
        wrapper.__signature__ = new_sig

        # Update type annotations, removing first parameter
        if hasattr(func, '__annotations__'):
            annotations = func.__annotations__.copy()
            # Get first parameter name
            first_param_name = list(original_sig.parameters.keys())[0]
            if first_param_name in annotations:
                del annotations[first_param_name]
            wrapper.__annotations__ = annotations

    return wrapper


def trpc_http_handler(opts: BaseServerTransportOption) -> Callable[[Request], Any]:
    """TRPC service HTTP handler for RPC calls.

    Creates an HTTP handler that processes TRPC RPC calls through the service
    interface, handling request decoding and response encoding.

    Args:
        opts: TRPC server transport options containing service configuration

    Returns:
        Callable[[Request], Any]: HTTP handler function for TRPC RPC calls

    Note:
        This handler is specifically designed for TRPC RPC protocol handling
        with proper content type and HTTP status code management.
    """

    async def _trpc_rpc_http_handler(request: Request) -> Any:
        ctx = trpc_req_ctx.get()
        rsp_body = await opts.service.handle(ctx, b'')
        headers = pop_http_rsp_header(ctx)
        headers["Content-Type"] = "application/octet-stream"
        code = get_http_code(ctx)
        response = Response(content=rsp_body, media_type="application/octet-stream", status_code=code, headers=headers)
        return response

    return _trpc_rpc_http_handler


def fastapi_http_websocket_handler(opts: BaseServerTransportOption, func: Callable[..., Any]) -> Callable[..., Any]:
    """Adapter for FastAPI HTTP handlers to work with TRPC framework.

    This function wraps a FastAPI-compatible handler function to make it compatible
    with TRPC framework by adding the first TRPC context parameter while preserving
    other function metadata.
    """

    @wraps(func)
    async def wrapper(websocket: WebSocket) -> Any:
        ctx = make_trpc_context(opts, websocket)
        TrpcFastApiServerHttpCodec.decode_trpc_req_header(ctx, websocket)

        async def _http_func(ctx: TrpcContext, req: WebSocket) -> Any:
            return await func(req)

        return await opts.service.handle_http(ctx, _http_func)

    return wrapper
