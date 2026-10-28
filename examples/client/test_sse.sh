#!/bin/bash

# Test the FastAPI static-file service
# Uses this project's routes

echo "=== 测试 FastAPI 静态文件服务 ==="

BASE_URL="http://127.0.0.1:8000"

# Use an absolute curl path when one is available
CURL_CMD="curl"
if [ -x "/usr/bin/curl" ]; then
    CURL_CMD="/usr/bin/curl"
elif [ -x "/usr/local/bin/curl" ]; then
    CURL_CMD="/usr/local/bin/curl"
fi

echo "使用 curl 命令: $CURL_CMD"

echo "1. 测试根路径"

$CURL_CMD -X GET http://127.0.0.1:8000/sse -v

echo -e "\n"
