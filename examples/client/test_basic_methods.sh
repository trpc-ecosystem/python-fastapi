#!/bin/bash

# Test the common HTTP methods
# A short script that covers the usual methods

echo "=== 测试基本 HTTP 方法 ==="

BASE_URL="http://127.0.0.1:8000"
PATH="/fastapi_users"

# Use an absolute curl path when one is available
CURL_CMD="curl"
if [ -x "/usr/bin/curl" ]; then
    CURL_CMD="/usr/bin/curl"
elif [ -x "/usr/local/bin/curl" ]; then
    CURL_CMD="/usr/local/bin/curl"
fi

echo "使用 curl 命令: $CURL_CMD"

# Check that the server is running
echo "检查服务器状态..."
if ! $CURL_CMD -s "$BASE_URL/health" > /dev/null; then
    echo "❌ 服务器未运行，请先启动服务器："
    echo "python examples/trpc_main.py"
    exit 1
fi

echo "✅ 服务器运行正常"
echo ""

# 1. GET: list users
echo "1. GET 方法 - 获取用户列表"
$CURL_CMD -X GET "$BASE_URL$PATH" \
  -H "Accept: application/json" \
  -H "trpc-version: 1" \
  -H 'Trpc-Trans-Info: {"traceparent":"MDAtYmExZTBkYzhkNDVmNjQ0ODczNjYzOWY4NDZjNWEzZjUtMjFlMmYyMzk0OWVhMTdiNC0wMQ=="}'

echo -e "\n"

# 2. GET: fetch one user
echo "2. GET 方法 - 获取特定用户"
$CURL_CMD -X GET "$BASE_URL$PATH/1" \
  -H "Accept: application/json"

echo -e "\n"

# 3. POST: create a user
echo "3. POST 方法 - 创建用户"
$CURL_CMD -X POST "$BASE_URL$PATH" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"name": "Alice Johnson", "email": "alice@example.com", "age": 28}'

echo -e "\n"

# 4. PUT: replace a user
echo "4. PUT 方法 - 更新用户"
$CURL_CMD -X PUT "$BASE_URL$PATH/1" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"name": "John Updated", "email": "john.updated@example.com", "age": 31}'

echo -e "\n"

# 5. PATCH: update part of a user
echo "5. PATCH 方法 - 部分更新用户"
$CURL_CMD -X PATCH "$BASE_URL$PATH/1" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"age": 32}'

echo -e "\n"

# 6. DELETE: delete a user
echo "6. DELETE 方法 - 删除用户"
$CURL_CMD -X DELETE "$BASE_URL$PATH/2" \
  -H "Accept: application/json"

echo -e "\n"

# 7. HEAD: check the user endpoint
echo "7. HEAD 方法 - 检查用户端点"
$CURL_CMD -X HEAD "$BASE_URL$PATH" \
  -H "Accept: application/json"

echo -e "\n"

# 8. OPTIONS: check CORS options
echo "8. OPTIONS 方法 - 检查 CORS 选项"
$CURL_CMD -X OPTIONS "$BASE_URL$PATH" \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: Content-Type"

echo -e "\n"

# 9. TRACE: debug the request
echo "9. TRACE 方法 - 调试请求"
$CURL_CMD -X TRACE "$BASE_URL$PATH" \
  -H "Accept: application/json"

echo -e "\n"

# 10. Health check
echo "40. 健康检查"
$CURL_CMD -X GET "$BASE_URL/health" \
  -H "Accept: application/json"

echo -e "\n"

# 11. Root path
echo "41. 根路径"
$CURL_CMD -X GET "$BASE_URL/" \
  -H "Accept: application/json"

echo -e "\n"

echo "=== 基本 HTTP 方法测试完成 ==="
