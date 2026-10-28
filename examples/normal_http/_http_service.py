# Tencent is pleased to support the open source community by making tRPC-FastAPI-Python available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# tRPC-FastAPI-Python is licensed under the Apache-2.0.
"""Example HTTP handlers for tRPC-style routes and FastAPI methods."""

from typing import Optional
from pydantic import BaseModel

from fastapi import Request, Response, HTTPException
from fastapi import __version__ as fastapi_version
from fastapi.responses import JSONResponse

from trpc_sdk.abc import get_message
from trpc_sdk.log import logger

from trpc_fastapi import trpc_fastapi_version
from trpc_fastapi import get_trpc_ctx
from trpc_fastapi import fastapi_route
from trpc_fastapi import get_service_name
from trpc_fastapi import fastapi_register_any
from trpc_fastapi import fastapi_register_get
from trpc_fastapi import fastapi_register_post
from trpc_fastapi import fastapi_register_put
from trpc_fastapi import fastapi_register_patch
from trpc_fastapi import fastapi_register_delete
from trpc_fastapi import fastapi_register_head
from trpc_fastapi import fastapi_register_options
from trpc_fastapi import fastapi_register_trace

from ._static_http_service import get_all_endpoints

# 1. Existing tRPC-Python HTTP handler.
@fastapi_register_any("/trpc_http")
async def normal_http(request: Request) -> dict:
    """Test normal http"""
    logger.debug(f"=== normal_http, http_req header: {request.headers} ===")
    ctx = get_trpc_ctx()
    msg = get_message(ctx)
    register_service_name = "trpc.trpc_python_group.helloworld.Greeter1"
    msg_info = f"\n\n test_route, register service_name: {register_service_name}"
    msg_info = f"{msg_info}, callee_service_name: {msg.callee_service_name}\n\n"
    logger.debug(f"=== normal_http, msg_info: {msg_info} ===")
    return {"message": "This normal_http"}


# 2. FastAPI HTTP handler that returns a dict.
@fastapi_route("/fastapi_http", ["GET", "HEAD"], route_params={'response_model': dict})
async def fastapi_http(request: Request) -> dict:
    """Test fastapi_http http"""
    logger.debug(f"=== normal_http, http_req header: {request.headers} ===")
    ctx = get_trpc_ctx()
    msg = get_message(ctx)
    register_service_name = get_service_name(ctx)
    msg_info = f"\n\n test_route, register service_name: {register_service_name}"
    msg_info = f"{msg_info}, callee_service_name: {msg.callee_service_name}\n\n"
    logger.debug(f"=== normal_http, msg_info: {msg_info} ===")
    return {"message": "This fastapi_http for [GET, HEAD]"}


class User(BaseModel):
    """User payload for create and full update."""
    name: str
    email: str
    age: Optional[int] = None


class UserUpdate(BaseModel):
    """Partial user payload; omitted fields stay unchanged."""
    name: Optional[str] = None
    email: Optional[str] = None
    age: Optional[int] = None


# In-memory user store.
users_db = {
    1: {
        "name": "John Doe",
        "email": "john@example.com",
        "age": 30
    },
    2: {
        "name": "Jane Smith",
        "email": "jane@example.com",
        "age": 25
    }
}


# 1. GET: list users.
@fastapi_register_get("/fastapi_users")
async def get_users():
    """Return every stored user.

    Returns:
        A list of user records.
    """
    ctx = get_trpc_ctx()
    msg = get_message(ctx)
    print(f"=== get_users, msg.server_req_head.version: {msg.server_req_head.version} ===")
    print(f"=== get_users, msg.server_meta_data: {msg.server_meta_data} ===")
    return {"users": list(users_db.values())}


@fastapi_register_get("/fastapi_users/{user_id}")
async def get_user(user_id: int):
    """Return one stored user.

    Args:
        user_id: Key in the in-memory store.

    Returns:
        The user record.
    """
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user": users_db[user_id]}


# 2. POST: create a user.
@fastapi_register_post("/fastapi_users")
async def create_user(user: User):
    """Store a new user.

    Args:
        user: User payload.

    Returns:
        The assigned id and the stored record.
    """
    user_id = max(users_db.keys()) + 1 if users_db else 1
    users_db[user_id] = user.model_dump()
    return {"message": "User created", "user_id": user_id, "user": user.model_dump()}


# 3. PUT: replace a user.
@fastapi_register_put("/fastapi_users/{user_id}")
async def update_user(user_id: int, user: User):
    """Replace a stored user.

    Args:
        user_id: Key in the in-memory store.
        user: Full user payload.

    Returns:
        The stored record.
    """
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    users_db[user_id] = user.model_dump()
    return {"message": "User updated", "user": user.model_dump()}


# 4. PATCH: update part of a user.
@fastapi_register_patch("/fastapi_users/{user_id}")
async def partial_update_user(user_id: int, user_update: UserUpdate):
    """Update the fields present on a stored user.

    Args:
        user_id: Key in the in-memory store.
        user_update: Fields to change. Omitted fields stay as they are.

    Returns:
        The stored record after the update.
    """
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")

    # Update only the fields the client sent.
    for field, value in user_update.model_dump(exclude_unset=True).items():
        users_db[user_id][field] = value

    return {"message": "User partially updated", "user": users_db[user_id]}


# 5. DELETE: delete a user.
@fastapi_register_delete("/fastapi_users/{user_id}")
async def delete_user(user_id: int):
    """Delete a stored user.

    Args:
        user_id: Key in the in-memory store.

    Returns:
        The record that was removed.
    """
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")

    deleted_user = users_db.pop(user_id)
    return {"message": "User deleted", "user": deleted_user}


# 6. HEAD: check user endpoints.
@fastapi_register_head("/fastapi_users")
async def head_users():
    """Return headers for the user-list endpoint.

    Returns:
        An empty response with a JSON content type.
    """
    return Response(headers={"Content-Type": "application/json"})


@fastapi_register_head("/fastapi_users/{user_id}")
async def head_user(user_id: int):
    """Return headers for one user endpoint.

    Args:
        user_id: Key in the in-memory store.

    Returns:
        An empty response with a JSON content type.
    """
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    return Response(headers={"Content-Type": "application/json"})


# 7. OPTIONS: report CORS options.
@fastapi_register_options("/fastapi_users")
async def options_users():
    """Return the methods allowed on the user-list endpoint.

    Returns:
        An empty response with ``Allow`` and CORS headers.
    """
    return Response(
        headers={
            "Allow": "GET, POST, HEAD, OPTIONS",
            "Access-Control-Allow-Methods": "GET, POST, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "86400"
        })


@fastapi_route("/fastapi_users/{user_id}", ["OPTIONS"])
async def options_user(user_id: int):
    """Return the methods allowed on one user endpoint.

    Args:
        user_id: Key in the in-memory store. Not read by this handler.

    Returns:
        An empty response with ``Allow`` and CORS headers.
    """
    return Response(
        headers={
            "Allow": "GET, PUT, PATCH, DELETE, HEAD, OPTIONS",
            "Access-Control-Allow-Methods": "GET, PUT, PATCH, DELETE, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "86400"
        })


# 8. TRACE: echo the request.
@fastapi_register_trace("/fastapi_users")
async def trace_users(request: Request):
    """Echo the request method, URL, headers, and query.

    Args:
        request: Incoming HTTP request.

    Returns:
        JSON describing the request.
    """
    trace_info = {
        "method": request.method,
        "url": str(request.url),
        "headers": dict(request.headers),
        "query_params": dict(request.query_params)
    }
    return JSONResponse(content=trace_info)


# Health check.
@fastapi_register_get("/health")
async def health_check():
    """Report that the example service is up.

    Returns:
        Status and the number of stored users.
    """
    return {"status": "healthy", "users_count": len(users_db)}


# Detailed endpoint info.
@fastapi_register_get("/details")
async def details():
    """Return plugin versions and the registered routes.

    Returns:
        Version fields and the route list.
    """
    return {
        "message": "TRPC FastAPI HTTP Methods API",
        "trpc_fastapi_version": trpc_fastapi_version,
        "fastapi_version": fastapi_version,
        "endpoints": get_all_endpoints()
    }
