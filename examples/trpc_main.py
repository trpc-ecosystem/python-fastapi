# Tencent is pleased to support the open source community by making tRPC-FastAPI-Python available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# tRPC-FastAPI-Python is licensed under the Apache-2.0.
"""Example server that registers Greeter and the FastAPI HTTP routes.

Importing ``trpc_fastapi`` registers the ``http_fastapi`` protocol. The process
then loads a config file and serves Greeter together with the example routes.
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List

from trpc_sdk.log import logger
from trpc_sdk.server import create_server

# import sdk and plugins

# pylint: disable=unused-import

# Importing the plugin registers it. This must happen before create_server.
import trpc_fastapi as _

DEFAULT_CONF_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "trpc_python.yaml"))

# add the example package and the generated stub to the path
sys.path.append(str(Path(__file__)))
sys.path.append(str(Path(__file__).parent / "rpc_http/stub"))
print(str(Path(__file__).parent / "rpc_http/stub"))

import normal_http as _
# Import WebSocket service
import http_websocket_service as _
import http_sse_service as _

from trpc_trpc_python_group_helloworld import rpc

from greeter import GreeterServicer



def parse_args(argv: List[str]):
    """Resolve the server config path from the command line.

    Args:
        argv: Full argument vector, including the script name at index 0.

    Returns:
        Path of a config file that exists. Falls back to the example config
        when the requested path is missing.
    """
    try:
        parser = argparse.ArgumentParser(description='TRPC Python Framework Server')
        parser.add_argument('--conf',
                            '-c',
                            default=DEFAULT_CONF_PATH,
                            help='start server with conf, for example: `python3 trpc_main.py  --conf=trpc_python.yaml`')
        args = parser.parse_args(argv[1:])  # Skip the script name
        if os.path.exists(args.conf):
            print(f"conf_path: {args.conf}")
            return args.conf
        print(f"conf_path: {args.conf} not exists")
        if os.path.exists(DEFAULT_CONF_PATH):
            print(f"use default conf path: {DEFAULT_CONF_PATH}")
            return DEFAULT_CONF_PATH
        print(f"default conf path: {DEFAULT_CONF_PATH} not exists, please check the path")
        sys.exit(1)
    except SystemExit:
        # argparse will call sys.exit() when --help is used or invalid args
        sys.exit(1)


def serve(conf_path: str):
    """Create the server, register Greeter, and block in ``serve``.

    Args:
        conf_path: Path of the tRPC config file.
    """

    svr = create_server(conf_path)

    rpc.register_GreeterServicer_server(svr, GreeterServicer())

    svr.serve()


def main():
    """Parse arguments and start the server."""

    # Resolve the config path from the command line.
    conf_path = parse_args(sys.argv)
    logger.info("load config %s", conf_path)

    # Start the server.
    serve(conf_path)


if __name__ == '__main__':
    sys.exit(main())
