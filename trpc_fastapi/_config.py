# Tencent is pleased to support the open source community by making tRPC-FastAPI-Python available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# tRPC-FastAPI-Python is licensed under the Apache-2.0.
"""Configuration module for TRPC FastAPI Plugin.

This module provides configuration classes and utilities for TRPC FastAPI integration,
including server and client configurations with proper dataclass support.
"""

# System modules
from dataclasses import dataclass, field
from typing import Any, Dict, List

# Third-party modules
from trpc_sdk.config import TrpcConfig
from trpc_sdk.config import TrpcConfigParser
from trpc_sdk.log import logger

from ._constants import DEFAULT_UVICORN_LOG_LEVEL
from ._constants import TRPC_TO_UVICORN_LOG_LEVEL


def _normalize_uvicorn_log_level(level: Any) -> Any:
    """Map a tRPC log level name to a uvicorn.Config log_level value.

    uvicorn.config.LOG_LEVELS only accepts
    critical/error/warning/info/debug/trace. tRPC additionally accepts
    the alias ``warn`` and the name ``fatal``. Translate those names at
    this adapter boundary so uvicorn does not raise KeyError during
    configure_logging().

    Non-string values (int levels or None) are returned unchanged because
    uvicorn already accepts them.

    Args:
        level: Raw level from plugins.log or plugins.trpc_fastapi.uvicorn.

    Returns:
        A uvicorn-accepted string level, or the original non-string value.
    """
    if not isinstance(level, str):
        return level
    mapped = TRPC_TO_UVICORN_LOG_LEVEL.get(level.strip().lower())
    if mapped is not None:
        return mapped
    logger.warning(
        "Unsupported uvicorn log_level %r; falling back to %s. "
        "Accepted values: %s",
        level,
        DEFAULT_UVICORN_LOG_LEVEL,
        ", ".join(sorted(TRPC_TO_UVICORN_LOG_LEVEL)),
    )
    return DEFAULT_UVICORN_LOG_LEVEL


def trpc_dataclass(cls, *args, **kwargs):
    """Decorator that enhances dataclass with TRPC-specific functionality.

    This decorator wraps the standard dataclass decorator and adds TRPC-specific
    features such as automatic documentation generation based on fields_map.

    Args:
        cls: The class to be decorated as a dataclass
        *args: Variable length argument list for dataclass decorator
        **kwargs: Arbitrary keyword arguments for dataclass decorator

    Returns:
        class: The decorated class with enhanced __init__ documentation if fields_map exists

    Example:
        @trpc_dataclass
        class MyConfig:
            @classmethod
            def fields_map(cls):
                return "Configuration parameters documentation"
    """
    cls = dataclass(cls, *args, **kwargs)
    fields_map = getattr(cls, "fields_map", None)
    if fields_map:
        init_func = getattr(cls, '__init__')
        init_func.__doc__ = fields_map()
    return cls


@trpc_dataclass
class FastapiConfig:
    """Configuration class for FastAPI server component.

    This class defines the configuration parameters for the FastAPI server
    implementation within the TRPC framework.

    Attributes:
        uvicorn_config (dict): Configuration dictionary for uvicorn server settings
        fastapi_config (dict): Configuration dictionary for FastAPI application settings
    """

    uvicorn_config: dict = field(default_factory=dict)
    fastapi_config: dict = field(default_factory=dict)

    @classmethod
    def fields_map(cls):
        """Generate documentation for configuration fields mapping.

        Returns:
            str: Documentation string describing the configuration parameters
                 in a format suitable for __init__ method documentation.
        """
        return """
        :param uvicorn_config: `uvicorn` uvicorn configuration
        :param fastapi_config: `fastapi` fastapi configuration
        """


def load_fastapi_config() -> FastapiConfig:
    """Load and initialize FastAPI configuration from TRPC global plugins config.

    This function retrieves the FastAPI configuration from the TRPC global
    plugins configuration and initializes a FastapiConfig instance with
    appropriate default values for any missing settings.

    Returns:
        FastapiConfig: Initialized FastAPI configuration with default values for missing settings

    Raises:
        ConfigurationError: If there are issues loading or parsing the configuration
    """
    conf_dict: dict = _plugins_config().get("trpc_fastapi") or {}
    fastapi_config = FastapiConfig()
    TrpcConfigParser.populate_from_dict(conf_dict, fastapi_config)
    return fastapi_config


def _plugins_config() -> dict:
    """Return the ``plugins`` section, or an empty dict when the YAML has none."""
    return TrpcConfig.plugins_config() or {}


def _get_log_config() -> dict:
    """Retrieve log configuration parameters from TRPC global configuration.

    This internal function extracts log configuration settings from the TRPC
    global configuration, specifically looking for file-based logging settings.

    Returns:
        dict: Dictionary containing log level and log file configuration

    Note:
        This is an internal utility function and should not be called directly.
    """
    log_config = _plugins_config().get("log") or {}
    default_config: List[Dict] = log_config.get("default") or []
    log_params = {"log_level": DEFAULT_UVICORN_LOG_LEVEL, "log_config": "./uvicorn.log"}
    for config in default_config:
        if config.get("writer", '') == 'file':
            log_params["log_level"] = _normalize_uvicorn_log_level(config.get("level", 'info'))
            log_params["log_config"] = config.get("writer_config", {}).get("filename", './uvicorn.log')
            break
    return log_params


def get_fastapi_server_config() -> dict:
    """Retrieve FastAPI server configuration from loaded FastAPI config.

    This function provides access to the FastAPI-specific server configuration
    settings that are used to configure the FastAPI application instance.

    Returns:
        dict: FastAPI server configuration dictionary
    """
    fastapi_config = load_fastapi_config()
    return fastapi_config.fastapi_config


def get_uvicorn_server_config() -> dict:
    """Retrieve uvicorn server configuration with TRPC-specific defaults.

    This function constructs a uvicorn server configuration dictionary by
    combining TRPC framework defaults with user-provided uvicorn settings.

    Returns:
        dict: Complete uvicorn server configuration dictionary
    """
    server_config = TrpcConfig.server_config()
    max_size = server_config.max_rbuf_size
    log_params = _get_log_config()
    uvicorn_config = {
        "ws_max_size": max_size,
        "h11_max_incomplete_event_size": max_size,
        "log_level": log_params["log_level"],
        # "log_config": log_params["log_config"]
    }
    fastapi_config = load_fastapi_config()
    uvicorn_config.update(fastapi_config.uvicorn_config)
    if "log_level" in uvicorn_config:
        uvicorn_config["log_level"] = _normalize_uvicorn_log_level(uvicorn_config["log_level"])
    # check_idle_timeout is in milliseconds; uvicorn's timeout_keep_alive is in seconds.
    check_idle_timeout = server_config.check_idle_timeout
    if "timeout_keep_alive" not in uvicorn_config and check_idle_timeout > 0:
        uvicorn_config["timeout_keep_alive"] = max(1, check_idle_timeout // 1000)
    return uvicorn_config
