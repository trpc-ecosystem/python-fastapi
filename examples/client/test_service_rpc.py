#!/usr/bin/env python3
# Tencent is pleased to support the open source community by making tRPC-FastAPI-Python available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# tRPC-FastAPI-Python is licensed under the Apache-2.0.
"""Client that calls Greeter.SayHello over HTTP."""

import sys
import asyncio
from pathlib import Path

from trpc_sdk.abc import TrpcContext
from trpc_sdk.client import Options
from trpc_sdk.plugin import init_plugins
from trpc_sdk.serialization import SerializationType

# add the stub to the path
sys.path.append(str(Path(__file__).parent.parent / "rpc_http/stub"))  # noqa

from trpc_trpc_python_group_helloworld import pb
from trpc_trpc_python_group_helloworld import rpc

# pylint: disable=invalid-name
async def test_sync_Greeter_SayHello():
    """Test Greeter of SayHello"""
    proxy = rpc.GreeterClientProxyImpl()
    req = pb.HelloRequest()
    req.msg = "[sync] Hi SayHello"
    options = (Options().set_target('ip://127.0.0.1:8000').set_protocol('http').set_serialization_type(
        SerializationType.PB).set_network('tcp').set_short_conn(True))
    ctx = TrpcContext()
    try:
        ret = await proxy.asyncSayHello(ctx, req, options)
        print(f"SayHello ret is {ret}")
        assert ret is not None
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"error {exc}")
        assert 0

# url = http://{ip:port}/trpc.trpc_python_group.helloworld.Greeter/SayHello
# curl -X POST url -H 'Content-Type: application/json' -d '{"msg":"data"}'


if __name__ == "__main__":
    init_plugins()
    asyncio.run(test_sync_Greeter_SayHello())
