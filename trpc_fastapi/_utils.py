# Tencent is pleased to support the open source community by making tRPC-FastAPI-Python available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# tRPC-FastAPI-Python is licensed under the Apache-2.0.
"""Utility functions for TRPC FastAPI Plugin integration.

This module provides helper functions for socket management and HTTP status code
handling in the TRPC FastAPI integration framework.
"""

import http
import socket

from trpc_sdk.abc import TrpcContext

from ._constants import HTTP_CODE
from ._constants import SERVER_NAME
from ._constants import PROTOCOL_NAME


def create_uvicorn_compatible_socket(host: str, port: int) -> socket.socket:
    """Create a uvicorn compatible socket with reuse port support.

    This function creates a TCP socket configured for reuse address and port options
    so that every rpc task in ``separate`` mode can bind the same host and port.

    Args:
        host: The host address to bind the socket to (e.g., 'localhost', '0.0.0.0')
        port: The port number to bind the socket to

    Returns:
        socket.socket: A configured socket object ready for uvicorn server usage

    Raises:
        OSError: If socket creation or binding fails
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Set socket options
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except OSError:
        # SO_REUSEPORT is not available, only use SO_REUSEADDR
        pass

    # Bind the address
    try:
        sock.bind((host, port))
    except OSError:
        sock.close()
        raise

    return sock


def get_http_code(ctx: TrpcContext) -> int:
    """Retrieve the HTTP status code from TRPC context metadata.

    This function extracts the HTTP status code stored in the TRPC context's
    metadata. If no status code is found, it defaults to HTTP 200 OK.

    Args:
        ctx: The TRPC context containing metadata

    Returns:
        int: The HTTP status code (defaults to 200 if not set)
    """
    return ctx.get_meta_data(HTTP_CODE, http.HTTPStatus.OK.value)


def set_http_code(ctx: TrpcContext, code: int) -> TrpcContext:
    """Set the HTTP status code in TRPC context metadata.

    This function stores an HTTP status code in the TRPC context's metadata
    for later retrieval and use in HTTP response handling.

    Args:
        ctx: The TRPC context to modify
        code: The HTTP status code to set

    Returns:
        TrpcContext: The modified TRPC context with updated metadata
    """
    return ctx.with_meta_data(HTTP_CODE, code)


def get_service_name(ctx: TrpcContext) -> str:
    """Get service name from TRPC context metadata.

    Returns:
        str: Service name
    """
    return ctx.get_meta_data(SERVER_NAME, "")


def get_protocol_name(ctx: TrpcContext) -> str:
    """Get protocol name from TRPC context metadata.

    Returns:
        str: Protocol name
    """
    return ctx.get_meta_data(PROTOCOL_NAME, "")
