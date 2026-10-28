# Tencent is pleased to support the open source community by making tRPC-FastAPI-Python available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# tRPC-FastAPI-Python is licensed under the Apache-2.0.
"""Tests for the request/response callback filter."""
import pytest
from fastapi import Response

from trpc_sdk.abc import FilterStreamResultType
from trpc_sdk.abc import TrpcContext
from trpc_sdk.abc import get_message
from trpc_sdk.exceptions import TrpcErrorCode
from trpc_sdk.exceptions import TrpcException
from trpc_sdk.filters import get_server_filter
from trpc_sdk.http import HTTP_RSP_KEY

from trpc_fastapi import register_after_process_response_callback
from trpc_fastapi import register_before_process_request_callback
from trpc_fastapi._callback import FastApiServerCallback
from trpc_fastapi._constants import CALLBACK_NAME


def test_callback_filter_is_registered():
    """Test the filter is reachable by name, as build_app looks it up."""
    assert isinstance(get_server_filter(CALLBACK_NAME), FastApiServerCallback)


@pytest.mark.asyncio
async def test_run_calls_before_and_after_callbacks():
    """Test both callbacks run around the handler, sync and async alike."""
    calls = []

    def before(ctx, req):
        calls.append(("before", req))

    async def after(ctx, rsp):
        calls.append(("after", rsp))

    register_before_process_request_callback(before)
    register_after_process_response_callback(after)

    async def next_handle():
        calls.append(("handler", None))
        return "rsp", None

    ctx = TrpcContext()
    rsp, err = await FastApiServerCallback().run(ctx, "req", next_handle)

    assert (rsp, err) == ("rsp", None)
    assert calls == [("before", "req"), ("handler", None), ("after", "rsp")]
    assert ctx.get_meta_data(HTTP_RSP_KEY) == "rsp"


@pytest.mark.asyncio
async def test_after_callback_response_replaces_handler_result():
    """Test a Response returned by the after-callback becomes the result."""
    replacement = Response(content=b"replaced")
    register_after_process_response_callback(lambda ctx, rsp: replacement)

    async def next_handle():
        return "rsp", None

    ctx = TrpcContext()
    rsp, err = await FastApiServerCallback().run(ctx, None, next_handle)

    assert rsp is replacement
    assert err is None
    assert ctx.get_meta_data(HTTP_RSP_KEY) is replacement


@pytest.mark.asyncio
async def test_handler_error_is_recorded_on_message():
    """Test an error from the chain is returned and stored as server_rsp_err."""
    error = TrpcException(1, TrpcErrorCode.TRPC_SERVER_SYSTEM_ERR, "boom")

    async def next_handle():
        return None, error

    ctx = TrpcContext()
    _, err = await FastApiServerCallback().run(ctx, None, next_handle)

    assert err is error
    assert get_message(ctx).server_rsp_err is error


@pytest.mark.asyncio
async def test_non_trpc_rsp_err_set_by_callback_is_wrapped():
    """Test a plain value left in server_rsp_err becomes a system TrpcException."""

    def after(ctx, rsp):
        get_message(ctx).set_server_rsp_err("callback failed")

    register_after_process_response_callback(after)

    async def next_handle():
        return "rsp", None

    _, err = await FastApiServerCallback().run(TrpcContext(), None, next_handle)

    assert isinstance(err, TrpcException)
    assert err.code == TrpcErrorCode.TRPC_SERVER_SYSTEM_ERR
    assert err.msg == "callback failed"


@pytest.mark.asyncio
async def test_run_stream_passes_results_through():
    """Test run_stream yields every result of the next stage unchanged."""
    results = [FilterStreamResultType(rsp=1), FilterStreamResultType(rsp=2)]

    async def next_handle():
        for result in results:
            yield result

    seen = [r async for r in FastApiServerCallback().run_stream(TrpcContext(), None, next_handle)]

    assert seen == results
