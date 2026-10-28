# Tencent is pleased to support the open source community by making tRPC-FastAPI-Python available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# tRPC-FastAPI-Python is licensed under the Apache-2.0.
"""Tests for the fastapi server codec."""
import base64
import json
from typing import Dict
from typing import Optional

import pytest
from starlette.requests import Request

from trpc_sdk._inner import trpc_pb2
from trpc_sdk.abc import TrpcContext
from trpc_sdk.abc import get_message
from trpc_sdk.exceptions import TrpcErrorCode
from trpc_sdk.exceptions import TrpcErrorType
from trpc_sdk.exceptions import TrpcException
from trpc_sdk.http import HTTP_TRPC_HEADER
from trpc_sdk.http import TRANS_INFO_BASE64_KEY
from trpc_sdk.http import get_http_rsp_header
from trpc_sdk.serialization import SerializationType

from trpc_fastapi._codec import TrpcFastApiServerHttpCodec
from trpc_fastapi._utils import get_http_code
from trpc_fastapi._utils import set_http_code


def make_request(method: str = "GET",
                 path: str = "/trpc.test.helloworld.Greeter/SayHello",
                 query: bytes = b"",
                 headers: Optional[Dict[str, str]] = None,
                 body: bytes = b"") -> Request:
    """Build a starlette request without a server."""
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": query,
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "client": ("10.0.0.1", 5555),
        "server": ("127.0.0.1", 8000),
        "scheme": "http",
        "http_version": "1.1",
    }

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


def make_ctx(request: Request, is_base64: bool = False) -> TrpcContext:
    """Context whose message carries ``request`` the way make_trpc_context sets it."""
    ctx = TrpcContext()
    ctx.with_meta_data(TRANS_INFO_BASE64_KEY, is_base64)
    get_message(ctx).set_server_raw_req(request)
    return ctx


def test_decode_trpc_req_header_reads_trpc_headers():
    """Test tRPC headers end up on the request head and message."""
    request = make_request(
        headers={
            HTTP_TRPC_HEADER.trpc_request_id: "42",
            HTTP_TRPC_HEADER.trpc_timeout: "800",
            HTTP_TRPC_HEADER.trpc_caller: "trpc.app.server.caller",
            HTTP_TRPC_HEADER.trpc_trans_info: json.dumps({"k": "v"}),
        })
    ctx = make_ctx(request)

    TrpcFastApiServerHttpCodec.decode_trpc_req_header(ctx, request)

    msg = get_message(ctx)
    head = msg.server_req_head
    assert isinstance(head, trpc_pb2.RequestProtocol)
    assert head.request_id == 42
    assert head.timeout == 800
    assert head.caller == b"trpc.app.server.caller"
    # Callee defaults to the first path segment.
    assert head.callee == b"trpc.test.helloworld.Greeter"
    assert head.func == b"/trpc.test.helloworld.Greeter/SayHello"
    assert head.trans_info["k"] == b"v"
    assert msg.server_meta_data["k"] == "v"
    assert msg.server_rpc_name == "/trpc.test.helloworld.Greeter/SayHello"


def test_decode_trpc_req_header_base64_trans_info():
    """Test base64 trans_info is decoded when the server enables it."""
    encoded = base64.b64encode(b"hello").decode()
    request = make_request(headers={HTTP_TRPC_HEADER.trpc_trans_info: json.dumps({"k": encoded})})
    ctx = make_ctx(request, is_base64=True)

    TrpcFastApiServerHttpCodec.decode_trpc_req_header(ctx, request)

    assert get_message(ctx).server_meta_data["k"] == "hello"


@pytest.mark.asyncio
async def test_decode_data_get_uses_query_and_form():
    """Test GET reads the query string and picks Form serialization."""
    request = make_request(method="GET", query=b"msg=hi")
    ctx = make_ctx(request)

    body = await TrpcFastApiServerHttpCodec().decode_data(ctx, b"")

    assert body == b"msg=hi"
    msg = get_message(ctx)
    assert msg.serialization_type == SerializationType.Form
    assert msg.server_req_head.content_type == SerializationType.Form


@pytest.mark.asyncio
@pytest.mark.parametrize("content_type, expected", [
    ("application/json", SerializationType.JSON),
    ("application/pb", SerializationType.PB),
    ("", SerializationType.JSON),
])
async def test_decode_data_post_picks_serialization_by_content_type(content_type, expected):
    """Test POST reads the body and maps Content-Type to a serialization type."""
    headers = {"Content-Type": content_type} if content_type else {}
    request = make_request(method="POST", headers=headers, body=b'{"msg": "hi"}')
    ctx = make_ctx(request)

    body = await TrpcFastApiServerHttpCodec().decode_data(ctx, b"")

    assert body == b'{"msg": "hi"}'
    assert get_message(ctx).serialization_type == expected


def test_encode_data_success_keeps_status_and_writes_trpc_headers():
    """Test a successful response keeps 200 and carries the tRPC response head."""
    ctx = make_ctx(make_request())
    rsp_head = trpc_pb2.ResponseProtocol()
    rsp_head.request_id = 7
    get_message(ctx).set_server_rsp_head(rsp_head)

    body = TrpcFastApiServerHttpCodec().encode_data(ctx, b"payload")

    assert body == b"payload"
    assert get_http_code(ctx) == 200
    headers = get_http_rsp_header(ctx)
    assert headers[HTTP_TRPC_HEADER.trpc_request_id] == "7"
    assert headers[HTTP_TRPC_HEADER.trpc_version] == str(trpc_pb2.TRPC_PROTO_V1)


@pytest.mark.parametrize("code, expected_status", [
    (TrpcErrorCode.TRPC_SERVER_NOFUNC_ERR, 404),
    (TrpcErrorCode.TRPC_SERVER_SYSTEM_ERR, 500),
    (10001, 200),
])
def test_encode_data_error_sets_error_headers_and_status(code, expected_status):
    """Test errors map to an HTTP status and are reported in tRPC error headers."""
    ctx = make_ctx(make_request())
    get_message(ctx).set_server_rsp_err(TrpcException(TrpcErrorType.BUSINESS, code, "boom"))

    TrpcFastApiServerHttpCodec().encode_data(ctx, b"")

    headers = get_http_rsp_header(ctx)
    assert headers[HTTP_TRPC_HEADER.trpc_error_message] == "boom"
    assert headers[HTTP_TRPC_HEADER.trpc_user_func_error_code] == str(int(code))
    assert get_http_code(ctx) == expected_status


def test_encode_data_unmapped_error_keeps_status_set_by_handler():
    """Test an error code with no HTTP mapping keeps the status already on the context."""
    ctx = make_ctx(make_request())
    set_http_code(ctx, 418)
    get_message(ctx).set_server_rsp_err(TrpcException(TrpcErrorType.BUSINESS, 10001, "boom"))

    TrpcFastApiServerHttpCodec().encode_data(ctx, b"")

    assert get_http_code(ctx) == 418
