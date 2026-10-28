# Tencent is pleased to support the open source community by making tRPC-FastAPI-Python available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# tRPC-FastAPI-Python is licensed under the Apache-2.0.
"""Registry for TRPC FastAPI Plugin.

Binds a service ``protocol`` name to the fastapi codec, the SDK HTTP parser and
the SDK protocol starter. All of it must happen at import time: ``create_server``
looks up the codec and parser while building services, and the SDK reads the
protocol starter table in processes forked by ``Server.serve()``.

No server transport is registered: for a protocol with a starter,
``ServiceAdapter.run`` always serves it through a ``UserProtocolTransport``.

For the default ``http_fastapi`` protocol the codec and parser are registered
in :mod:`trpc_fastapi._codec`, so only the starter is bound here.
"""
from trpc_sdk.abc import BasePlugin
from trpc_sdk.abc import PluginInitPos
from trpc_sdk.abc import PluginType
from trpc_sdk.http import ServerHttpParser
from trpc_sdk.plugin import register_plugin
from trpc_sdk.transport import register_protocol_handle

from ._codec import TrpcFastApiServerHttpCodec
from ._constants import TRPC_FASTAPI_PROTOCOL
from ._trpc_server_process import start_fastapi
from .version import __version__ as trpc_fastapi_version


def register_protocol_to_fastapi(protocol: str) -> None:
    """Serve every service whose ``protocol`` is ``protocol`` through fastapi.

    Must be called at import time, before ``create_server`` and
    ``Server.serve()``. Calling it again for the same name is harmless.

    Args:
        protocol: Service ``protocol`` value from the YAML config.
    """
    register_plugin(PluginType.SERVER_CODEC, protocol, init_pos=PluginInitPos.WORKER)(TrpcFastApiServerHttpCodec)
    register_plugin(PluginType.SERVER_PARSER, protocol, init_pos=PluginInitPos.WORKER)(ServerHttpParser)
    register_protocol_handle(protocol, start_fastapi)


register_protocol_handle(TRPC_FASTAPI_PROTOCOL, start_fastapi)


@register_plugin(PluginType.USER_DEFINED,
                 TRPC_FASTAPI_PROTOCOL,
                 init_pos=PluginInitPos.WORKER,
                 version=trpc_fastapi_version,
                 report=True)
class TrpcFastapiPlugin(BasePlugin):
    """Marks trpc-fastapi for plugin version reporting; does nothing else."""
