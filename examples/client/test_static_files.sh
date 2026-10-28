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

# Check that the server is running
echo "检查服务器状态..."
if ! $CURL_CMD -s "$BASE_URL/health" > /dev/null; then
    echo "❌ 服务器未运行，请先启动服务器："
    echo "python examples/trpc_main.py"
    exit 1
fi

echo "✅ 服务器运行正常"
echo ""

# 1. Test the root path
echo "1. 测试根路径"
$CURL_CMD -X GET "$BASE_URL/" \
  -H "Accept: text/html"

echo -e "\n"

# 2. Test the static CSS file
echo "2. 测试静态 CSS 文件"
$CURL_CMD -X GET "$BASE_URL/static/css/style.css" \
  -H "Accept: text/css"

echo -e "\n"

# 3. Test the static JavaScript file
echo "3. 测试静态 JavaScript 文件"
$CURL_CMD -X GET "$BASE_URL/static/js/script.js" \
  -H "Accept: application/javascript"

echo -e "\n"

# 4. Test static HTML page 1
echo "4. 测试静态 HTML 页面 1"
$CURL_CMD -X GET "$BASE_URL/static/html/page1.html" \
  -H "Accept: text/html"

echo -e "\n"

# 5. Test static HTML page 2
echo "5. 测试静态 HTML 页面 2"
$CURL_CMD -X GET "$BASE_URL/static/html/page2.html" \
  -H "Accept: text/html"

echo -e "\n"

# 6. Test the template page
echo "6. 测试模板页面"
$CURL_CMD -X GET "$BASE_URL/template_page" \
  -H "Accept: text/html"

echo -e "\n"

# 7. Test the file download
echo "7. 测试下载文件"
$CURL_CMD -X GET "$BASE_URL/download_file" \
  -H "Accept: text/plain"

echo -e "\n"

# 8. Test the health check
echo "8. 测试健康检查"
$CURL_CMD -X GET "$BASE_URL/health" \
  -H "Accept: application/json"

echo -e "\n"

# 9. Test a HEAD request
echo "9. 测试 HEAD 请求"
$CURL_CMD -X HEAD "$BASE_URL/static/css/style.css" \
  -H "Accept: text/css"

echo -e "\n"

# 10. Test a missing file
echo "11. 测试不存在的文件"
$CURL_CMD -X GET "$BASE_URL/static/nonexistent.txt" \
  -H "Accept: text/plain"

echo -e "\n"

# 11. Test an image file, if one exists
echo "12. 测试图片文件"
$CURL_CMD -X GET "$BASE_URL/image/logo.png" \
  -H "Accept: image/png"

echo -e "\n"

# 12. Test cache headers
echo "13. 测试缓存头"
$CURL_CMD -X GET "$BASE_URL/static/css/style.css" \
  -H "Accept: text/css" \
  -H "If-None-Match: \"etag123\""

echo -e "\n"

# 13. Test compression
echo "14. 测试压缩"
$CURL_CMD -X GET "$BASE_URL/static/css/style.css" \
  -H "Accept: text/css" \
  -H "Accept-Encoding: gzip, deflate"

echo -e "\n"

# 14. Test a range request
echo "15. 测试范围请求"
$CURL_CMD -X GET "$BASE_URL/static/css/style.css" \
  -H "Accept: text/css" \
  -H "Range: bytes=0-1023"

echo -e "\n"

echo "=== 静态文件服务测试完成 ==="
