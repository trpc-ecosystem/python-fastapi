# Tencent is pleased to support the open source community by making tRPC-FastAPI-Python available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# tRPC-FastAPI-Python is licensed under the Apache-2.0.
"""Tests for reading plugin and uvicorn settings from the tRPC config."""
from trpc_fastapi import load_fastapi_config
from trpc_fastapi._config import get_fastapi_server_config
from trpc_fastapi._config import get_uvicorn_server_config

BASE_YAML = """
server:
  app: test
  server: Greeter
  max_rbuf_size: 1048576
  check_idle_timeout: 60000
  service:
    - name: trpc.test.helloworld.FastApiGreeter
      ip: 127.0.0.1
      port: 18000
      network: tcp
      protocol: http_fastapi
"""


def test_check_idle_timeout_milliseconds_become_keep_alive_seconds(load_config):
    """Test check_idle_timeout (ms) is converted to timeout_keep_alive (s)."""
    load_config(BASE_YAML)

    config = get_uvicorn_server_config()

    assert config["timeout_keep_alive"] == 60
    assert config["ws_max_size"] == 1048576
    assert config["h11_max_incomplete_event_size"] == 1048576


def test_short_check_idle_timeout_rounds_up_to_one_second(load_config):
    """Test a sub-second idle timeout still keeps connections for one second."""
    load_config(BASE_YAML.replace("60000", "300"))

    assert get_uvicorn_server_config()["timeout_keep_alive"] == 1


def test_explicit_uvicorn_settings_win(load_config):
    """Test plugins.trpc_fastapi.uvicorn overrides derived values and maps log levels."""
    load_config(BASE_YAML + """
plugins:
  trpc_fastapi:
    uvicorn:
      timeout_keep_alive: 150
      log_level: fatal
    fastapi:
      title: demo
""")

    config = get_uvicorn_server_config()

    assert config["timeout_keep_alive"] == 150
    assert config["log_level"] == "critical"
    assert get_fastapi_server_config() == {"title": "demo"}
    assert load_fastapi_config().uvicorn_config["timeout_keep_alive"] == 150


def test_log_level_follows_file_writer(load_config):
    """Test the file log writer's level is translated to a uvicorn level."""
    load_config(BASE_YAML + """
plugins:
  log:
    default:
      - writer: console
        level: debug
      - writer: file
        level: warn
        writer_config:
          filename: ./hello.log
""")

    assert get_uvicorn_server_config()["log_level"] == "warning"


def test_no_plugins_section_uses_defaults(load_config):
    """Test a config without plugins still yields a usable uvicorn config."""
    load_config(BASE_YAML)

    config = get_uvicorn_server_config()

    assert config["log_level"] == "info"
    assert get_fastapi_server_config() == {}
