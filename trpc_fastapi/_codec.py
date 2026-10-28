# Tencent is pleased to support the open source community by making tRPC-FastAPI-Python available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# tRPC-FastAPI-Python is licensed under the Apache-2.0.
"""
Codec for TRPC FastAPI Plugin

This module provides encoding and decoding functionality for TRPC protocol
over HTTP/FastAPI transport. It handles protocol conversion between TRPC
messages and HTTP requests/responses, including header parsing, serialization
type detection, and error handling.

The request travels on the context's message as ``server_raw_req`` (set by
``make_trpc_context``); the HTTP status code and response headers are kept in
the context's meta data until ``filter_middleware`` or the RPC route handler
builds the starlette response.

Key Components:
- TrpcFastApiServerHttpCodec: Main codec for encoding/decoding TRPC messages

The codec and the SDK's ``ServerHttpParser`` (uvicorn parses HTTP itself, so
the parser only fills the protocol's parser slot) are registered here for the
default ``http_fastapi`` protocol; other
protocols are added by
:func:`~trpc_fastapi._registry.register_protocol_to_fastapi`.
"""

import base64
import http
import json
from typing import Any
from typing import MutableMapping

from starlette.datastructures import Headers
from starlette.requests import HTTPConnection
from starlette.requests import Request as HttpRequest

from trpc_sdk._inner import trpc_pb2
from trpc_sdk.abc import BaseCodec
from trpc_sdk.abc import PluginInitPos
from trpc_sdk.abc import PluginType
from trpc_sdk.abc import TrpcContext
from trpc_sdk.abc import TrpcMessage
from trpc_sdk.abc import get_message
from trpc_sdk.exceptions import TrpcErrorCode
from trpc_sdk.exceptions import TrpcException
from trpc_sdk.http import HTTP_TRPC_HEADER
from trpc_sdk.http import ServerHttpParser
from trpc_sdk.http import TRANS_INFO_BASE64_KEY
from trpc_sdk.http import find_http_status
from trpc_sdk.http import find_serialization_type
from trpc_sdk.http import get_http_rsp_header
from trpc_sdk.http import get_trpc_error_code
from trpc_sdk.http import set_http_rsp_header
from trpc_sdk.plugin import register_plugin
from trpc_sdk.serialization import SerializationType

from ._constants import CONTENT_TYPE
from ._constants import GET_METHOD
from ._constants import TRPC_FASTAPI_PROTOCOL
from ._utils import get_http_code
from ._utils import set_http_code


register_plugin(PluginType.SERVER_PARSER, TRPC_FASTAPI_PROTOCOL, init_pos=PluginInitPos.WORKER)(ServerHttpParser)


@register_plugin(PluginType.SERVER_CODEC, TRPC_FASTAPI_PROTOCOL, init_pos=PluginInitPos.WORKER)
class TrpcFastApiServerHttpCodec(BaseCodec):
    """
    TRPC FastAPI Server HTTP Codec

    This class handles encoding and decoding of TRPC protocol messages
    over HTTP/FastAPI transport. It provides the core functionality for:

    - Encoding server responses to HTTP responses with proper headers
    - Decoding HTTP requests to TRPC protocol messages
    - Handling serialization types (JSON, Form, etc.)
    - Managing TRPC-specific headers and metadata
    - Error handling and status code mapping

    Overrides the context-first ``encode_data`` / ``decode_data`` pair
    because both need the starlette request stored on the context's message.
    There is no message-first ``encode`` / ``decode``.
    """

    def encode_data(self, context: TrpcContext, body: Any) -> Any:
        """
        Encode server response body to binary data for client

        This method handles the encoding of server response data, including:
        - Error handling and status code mapping
        - TRPC header encoding
        - HTTP status code setting
        - Response header management

        Args:
            context: Server request context; the status code and response
                headers are written back into its meta data
            body: Response body bytes to be encoded

        Returns:
            bytes: Encoded response body (same as input body)
        """
        message: TrpcMessage = get_message(context)
        headers: dict = get_http_rsp_header(context)
        err: TrpcException = message.server_rsp_err
        status_code = get_http_code(context)
        if err.code != TrpcErrorCode.TRPC_INVOKE_SUCCESS:
            headers[HTTP_TRPC_HEADER.trpc_error_message] = err.msg
            trpc_error_code = get_trpc_error_code(err.type, HTTP_TRPC_HEADER.trpc_user_func_error_code)
            headers[trpc_error_code] = str(err.code)
            http_code = find_http_status(err.code, None)
            if http_code is None:
                if status_code in http.HTTPStatus.__members__.values():
                    http_code = http.HTTPStatus(status_code)
                elif err.code in http.HTTPStatus.__members__.values():
                    http_code = http.HTTPStatus(err.code)
                else:
                    # Non-standard HTTP codes still go out as 200; the
                    # tRPC error headers carry the real code.
                    http_code = http.HTTPStatus.OK
            set_http_code(context, http_code.value)

        self.encode_trpc_rsp_header(context, headers)
        set_http_rsp_header(context, headers)

        return body

    @classmethod
    def encode_trpc_rsp_header(cls, ctx: TrpcContext, rsp_headers: MutableMapping[str, str]) -> None:
        """
        Set TRPC-related headers in HTTP response

        This method encodes TRPC protocol information into HTTP response headers,
        including call type, request ID, message type, version, and transmission info.
        It also handles base64 encoding of transmission data when required.

        Args:
            ctx: Server request context; supplies the message and the
                ``TRANS_INFO_BASE64_KEY`` flag
            rsp_headers: Mutable HTTP response headers to be updated
        """
        message: TrpcMessage = get_message(ctx)
        trans_info = message.server_meta_data or {}
        is_base64 = ctx.get_meta_data(TRANS_INFO_BASE64_KEY, False)
        if isinstance(message.server_rsp_head, trpc_pb2.ResponseProtocol):
            trpc_rsp = message.server_rsp_head
            rsp_headers[HTTP_TRPC_HEADER.trpc_call_type] = str(trpc_rsp.call_type)
            rsp_headers[HTTP_TRPC_HEADER.trpc_request_id] = str(trpc_rsp.request_id)
            rsp_headers[HTTP_TRPC_HEADER.trpc_message_type] = str(trpc_rsp.message_type)
            rsp_headers[HTTP_TRPC_HEADER.trpc_version] = str(trpc_pb2.TRPC_PROTO_V1)
            trans_info.update(trpc_rsp.trans_info)

        for key, value in trans_info.items():
            if is_base64:
                if not isinstance(value, bytes):
                    value = str(value).encode()
                # Turn into str below so json.dumps accepts it.
                value = base64.b64encode(value)
            if isinstance(value, bytes):
                value = value.decode()
            trans_info[key] = value
        if trans_info:
            rsp_headers[HTTP_TRPC_HEADER.trpc_trans_info] = json.dumps(trans_info)

    async def decode_data(self, context: TrpcContext, _: Any) -> bytes:
        """
        Decode client request on server side

        This method handles the decoding of incoming HTTP requests to TRPC protocol
        messages. It supports both GET and POST requests, automatically detects
        serialization types, and extracts TRPC-specific headers.

        Args:
            context: Server request context whose message holds the starlette
                request as ``server_raw_req``
            _: Unused; the body is read from that request

        Returns:
            bytes: Request body bytes for further processing
        """
        message: TrpcMessage = get_message(context)
        request: HttpRequest = message.server_raw_req

        # Parse TRPC request headers from HTTP protocol
        self.decode_trpc_req_header(context, request)
        trpc_req = message.server_req_head

        if request.method == GET_METHOD:
            req_body = request.url.query.encode('utf-8')
            message.set_serialization_type(SerializationType.Form)
            trpc_req.content_type = SerializationType.Form
            return req_body

        # Read request data
        req_body = await request.body()

        # Set serialization type
        message.set_serialization_type(SerializationType.JSON)

        # Get content type and set serialization type
        content_type = request.headers.get(CONTENT_TYPE, "")
        serialization_type = find_serialization_type(content_type, SerializationType.JSON)
        message.set_serialization_type(serialization_type)
        trpc_req.content_type = serialization_type

        return req_body

    @classmethod
    def decode_trpc_req_header(cls, ctx: TrpcContext, request: HTTPConnection) -> None:
        """
        Parse TRPC information from HTTP request headers

        This method extracts TRPC protocol information from HTTP request headers,
        including version, call type, message type, request ID, timeout, caller info,
        callee info, and transmission information. It also handles base64 decoding
        of transmission data when required.

        Args:
            ctx: Server request context; its message is populated and its
                ``TRANS_INFO_BASE64_KEY`` flag is read
            request: HTTP request or WebSocket connection carrying the headers
        """
        message: TrpcMessage = get_message(ctx)
        url_path = request.url.path
        message.set_server_rpc_name(url_path)
        trpc_req = trpc_pb2.RequestProtocol()
        headers: Headers = request.headers

        trpc_version = headers.get(HTTP_TRPC_HEADER.trpc_version, trpc_req.version)
        trpc_req.version = int(trpc_version)

        trpc_call_type = headers.get(HTTP_TRPC_HEADER.trpc_call_type, trpc_req.call_type)
        trpc_req.call_type = int(trpc_call_type)

        trpc_message_type = headers.get(HTTP_TRPC_HEADER.trpc_message_type, trpc_req.message_type)
        trpc_req.message_type = int(trpc_message_type)

        trpc_request_id = headers.get(HTTP_TRPC_HEADER.trpc_request_id, trpc_req.request_id)
        trpc_req.request_id = int(trpc_request_id)
        message.set_request_id(trpc_req.request_id)

        trpc_timeout = headers.get(HTTP_TRPC_HEADER.trpc_timeout, trpc_req.timeout)
        trpc_req.timeout = int(trpc_timeout)
        message.set_timeout(trpc_req.timeout)

        trpc_caller_method = headers.get(HTTP_TRPC_HEADER.trpc_caller_method)
        if trpc_caller_method:
            message.set_caller_method(trpc_caller_method)

        trpc_caller = headers.get(HTTP_TRPC_HEADER.trpc_caller, None)  # trpc.app.server.service
        if trpc_caller:
            trpc_req.caller = trpc_caller.encode('utf-8')
            message.set_caller_service_name(trpc_caller)

        trpc_req.func = url_path.encode('utf-8')
        path = url_path.split("/")
        callee = path[1] if len(path) > 1 else None

        trpc_callee = headers.get(HTTP_TRPC_HEADER.trpc_callee, callee)  # trpc.app.server.service
        if trpc_callee:
            trpc_req.callee = trpc_callee.encode('utf-8')
            message.set_callee_service_name(trpc_callee)

        message.set_dyeing((trpc_req.message_type & trpc_pb2.TRPC_DYEING_MESSAGE) != 0)

        trpc_trans_info = headers.get(HTTP_TRPC_HEADER.trpc_trans_info, None)
        is_base64 = ctx.get_meta_data(TRANS_INFO_BASE64_KEY, False)
        if trpc_trans_info:
            trpc_trans_info: dict = json.loads(trpc_trans_info)
            if is_base64:
                for k, v in trpc_trans_info.items():
                    val = base64.b64decode(v)
                    try:
                        trpc_trans_info[k] = val.decode()
                    except Exception:  # pylint: disable=broad-except
                        # If decoding fails, keep the original value
                        trpc_trans_info[k] = val
            message.server_meta_data.update(trpc_trans_info)
            for k, v in trpc_trans_info.items():
                if not isinstance(v, bytes):
                    v = str(v).encode()
                trpc_req.trans_info[k] = v

        message.set_server_req_head(trpc_req)
