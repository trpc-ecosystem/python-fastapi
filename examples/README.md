# tRPC FastAPI 示例

本示例在一个进程里同时提供 FastAPI HTTP 服务和原生 tRPC Greeter。HTTP 走 8000，tRPC 走 8001。

## 关键特性

- **装饰器路由**：`GET` / `POST` / `PUT` / `PATCH` / `DELETE` / `HEAD` / `OPTIONS` / `TRACE`，以及 `/health`、`/details`
- **RPC over HTTP**：Greeter 的 `SayHello` 可以用 JSON `curl`，也可以用桩代码按 PB 调用
- **静态页和模板**：`/`、`/template_page`、`/static/...`、`/download_file`
- **SSE 和 WebSocket**：`/sse` 持续推事件，`/ws` 回显一条文本
- **四种进程模型**：同一套服务配四份 YAML，用来看 uvicorn 落在哪个进程、哪条线程

关键文件：

- [trpc_main.py](trpc_main.py)：先 `import trpc_fastapi` 注册协议，再导入路由和 Greeter，然后 `create_server` + `serve`
- [normal_http/](normal_http/)：HTTP 方法、健康检查、静态文件和 Jinja2 页面
- [http_sse_service.py](http_sse_service.py)：`/sse`
- [http_websocket_service.py](http_websocket_service.py)：`/ws` 和浏览器页 `/ws_index`
- [greeter.py](greeter.py)：`SayHello` 把请求里的 `msg` 加上 `hello: ` 前缀返回
- [client/test_service_rpc.py](client/test_service_rpc.py)：用桩代码打 `SayHello`
- [client/test_websocket_client.py](client/test_websocket_client.py)：连上 `/ws`，发一句话并打印回复
- [run_examples.sh](run_examples.sh)：起服务、等 8000、跑检查、停服务
- `trpc_python*.yaml`：每种进程模型一份。FastAPI 都听 `0.0.0.0:8000`，tRPC 都听 `0.0.0.0:8001`

调用关系：

```text
curl / 桩代码 / WebSocket 客户端
└── :8000  http_fastapi（uvicorn）
    ├── 装饰器路由：/health、/fastapi_users、/sse、/ws、静态文件
    └── RPC：/trpc.trpc_python_group.helloworld.Greeter/SayHello
```

## 环境要求

- Python >= 3.8
- macOS 或 Linux
- 本机 8000、8001 空闲
- 在仓库根目录安装：`pip install -e ".[all]"`。静态页要 `jinja2`，WebSocket 客户端要 `websockets`，这组额外依赖都在 `.[all]` 里

## 运行步骤

在 `examples` 目录下：

```bash
./run_examples.sh list
./run_examples.sh
./run_examples.sh http trpc_python_separate.yaml
./run_examples.sh all
```

`./run_examples.sh` 和 `./run_examples.sh http` 一样，用 [trpc_python.yaml](trpc_python.yaml)。`http` 后面可以换成本目录里的另一份 YAML，或一个绝对路径。`all` 按下面表格的顺序各跑一遍。

解释器按 `$PYTHON`、`../venv/bin/python`、`python3` 的顺序选。服务日志写在 `examples/.server_run.log`。上一级目录里有 `trpc_sdk` 包时，脚本把它的父目录放在 `PYTHONPATH` 前面。

手动两步，效果和默认的 `http` 相同：

```bash
# 终端 1，当前目录必须是 examples
python trpc_main.py -c trpc_python.yaml

# 终端 2
curl -sS http://127.0.0.1:8000/health
curl -sS -X POST http://127.0.0.1:8000/trpc.trpc_python_group.helloworld.Greeter/SayHello \
  -H 'Content-Type: application/json' -d '{"msg":"data"}'
python client/test_service_rpc.py
python client/test_websocket_client.py
curl -N --max-time 3 http://127.0.0.1:8000/sse
```

浏览器打开 <http://127.0.0.1:8000/docs>、<http://127.0.0.1:8000/> 和 <http://127.0.0.1:8000/ws_index>。

| 配置 | `global.processmodel` | uvicorn |
| --- | --- | --- |
| `trpc_python.yaml` | 不写。单进程，一个事件循环 | 服务进程里一个线程 |
| `trpc_python_merge_threads.yaml` | `single_process`，`handle_num: 2` | serving thread 0 起一个 |
| `trpc_python_separate_thread.yaml` | `single_process`，`io_handle_type: separate`，`io_num: 1`，`handle_num: 2` | serving thread 0 起一个。HTTP 处理不进 handler 线程 |
| `trpc_python_separate.yaml` | `multi_process`，`io_handle_type: separate`，`handle_num: 2` | 每个 rpc task 一个。I/O 进程只听 8001，两个 rpc task 用 `SO_REUSEPORT` 听 8000 |

## 运行结果

`./run_examples.sh` 对下面这些请求检查状态码和正文，每一项打印 `[PASS]`：

| 请求 | 预期 |
| --- | --- |
| `GET /health` | 正文含 `healthy` |
| `GET /fastapi_http` | 正文含 `This fastapi_http` |
| `GET /fastapi_users` | 正文含 `John Doe` |
| `GET /trpc_http` | 正文含 `This normal_http` |
| `POST .../Greeter/SayHello`，body `{"msg":"data"}` | 正文含 `hello:` |
| `GET /`、`/static/html/page1.html`、`/static/css/style.css` | 状态码 200 |
| `GET /download_file` | 状态码 200，响应头带 `content-disposition` |
| `GET /sse`，最多等 3 秒 | 输出里有 `data:` |
| `client/test_service_rpc.py` | 打印 `SayHello ret is msg: "hello: [sync] Hi SayHello"` |
| `client/test_websocket_client.py` | 打印 `收到服务器消息: Message text was: 你好，服务器！` |

`client/test_basic_methods.sh`、`client/test_static_files.sh`、`client/test_sse.sh` 是手动查看输出用的。一键脚本自己发请求并检查结果。

## 适用场景

- 确认插件注册、装饰器路由、JSON RPC、静态页、SSE、WebSocket 在默认配置下可用
- 换 YAML 之后确认 8000 仍然由对应进程模型里的 uvicorn 提供
