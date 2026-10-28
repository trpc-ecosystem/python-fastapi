# Tencent is pleased to support the open source community by making tRPC-FastAPI-Python available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# tRPC-FastAPI-Python is licensed under the Apache-2.0.
"""Example routes for static files, templates, downloads, and version info."""
import os
from pathlib import Path
from typing import Any, Dict
from fastapi import Request
from fastapi import __version__ as fastapi_version
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates

from trpc_fastapi import fastapi_register_static
from trpc_fastapi import trpc_fastapi_version
from trpc_fastapi import fastapi_register_static
from trpc_fastapi import get_fastapi_app
from trpc_fastapi import fastapi_register_get

# Directory of static files served by the example.
static_dir = Path(__file__).parent / "static"
templates_dir = Path(__file__).parent / "templates"

fastapi_register_static("/static", static_dir)

# Configure the template engine.
templates = Jinja2Templates(directory=templates_dir)


# Collect every registered endpoint.
def get_all_endpoints() -> Dict[str, Dict[str, Any]]:
    """Return the routes currently registered on the FastAPI app.

    Returns:
        Mapping of path to path, methods, and route name. Static-file routes
        and ``/openapi.json`` are omitted.
    """

    app = get_fastapi_app()
    endpoints = {}

    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            # Skip static-file routes and the OpenAPI document.
            if not route.path.startswith('/static') and route.path != '/openapi.json':
                methods = list(route.methods) if route.methods else ['GET']
                endpoints[route.path] = {
                    'path': route.path,
                    'methods': methods,
                    'name': getattr(route, 'name', 'unnamed'),
                }

    return endpoints


# 1. Root path: return an HTML page.
@fastapi_register_get("/", route_params={'response_class': HTMLResponse})
async def static_page(request: Request):
    """Render the static-file demo page.

    Args:
        request: Incoming HTTP request passed to the template.

    Returns:
        Rendered HTML response with version info and the route list.
    """
    # Render the template with version info.
    print(f"trpc_fastapi_version: {trpc_fastapi_version}")
    print(f"fastapi_version: {fastapi_version}")
    return templates.TemplateResponse(
        request,
        "static_page.html", {
            "trpc_fastapi_version": trpc_fastapi_version,
            "fastapi_version": fastapi_version,
            "endpoints": get_all_endpoints()
        })


# 2. Template page.
@fastapi_register_get("/template_page", route_params={'response_class': HTMLResponse})
async def template_page(request: Request):
    """Render the Jinja2 template page.

    Args:
        request: Incoming HTTP request passed to the template.

    Returns:
        Rendered HTML response.
    """
    return templates.TemplateResponse(request, "index.html", {
        "title": "模板页面",
        "message": "这是一个使用 Jinja2 模板的页面",
        "items": ["项目 1", "项目 2", "项目 3"]
    })


# 3. File download.
@fastapi_register_get("/download_file")
async def download_file():
    """Write a sample file and return it as a download.

    Returns:
        The sample text file.
    """
    # Create a sample file.
    file_path = os.path.join(static_dir, "example.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("这是一个示例文件\n")
        f.write("FastAPI 静态文件服务\n")
        f.write("支持各种文件类型\n")

    return FileResponse(path=file_path, filename="example.txt", media_type="text/plain")


# 4. Image files.
@fastapi_register_get("/image/{filename}")
async def get_image(filename: str):
    """Return an image from the static images directory.

    Args:
        filename: Image file name under ``static/images``.

    Returns:
        The image file, or an error object when it is missing.
    """
    image_path = os.path.join(static_dir, "images", filename)
    if os.path.exists(image_path):
        return FileResponse(image_path)
    else:
        return {"error": "图片不存在"}


# 5. Version-info API.
@fastapi_register_get("/version_info")
async def get_version_info():
    """Return the plugin and FastAPI versions.

    Returns:
        Version fields and a short description.
    """
    return {
        "trpc_fastapi_version": trpc_fastapi_version,
        "fastapi_version": fastapi_version,
        "description": "TRPC FastAPI 版本信息"
    }
