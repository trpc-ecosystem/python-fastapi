中文 | [English](README.en.md)

# tRPC-FastAPI

tRPC-FastAPI 是一个基于 tRPC-Python 框架（`trpc_sdk`）的 FastAPI 集成插件，提供开箱即用的 HTTP 服务能力，可以快速开发、调试、部署、调用 HTTP API 服务。`fastapi 只是服务端，所以该插件仅支持服务端， 任何http的客户端都可以访问`

## 核心特性

- **🚀 FastAPI 集成**：
    - **无缝集成**：与 tRPC-Python 框架无缝集成，保持 tRPC 的所有特性；
    - **HTTP 路由**：支持所有 HTTP 方法（GET、POST、PUT、DELETE、HEAD、OPTIONS 等）；
    - **自动文档**：自动生成 OpenAPI/Swagger 文档，支持交互式 API 测试；
    - **类型安全**：完整的类型注解支持，提供更好的开发体验；
- **🔧 开发工具**：
    - **静态文件服务**：支持 HTML、CSS、JS、图片等静态资源；
    - **模板引擎**：集成 Jinja2 模板引擎，支持动态页面渲染；
    - **版本管理**：自动获取和显示 FastAPI 及插件版本信息；
- **🌐 部署支持**：
    - **容器化**：支持 Docker 容器化部署；
    - **云原生**：支持 Kubernetes 等云原生环境；

## 安装方式

### 环境要求

- Python 3.8+
- Linux / macOS（tRPC-Python 不支持 Windows）
- tRPC-Python-SDK

### 安装

tRPC-Python 目前通过 git 依赖固定到上面的提交，`pip` 会随插件一起安装：
```bash
pip install -e .
# 如果期望安装带有 static 静态模板的：
# pip install -e ".[static]"
```

## 快速体验

### 基础使用

这里假设用户已经生成的 trpc 项目。完整说明和一键运行见 [examples/README.md](./examples/README.md)。主要文件如下：
```txt
examples/
├── normal_http/
├── http_sse_service.py
├── http_websocket_service.py
├── trpc_main.py
├── run_examples.sh
├── trpc_python.yaml                 # 单进程，一个 uvicorn
├── trpc_python_merge_threads.yaml   # 单进程，多条 handler 线程
├── trpc_python_separate_thread.yaml # 单进程，I/O 与 handler 分开
└── trpc_python_separate.yaml        # 多进程 separate
```

#### 1. 注册 HTTP 服务路由

可以在单独的文件中注册各种服务路由，假设当前的文件名为 [http_service.py](./examples/normal_http/_http_service.py)
```python

from trpc_fastapi import fastapi_route

@fastapi_route("/fastapi_http", ["GET", "HEAD"], route_params={'response_model': dict})
async def fastapi_http(request: Request) -> dict:
    """Test fastapi_http http"""
    logger.debug(f"=== normal_http, http_req header: {request.headers} ===")
    ctx = get_trpc_ctx()
    msg = ctx.get_client_message()
    register_service_name = "trpc.trpc_python_group.helloworld.Greeter1"
    msg_info = f"\n\n test_route, register service_name: {register_service_name}"
    msg_info = f"{msg_info}, callee_service_name: {msg.callee_service_name}\n\n"
    logger.debug(f"=== normal_http, msg_info: {msg_info} ===")
    return {"message": "This fastapi_http for [GET, HEAD]"}
```

#### 2. RPC 类型的 http 服务

根据桩代码生成工具生成的代码，带有 pb 对象，直接配置 http_fastapi 即可访问，通过桩代码访问的方式如下, 完整源码参考：[test_service_rpc](./examples/client/test_service_rpc.py)：

```python
from trpc_sdk.abc import TrpcContext
from trpc_sdk.client import Options
from trpc_sdk.serialization import SerializationType

async def test_sync_Greeter_SayHello():
    """Test Greeter of SayHello"""
    proxy = rpc.GreeterClientProxyImpl()
    req = pb.HelloRequest()
    req.msg = "[sync] Hi SayHello"
    options = (Options().set_target('ip://127.0.0.1:8000').set_protocol('http').set_serialization_type(
        SerializationType.PB).set_network('tcp').set_short_conn(True))
    ctx = TrpcContext()
    try:
        ret = await proxy.asyncSayHello(ctx, req, options)
        print(f"SayHello ret is {ret}")
        assert ret is not None
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"error {exc}")
        assert 0
```
curl 命令
```sh
curl -X POST http://127.0.0.1:8000/trpc.trpc_python_group.helloworld.Greeter/SayHello \
     -H 'Content-Type: application/json' -d '{"msg":"data"}'
```


在 trpc_main.py 中导入注册路由的文件，导入必须在 `create_server` 之前：

```python
# 导入过程其实是属于注册插件的过程，所以需要放在最前面
import trpc_fastapi as _
# 导入注册的 http service
import normal_http as _
```

如果要让其他协议名也由 FastAPI 承载（比如 a2a 插件），在 import 阶段调用 `register_protocol_to_fastapi`，同样必须早于 `create_server`：

```python
from trpc_fastapi import register_protocol_to_fastapi

register_protocol_to_fastapi("a2a")
```

#### 3. 配置文件
参考：[trpc_python.yaml](./examples/trpc_python.yaml)。不写 `global.processmodel` 时是单进程、一个事件循环，uvicorn 跑在服务进程的一个线程里。
```yaml
server:
  service:
    - name: trpc.trpc_python_group.helloworld.FastApiGreeter
      ip: 0.0.0.0
      port: 8000
      network: tcp
      protocol: http_fastapi
```

#### 运行模式

| 配置 | `global.processmodel` | uvicorn |
|---|---|---|
| [trpc_python.yaml](./examples/trpc_python.yaml) | 不写 | 整个服务一个 |
| [trpc_python_merge_threads.yaml](./examples/trpc_python_merge_threads.yaml) | `single_process`，`handle_num: 2` | serving thread 0 起一个 |
| [trpc_python_separate_thread.yaml](./examples/trpc_python_separate_thread.yaml) | `single_process`，`io_handle_type: separate` | serving thread 0 起一个 |
| [trpc_python_separate.yaml](./examples/trpc_python_separate.yaml) | `multi_process`，`io_handle_type: separate`，`handle_num: 2` | 每个 rpc task 一个，`SO_REUSEPORT` 听 8000。I/O 进程只听 tRPC 端口 |

多进程 separate 的片段：

```yaml
global:
  processmodel:
    mode: multi_process
    io_handle_type: separate
    handle_num: 2
```

#### 4. 启动服务

在 [trpc_main.py](./examples/trpc_main.py) 中导入注册路由的文件，例如上面的: http_service.py 文件

```sh
cd examples
./run_examples.sh
# 或手动启动
python3 trpc_main.py --conf trpc_python.yaml
python3 trpc_main.py --conf trpc_python_separate.yaml
```

#### 5. 访问服务

- 浏览器访问：http://{IP}:{Port}/docs (IP 和 Port 为配置文件中的配置，如果是 0.0.0.0.则需要换成你环境具体的ip)

- curl 访问
  ```sh
  curl -X GET http://127.0.0.1:8000/details -v
  ```

### 高级功能

#### SSE 服务

- 服务代码[http_sse_service](./examples/http_sse_service.py)
  ```python
  import asyncio
  from fastapi.responses import StreamingResponse

  from trpc_fastapi import fastapi_route

  async def event_generator():
      """
      模拟异步生成事件，每隔1秒推送一条消息。
      """
      counter = 0
      while True:
          counter += 1
          # SSE格式: data: 消息内容\n\n
          yield f"data: 这是第 {counter} 条消息\n\n"
          await asyncio.sleep(1)

  @fastapi_route('/sse', ["GET"])
  async def sse_endpoint():
      """
      SSE 端点，返回事件流。
      """
      return StreamingResponse(event_generator(), media_type='text/event-stream')
  ```

- 在 [trpc_main.py](./examples/trpc_main.py) 导入
  ```python
  import http_sse_service as _
  ```
- 客户端测试
  ```sh
  curl -X GET http://127.0.0.1:8000/sse -v
  ```

#### Websocket 特性

- 服务代码[http_websocket_service](./examples/http_websocket_service.py)
  ```python
  from fastapi import WebSocket
  from fastapi.responses import HTMLResponse

  from trpc_sdk.log import logger
  from trpc_fastapi import fastapi_route

  @fastapi_route("/ws", method="WEBSOCKET")
  async def websocket_endpoint(websocket: WebSocket):
      await websocket.accept()
      try:
          while True:
              data = await websocket.receive_text()
              await websocket.send_text(f"Message text was: {data}")
      except Exception as e:  # pylint: disable=broad-except
          logger.error(f"websocket error: {e}")
  ```

- 在 [trpc_main.py](./examples/trpc_main.py) 导入
  ```python
  import http_websocket_service as _
  ```
- 客户端测试
  ```sh
  python3 examples/client/test_websocket_client.py
  ```

#### 静态文件服务

参考：[static_http_service](./examples/normal_http/_static_http_service.py)
- 安装
  静态安装可能需要使用渲染，推荐这种安装方式
  ```sh
  pip install -e ".[static]"
  ```
- 注册静态文件路径
  ```python
  from trpc_fastapi import fastapi_register_static
  # 创建静态文件目录
  static_dir = Path(__file__).parent / "static"
  # 模板渲染使用的文件
  templates_dir = Path(__file__).parent / "templates"

  fastapi_register_static("/static", static_dir)
  ```
- 注册静态服务路由
  ```python
  from trpc_fastapi import fastapi_register_get, trpc_fastapi_version, get_fastapi_app

  @fastapi_register_get("/", route_params={'response_class': HTMLResponse})
  async def static_page(request: Request):
      """根路径 - 返回 HTML 页面"""
      return templates.TemplateResponse(
          request,
          "static_page.html", {
              "trpc_fastapi_version": trpc_fastapi_version,
              "fastapi_version": fastapi_version,
              "endpoints": get_all_endpoints()
          })
  ```
  `get_fastapi_app()` 要在 `async def` 路由里调用：同步路由由 FastAPI 放到线程池执行，找不到当前 uvicorn 线程对应的 app。
- 浏览器访问：http://{IP}:{Port}/ (IP 和 Port 为配置文件中的配置，如果是 0.0.0.0.则需要换成你环境具体的ip)

### 开发环境设置

```bash
# 克隆本仓库后进入项目目录，安装开发依赖
pip install -e ".[all]"

# 运行测试
pytest tests

# 代码格式化
./format.sh
```

### 提交规范

- 使用 `feat:` 前缀表示新功能
- 使用 `fix:` 前缀表示修复
- 使用 `docs:` 前缀表示文档更新

## 许可证

本项目采用 Apache-2.0 许可证。详见 [LICENSE](LICENSE) 文件。
