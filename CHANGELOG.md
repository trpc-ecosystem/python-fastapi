# Change Log

## 1.0.0

- 导入 `trpc_fastapi` 即注册 `http_fastapi` 协议，需在 `create_server` 之前导入。
- 把 tRPC 服务暴露为 FastAPI HTTP 路由，并支持中间件和 WebSocket。
