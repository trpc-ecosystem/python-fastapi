# Tencent is pleased to support the open source community by making tRPC-FastAPI-Python available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# tRPC-FastAPI-Python is licensed under the Apache-2.0.
"""
TRPC FastAPI Server Transport Module.

Every fastapi protocol is registered with ``register_protocol_handle``, so
``ServiceAdapter.run`` serves its addresses through a ``UserProtocolTransport``
bound to :func:`~trpc_fastapi._trpc_server_process.start_fastapi`. The SDK then
calls that starter in whichever process and thread serves the address.
"""
from fastapi import FastAPI

from trpc_sdk.abc import BasePluginFactory
from trpc_sdk.common import get_current_process_var
from trpc_sdk.transport import UserProtocolTransport

from ._constants import FASTAPI_PROCESS_VAR
from ._trpc_server_process import start_fastapi


class FastapiServerTransport(UserProtocolTransport):
    """fastapi server transport: a ``UserProtocolTransport`` bound to ``start_fastapi``.

    The SDK builds its own ``UserProtocolTransport`` for every fastapi service
    from the registered starter, so this class is not a plugin; it is kept for
    code that constructs the fastapi transport explicitly.
    """

    def __init__(self) -> None:
        """Bind the transport to the fastapi starter."""
        super().__init__(start_fastapi)


class FastapiServerTransportFactory(BasePluginFactory):
    """Factory for :class:`FastapiServerTransport`.

    Not registered as a plugin, for the same reason as the transport.
    """

    def create(self) -> FastapiServerTransport:
        """Create a new FastAPI server transport instance.

        Returns:
            FastapiServerTransport: A new instance of FastAPI server transport
        """
        return FastapiServerTransport()


def get_fastapi_app() -> FastAPI:
    """Retrieve the FastAPI app serving the current request.

    Looked up per process and then per uvicorn thread, so each serving
    process, and each fastapi address within a process, sees its own app.

    Returns:
        FastAPI: The FastAPI application instance

    Raises:
        ValueError: If no fastapi app runs in this process, or the caller is
            not on a fastapi request thread
    """
    fastapi_process = get_current_process_var(FASTAPI_PROCESS_VAR)
    if fastapi_process is None:
        raise ValueError("Fastapi app not found in current process")
    return fastapi_process.fastapi_app
