# Tencent is pleased to support the open source community by making tRPC-FastAPI-Python available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# tRPC-FastAPI-Python is licensed under the Apache-2.0.
"""Greeter service implementation used by the example server."""

import sys
from pathlib import Path

from trpc_sdk.abc import TrpcContext
from trpc_sdk.log import logger

# add the stub to the path
sys.path.append(str(Path(__file__).parent / "rpc_http/stub"))

from trpc_trpc_python_group_helloworld import pb
from trpc_trpc_python_group_helloworld import rpc


class GreeterServicer(rpc.GreeterServicer):
    """Provides methods that implement functionality of Greeter servicer."""

    def __init__(self):
        """Create a Greeter servicer with no extra state."""
        pass

    # pylint: disable=invalid-name
    async def SayHello(self, ctx: TrpcContext, request: pb.HelloRequest) -> pb.HelloReply:
        """Reply with the request message prefixed by ``hello: ``.

        Args:
            ctx: tRPC request context. This example does not read it.
            request: Incoming hello request.

        Returns:
            A reply whose ``msg`` is ``hello: `` plus ``request.msg``.
        """
        logger.debug("[SayHello] test debug log")

        rsp = pb.HelloReply()
        print(f"request: {request.msg}")
        rsp.msg = f"hello: {request.msg}"

        return rsp
