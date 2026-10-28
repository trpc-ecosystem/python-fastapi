# Tencent is pleased to support the open source community by making tRPC-FastAPI-Python available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# tRPC-FastAPI-Python is licensed under the Apache-2.0.
"""
Callback for TRPC FastAPI Plugin

This module provides callback functionality for TRPC FastAPI plugin.
It includes callback functions for various events in the TRPC framework.
"""
import inspect
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import List

from fastapi import Request
from fastapi import Response

from trpc_sdk.abc import BaseFilter
from trpc_sdk.abc import FilterAsyncGenHandleType
from trpc_sdk.abc import FilterAsyncGenReturnType
from trpc_sdk.abc import FilterHandleType
from trpc_sdk.abc import FilterReturnType
from trpc_sdk.abc import PluginInitPos
from trpc_sdk.abc import PluginType
from trpc_sdk.abc import TrpcContext
from trpc_sdk.abc import get_message
from trpc_sdk.exceptions import TrpcErrorCode
from trpc_sdk.exceptions import TrpcErrorType
from trpc_sdk.exceptions import TrpcException
from trpc_sdk.http import HTTP_RSP_KEY
from trpc_sdk.plugin import register_plugin

from ._constants import CALLBACK_NAME

_before_process_request_callback: List[Callable[[TrpcContext, Request], Awaitable[Any]]] = []
_after_process_response_callback: List[Callable[[TrpcContext, Response], Awaitable[Any]]] = []


def register_before_process_request_callback(callback: Callable[[TrpcContext, Request], Awaitable[Any]]):
    """Run ``callback(ctx, request)`` before every fastapi request reaches its handler.

    Args:
        callback: Sync or async callable.
    """
    _before_process_request_callback.append(callback)


def register_after_process_response_callback(callback: Callable[[TrpcContext, Response], Awaitable[Any]]):
    """Run ``callback(ctx, response)`` after every fastapi handler returns.

    A ``Response`` returned by the callback replaces the handler's response.

    Args:
        callback: Sync or async callable.
    """
    _after_process_response_callback.append(callback)


async def execute_before_process_request_callback(ctx: TrpcContext, req: Request):
    """Run every registered before-request callback.

    Args:
        ctx: tRPC request context.
        req: Incoming HTTP request.
    """
    for callback in _before_process_request_callback:
        if inspect.iscoroutinefunction(callback):
            await callback(ctx, req)
        else:
            callback(ctx, req)


async def execute_after_process_response_callback(ctx: TrpcContext, rsp: Response):
    """Run the first registered after-response callback and return its result.

    Args:
        ctx: tRPC request context.
        rsp: Handler response.

    Returns:
        The value returned by the first callback, or ``None`` when none is registered.
    """
    for callback in _after_process_response_callback:
        if inspect.iscoroutinefunction(callback):
            return await callback(ctx, rsp)
        else:
            return callback(ctx, rsp)


@register_plugin(PluginType.SERVER_FILTER_COMPONENT, CALLBACK_NAME, init_pos=PluginInitPos.WORKER)
class FastApiServerCallback(BaseFilter):
    """Server-side filter that runs the registered request/response callbacks.

    Installed on every fastapi service when its app is built. The handler
    result is stored under ``HTTP_RSP_KEY`` so ``filter_middleware`` can still
    return it when the filter chain hands back something other than a
    ``Response``.
    """

    async def run(self, ctx: TrpcContext, req: Any, next_handle: FilterHandleType) -> FilterReturnType:
        """Wrap one unary request with the before/after callbacks.

        Args:
            ctx: Request context.
            req: Starlette request, taken from the message's ``server_raw_req``.
            next_handle: Next stage of the filter chain.

        Returns:
            ``(response, error)``; the response is the one returned by an
            after-callback when it returned a ``Response``.
        """
        msg = get_message(ctx)
        await execute_before_process_request_callback(ctx, req)
        rsp, err = await next_handle()
        if err:
            msg.set_server_rsp_err(err)
        ctx.with_meta_data(HTTP_RSP_KEY, rsp)
        response = await execute_after_process_response_callback(ctx, rsp)
        if not err and msg.server_rsp_err:
            if isinstance(msg.server_rsp_err, TrpcException):
                if msg.server_rsp_err.code != TrpcErrorCode.TRPC_INVOKE_SUCCESS:
                    err = msg.server_rsp_err
            else:
                err = TrpcException(TrpcErrorType.BUSINESS, TrpcErrorCode.TRPC_SERVER_SYSTEM_ERR,
                                    str(msg.server_rsp_err))
        if isinstance(response, Response):
            ctx.with_meta_data(HTTP_RSP_KEY, response)
            return response, err
        return rsp, err

    async def run_stream(self, ctx: TrpcContext, req: Any,
                         next_handle: FilterAsyncGenHandleType) -> FilterAsyncGenReturnType:
        """Pass stream results through unchanged; fastapi routes are unary only.

        Args:
            ctx: Request context.
            req: Request object.
            next_handle: Next stage of the stream filter chain.

        Yields:
            Every result produced by ``next_handle``.
        """
        async for result in next_handle():
            yield result
