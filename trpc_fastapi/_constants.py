# Tencent is pleased to support the open source community by making tRPC-FastAPI-Python available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# tRPC-FastAPI-Python is licensed under the Apache-2.0.
"""Constants for TRPC FastAPI Plugin.

This module defines all constants used by the TRPC FastAPI plugin.
It includes protocol definitions, plugin metadata, HTTP methods,
and other configuration constants required for the plugin operation.
"""
from typing import Dict, Final, List

TRPC_FASTAPI_PROTOCOL = "http_fastapi"
TRPC_FASTAPI_PLUGIN_DESCRIPTION = "TRPC Fastapi Plugin"
TRPC_FASTAPI_PLUGIN_AUTHOR = "Tencent"
TRPC_FASTAPI_PLUGIN_AUTHOR_EMAIL = "team@tencent.com"
TRPC_FASTAPI_PLUGIN_LICENSE = "MIT"
TRPC_FASTAPI_PLUGIN_LICENSE_FILE = "LICENSE"

HTTP_CODE: str = "status_code"
CONTENT_TYPE: str = "Content-Type"
SERVER_NAME: str = "__server_name"
PROTOCOL_NAME: str = "__protocol_name"
CALLBACK_NAME: str = "__trpc_fastapi_callback"
# Attribute on ``multiprocessing.current_process()`` holding this process's
# ``FastapiProcess``. A forked rpc task gets a fresh process object, so it
# never sees the parent's value.
FASTAPI_PROCESS_VAR: str = "trpc_fastapi_process"

WEB_SOCKET_METHOD: Final[str] = "WEBSOCKET"
ANY_METHOD: Final[str] = "*"
GET_METHOD: Final[str] = "GET"
HEAD_METHOD: Final[str] = "HEAD"
DELETE_METHOD: Final[str] = "DELETE"
OPTIONS_METHOD: Final[str] = "OPTIONS"
PATCH_METHOD: Final[str] = "PATCH"
POST_METHOD: Final[str] = "POST"
PUT_METHOD: Final[str] = "PUT"
TRACE_METHOD: Final[str] = "TRACE"
ALL_METHODS: Final[List[str]] = [
    GET_METHOD, POST_METHOD, PUT_METHOD, DELETE_METHOD, PATCH_METHOD, OPTIONS_METHOD, HEAD_METHOD, TRACE_METHOD
]

# uvicorn only accepts the names in uvicorn.config.LOG_LEVELS, which has no
# "warn"/"fatal"; translate tRPC level names at the adapter boundary.
TRPC_TO_UVICORN_LOG_LEVEL: Final[Dict[str, str]] = {
    "trace": "trace",
    "debug": "debug",
    "info": "info",
    "warn": "warning",
    "warning": "warning",
    "error": "error",
    "fatal": "critical",
    "critical": "critical",
}
DEFAULT_UVICORN_LOG_LEVEL: Final[str] = "info"
